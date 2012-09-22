from construct import *
from pyasm2 import java

def _cstringify(s, maxlen):
    s = s[:min(len(s), maxlen)]
    s = s.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
    return ''.join(ch if ord(ch) >= 0x20 and ord(ch) < 0x7f else '\\u%04x' %
        ord(ch) for ch in s)

_constant_pool_stringify = {
    'Class': lambda x: '%s' % x.name.value,
    'Fieldref': lambda x: '%s.%s %s' % (x.class_.name.value,
        x.name_and_type.name.value, x.name_and_type.descriptor.value),
    'Methodref': lambda x: '%s.%s %s' % (x.class_.name.value,
        x.name_and_type.name.value, x.name_and_type.descriptor.value),
    'InterfaceMethodref': lambda x: '%s.%s %s' % (x.class_.name.value,
        x.name_and_type.name.value, x.name_and_type.descriptor.value),
    'String': lambda x: '"%s"' % _cstringify(x.string.value, 32),
    'Integer': lambda x: str(x.value),
    'Float': lambda x: str(x.value),
    'Long': lambda x: str(x.value),
    'Double': lambda x: str(x.value),
}

def _constant_pool_str(x):
    return _constant_pool_stringify[x.tag[9:]](x)

ConstantPoolInfo = Struct('ConstantPoolInfo',
    Enum(UBInt8('tag'),
        CONSTANT_Class = 7,
        CONSTANT_Fieldref = 9,
        CONSTANT_Methodref = 10,
        CONSTANT_InterfaceMethodref = 11,
        CONSTANT_String = 8,
        CONSTANT_Integer = 3,
        CONSTANT_Float = 4,
        CONSTANT_Long = 5,
        CONSTANT_Double = 6,
        CONSTANT_NameAndType = 12,
        CONSTANT_Utf8 = 1
    ),
    Embed(Switch('info', lambda ctx: ctx.tag, {
        'CONSTANT_Class': Struct('CONSTANT_Class_info',
            UBInt16('name_index')),
        'CONSTANT_Fieldref': Struct('CONSTANT_Fieldref_info',
            UBInt16('class__index'),
            UBInt16('name_and_type_index')),
        'CONSTANT_Methodref': Struct('CONSTANT_Methodref_info',
            UBInt16('class__index'),
            UBInt16('name_and_type_index')),
        'CONSTANT_InterfaceMethodref': Struct(
            'CONSTANT_InterfaceMethodref_info',
            UBInt16('class__index'),
            UBInt16('name_and_type_index')),
        'CONSTANT_String': Struct('CONSTANT_String_info',
            UBInt16('string_index')),
        'CONSTANT_Integer': Struct('CONSTANT_Integer_info',
            SBInt32('value')),
        'CONSTANT_Float': Struct('CONSTANT_Float_info',
            BFloat32('value')),
        'CONSTANT_Long': Struct('CONSTANT_Long_info',
            SBInt64('value')),
        'CONSTANT_Double': Struct('CONSTANT_Double_info',
            BFloat64('value')),
        'CONSTANT_NameAndType': Struct('CONSTANT_NameAndType_info',
            UBInt16('name_index'),
            UBInt16('descriptor_index')),
        'CONSTANT_Utf8': Struct('CONSTANT_Utf8_info',
            PascalString('value', length_field=UBInt16('length'))),
    })))

AttributeInfo = Struct('AttributeInfo',
    UBInt16('attribute_name_index'),
    UBInt32('attribute_length'),
    MetaField('info', lambda ctx: ctx.attribute_length))

CodeAttribute = Struct('CodeAttribute',
    UBInt16('max_stack'),
    UBInt16('max_locals'),
    UBInt32('code_length'),
    MetaField('code', lambda ctx: ctx.code_length),
    UBInt16('exception_table_length'),
    MetaArray(lambda ctx: ctx.exception_table_length, Struct(
        'exception_table',
        UBInt16('start_pc'),
        UBInt16('end_pc'),
        UBInt16('handler_pc'),
        UBInt16('catch_type'))),
    UBInt16('attributes_count'),
    MetaArray(lambda ctx: ctx.attributes_count, AttributeInfo))

SourceFileAttribute = Struct('SourceFileAttribute',
    UBInt16('sourcefile_index'))

FieldInfo = Struct('FieldInfo',
    UBInt16('access_flags'),
    UBInt16('name_index'),
    UBInt16('descriptor_index'),
    UBInt16('attributes_count'),
    MetaArray(lambda ctx: ctx.attributes_count, AttributeInfo))

MethodInfo = Struct('MethodInfo',
    UBInt16('access_flags'),
    UBInt16('name_index'),
    UBInt16('descriptor_index'),
    UBInt16('attributes_count'),
    MetaArray(lambda ctx: ctx.attributes_count, AttributeInfo))

def _constant_pool_count(obj, ctx):
    if not hasattr(ctx, '_constant_pool_count'):
        ctx._constant_pool_count = ctx.constant_pool_count-1

    ctx._constant_pool_count -= 1

    # Long and Double types take two spots..
    if obj.tag[9:] in ('Long', 'Double'):
        ctx._constant_pool_count -= 1

    return not ctx._constant_pool_count

