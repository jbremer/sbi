from construct import *

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
            UBInt16('class_index'),
            UBInt16('name_and_type_index')),
        'CONSTANT_Methodref': Struct('CONSTANT_Methodref_info',
            UBInt16('class_index'),
            UBInt16('name_and_type_index')),
        'CONSTANT_InterfaceMethodref': Struct(
            'CONSTANT_InterfaceMethodref_info',
            UBInt16('class_index'),
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
            PascalString('value', length_field=UBInt16('length'),
                encoding='utf8')),
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

_ClassFile = Struct('ClassFile',
    Magic('\xca\xfe\xba\xbe'),
    UBInt16('minor_version'),
    UBInt16('major_version'),
    UBInt16('constant_pool_count'),
    MetaArray(lambda ctx: ctx.constant_pool_count-1, ConstantPoolInfo),
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
        # parse the main structures in the file
        self.root = _ClassFile.parse(data)

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
                resolve_cp(x, 'class', 'Class')
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

        # resolve ClassFile.AttributeInfo
        for x in self.root.AttributeInfo:
            resolve_cp(x, 'attribute_name', 'Utf8')

    def __str__(self):
        return self.root.__str__()

if __name__ == '__main__':
    import sys, jsbeautifier
    a = ClassFile(file(sys.argv[1], 'rb').read())
    print jsbeautifier.beautify(a.__str__())
