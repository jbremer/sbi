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
    UBInt16('attribute_name_index'),
    UBInt32('attribute_length'),
    UBInt16('max_stack'),
    UBInt16('max_locals'),
    UBInt32('code_length'),
    MetaArray(lambda ctx: ctx.code_length, UBInt8('code')),
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
    UBInt16('attribute_name_index'),
    UBInt32('attribute_length'),
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

        cp = self.root.ConstantPoolInfo

        # resolve ClassFile.this_class
        self.root.this_class = cp[self.root.this_class_index-1]

        # resolve ClassFile.super_class
        if self.root.super_class_index:
            self.root.super_class = cp[self.root.super_class_index-1]

        # dictionary in order to resolve ClassFile.ConstantPoolInfo entries
        constant_pool_tags = {
            'Class': {'name_index': 'Utf8'},
            'Fieldref': {'class_index': 'Class',
                'name_and_type_index': 'NameAndType'},
            'Methodref': {'class_index': 'Class',
                'name_and_type_index': 'NameAndType'},
            'InterfaceMethodref': {'class_index': 'Class',
                'name_and_type_index': 'NameAndType'},
            'String': {'string_index': 'Utf8'},
            'NameAndType': {'name_index': 'Utf8', 'descriptor_index': 'Utf8'},
        }

        # resolve ClassFile.ConstantPoolInfo
        for x in self.root.ConstantPoolInfo:
            for key, tag in constant_pool_tags.get(x.tag[9:], {}).items():
                entry = cp[getattr(x, key)-1]
                assert entry.tag[9:] == tag
                setattr(x, key[:-6], entry)

        # resolve ClassFile.MethodInfo
        for x in self.root.MethodInfo:
            x.name = cp[x.name_index-1]
            x.descriptor = cp[x.descriptor_index-1]

            # resolve ClassFile.MethodInfo.AttributeInfo
            for y in x.AttributeInfo:
                y.attribute_name = cp[y.attribute_name_index-1]

        # resolve ClassFile.AttributeInfo
        for x in self.root.AttributeInfo:
            x.attribute_name = cp[x.attribute_name_index-1]

    def __str__(self):
        return self.root.__str__()

if __name__ == '__main__':
    import sys, jsbeautifier
    a = ClassFile(file(sys.argv[1], 'rb').read())
    print jsbeautifier.beautify(a.__str__())