_ClassFile = Struct('ClassFile',
    Magic('\xca\xfe\xba\xbe'),
    UBInt16('minor_version'),
    UBInt16('major_version'),
    UBInt16('constant_pool_count'),
    RepeatUntil(_constant_pool_count, ConstantPoolInfo),
    UBInt16('access_flags'),
    UBInt16('this_class_index'),
    UBInt16('super_class_index'),
    UBInt16('interfaces_count'),
    MetaArray(lambda ctx: ctx.interfaces_count, UBInt16('interfaces')),
    UBInt16('fields_count'),
    MetaArray(lambda ctx: ctx.fields_count, FieldInfo),
    UBInt16('methods_count'),
    MetaArray(lambda ctx: ctx.methods_count, MethodInfo),
    UBInt16('attributes_count'),
    MetaArray(lambda ctx: ctx.attributes_count, AttributeInfo))

class ClassFile:
    def __init__(self, data):
        """Parses a Java ClassFile"""
        # parse the main structures in the file
        self.root = _ClassFile.parse(data)

        # fix the constant pool, each entry that has the type Long or Double
        # needs to be appended with another element (we'll just set it to
        # None), because the specification is that these types take two
        # entries
        for idx, x in enumerate(self.root.ConstantPoolInfo):
            if x.tag[9:] in ('Long', 'Double'):
                # CONSTANT_None is a non-existant type.. made up to fix this
                # weird feature of the specification
                self.root.ConstantPoolInfo.insert(idx+1,
                    Container(tag='CONSTANT_None'))

            # we have to manually decode the strings in the Constant Pool
            # because Java encodes "\x00" as "\xc0\x80" in order to prevent
            # null-bytes in the strings, but this is an illegal encoding
            # according to the utf8 standards
            if x.tag[9:] == 'Utf8':
                x.value = x.value.replace('\xc0\x80', '\x00').decode('utf8')

        # resolves an entry from the Constant Pool
        def resolve_cp(obj, key, typ):
            idx = getattr(obj, key + '_index')
            val = self.root.ConstantPoolInfo[idx-1]
            assert val.tag[9:] == typ
            setattr(obj, key, val)

        # resolve ClassFile.this_class
        resolve_cp(self.root, 'this_class', 'Class')

        # resolve ClassFile.super_class
        if self.root.super_class_index:
            resolve_cp(self.root, 'super_class', 'Class')

        # resolve ClassFile.ConstantPoolInfo
        for x in self.root.ConstantPoolInfo:
            if x.tag[9:] == 'Class':
                resolve_cp(x, 'name', 'Utf8')
            elif x.tag[9:] in ('Fieldref', 'Methodref', 'InterfaceMethodref'):
                resolve_cp(x, 'class_', 'Class')
                resolve_cp(x, 'name_and_type', 'NameAndType')
            elif x.tag[9:] == 'String':
                resolve_cp(x, 'string', 'Utf8')
            elif x.tag[9:] == 'NameAndType':
                resolve_cp(x, 'name', 'Utf8')
                resolve_cp(x, 'descriptor', 'Utf8')

        # resolve ClassFile.MethodInfo
        for x in self.root.MethodInfo:
            resolve_cp(x, 'name', 'Utf8')
            resolve_cp(x, 'descriptor', 'Utf8')

            # resolve ClassFile.MethodInfo.AttributeInfo
            for y in x.AttributeInfo:
                resolve_cp(y, 'attribute_name', 'Utf8')

                # bit hardcoded, but oke
                if y.attribute_name.value == 'Code':
                    y.attribute = CodeAttribute.parse(y.info)

                    # resolve CodeAttribute.AttributeInfo
                    for z in y.attribute.AttributeInfo:
                        resolve_cp(z, 'attribute_name', 'Utf8')

                    # disassemble the entire function
                    y.instructions = [] ; offset = 0
                    while offset < len(y.attribute.code):
                        ins = java.disassemble(y.attribute.code, offset)
                        if ins.cp:
                            ins.cp = self.root.ConstantPoolInfo[ins.cp-1]
                            ins.rep += ' ; ' + _constant_pool_str(ins.cp)
                        offset += ins.length
                        y.instructions.append(ins)

        # resolve ClassFile.AttributeInfo
        for x in self.root.AttributeInfo:
            resolve_cp(x, 'attribute_name', 'Utf8')

    def __str__(self):
        return self.root.__str__()

if __name__ == '__main__':
    import sys, jsbeautifier
    a = ClassFile(file(sys.argv[1], 'rb').read())
    #print jsbeautifier.beautify(a.__str__())
    for x in a.root.MethodInfo:
        print 'function: %s, descriptor: %s' % (x.name.value,
            x.descriptor.value)
        for y in x.AttributeInfo:
            if y.attribute_name.value == 'Code':
                for z in y.instructions:
                    print str(z)
        print
