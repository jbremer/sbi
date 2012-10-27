from construct import *
from pyasm2 import dalvik

def _uleb128(data):
    value = 0
    for x in xrange(5):
        value += (data[x] & 127) << (7 * x)
        if not data[x] & 128:
            break
    if x == 4 and data[x] & 128 or value >= 2**32:
        raise Exception('Invalid uleb128 encoding')
    return x + 1, value

def _uleb128x(value):
    data = ''
    while value:
        data += chr(128 + (value & 127))
        value /= 128
    return data[:-1] + chr(128 ^ ord(data[-1]))

def _uleb128p1(data):
    length, value = _uleb128(data)
    return length, value - 1

def _uleb128p1x(value):
    return _uleb128(value + 1)

def _sleb128(data):
    length, value = _uleb128(data)
    if value & (2 ** (7 * length - 1)):
        value -= 2 ** (7 * length)
    return length, value

def _sleb128x(value):
    return _uleb128x(value if value >= 0 else 2**32 - value)

class _ULEB128(Adapter):
    def _decode(self, obj, context): return _uleb128(obj)[1]
    def _encode(self, obj, context): return _uleb128x(obj)

class _ULEB128p1(Adapter):
    def _decode(self, obj, context): return _uleb128p1(obj)[1]
    def _encode(self, obj, context): return _uleb128p1x(obj)

class _SLEB128(Adapter):
    def _decode(self, obj, context): return _sleb128(obj)[1]
    def _encode(self, obj, context): return _sleb128x(obj)

def _LEB128(name, typ):
    return Embed(Struct(None,
        RepeatUntil(lambda obj, ctx: not obj & 128, Byte(name + '_bytes')),
        typ(Value(name, lambda ctx: getattr(ctx, name + '_bytes')))))

# adapters for ULEB128, SLEB128, ULEB128p1
def ULEB128(name): return _LEB128(name, _ULEB128)
def SLEB128(name): return _LEB128(name, _SLEB128)
def ULEB128p1(name): return _LEB128(name, _ULEB128p1)

def _type_identifier_list(name, typ='_ids'):
    return Embed(Struct(None,
        ULInt32('%s%s_size' % (name, typ)),
        ULInt32('%s%s_off' % (name, typ))))

header_item = Struct('header_item',
    Magic('dex\n035\x00'),
    ULInt32('checksum'),
    Bytes('signature', 20),
    ULInt32('file_size'),
    ULInt32('header_size'),
    Magic('\x78\x56\x34\x12'),
    ULInt32('link_size'),
    ULInt32('link_off'),
    ULInt32('map_off'),
    _type_identifier_list('string'),
    _type_identifier_list('type'),
    _type_identifier_list('proto'),
    _type_identifier_list('field'),
    _type_identifier_list('method'),
    _type_identifier_list('class', '_defs'),
    _type_identifier_list('data', ''))

def mutf8_string(name):
    return Embed(Struct(None,
        CString('%s_bytes' % name),
        Value(name, lambda ctx: getattr(ctx,
            '%s_bytes' % name).replace('\xc0\x80', '\x00'))))

_signed_int_types = {1: SLInt8, 2: SLInt16, 4: SLInt32, 8: SLInt64}
_unsigned_int_types = {1: ULInt8, 2: ULInt16, 4: ULInt32, 8: ULInt64}
_float_types = {4: LFloat32, 8: LFloat64}

def _sign_extend(value, length):
    return value.rjust(length, '\xff' if ord(value[0]) & 0x80 else '\x00')

def _signed_int(name, length):
    return Embed(Struct(None,
        MetaField('%s_bytes' % name, lambda ctx: ctx.value_arg+1),
        Value(name, lambda ctx: _unsigned_int_types[length](None).parse(
            _sign_extend(getattr(ctx, '%s_bytes' % name), length)))))

def _unsigned_int(name, length):
    return Embed(Struct(None,
        MetaField('%s_bytes' % name, lambda ctx: ctx.value_arg+1),
        Value(name, lambda ctx: _unsigned_int_types[length](None).parse(
            getattr(ctx, '%s_bytes' % name).rjust(length, '\x00')))))

def _float(name, size):
    return Embed(Struct(None,
        MetaField('%s_bytes' % name, lambda ctx: ctx.value_arg+1),
        Value(name, lambda ctx: _float_types[length](None).parse(
            getattr(ctx, '%s_bytes' % name).ljust(length, '\x00')))))

encoded_value = Struct('encoded_value',
    Embed(BitStruct(None,
        BitField('value_arg', 3),
        Enum(BitField('value_type', 5),
            VALUE_BYTE = 0x00,
            VALUE_SHORT = 0x02,
            VALUE_CHAR = 0x03,
            VALUE_INT = 0x04,
            VALUE_LONG = 0x06,
            VALUE_FLOAT = 0x10,
            VALUE_DOUBLE = 0x11,
            VALUE_STRING = 0x17,
            VALUE_TYPE = 0x18,
            VALUE_FIELD = 0x19,
            VALUE_METHOD = 0x1a,
            VALUE_ENUM = 0x1b,
            VALUE_ARRAY = 0x1c,
            VALUE_ANNOTATION = 0x1d,
            VALUE_NULL = 0x1e,
            VALUE_BOOLEAN = 0x1f
    ))),
    Embed(Switch(None, lambda ctx: ctx.value_type, {
        'VALUE_BYTE': _signed_int('value', 1),
        'VALUE_SHORT': _signed_int('value', 2),
        'VALUE_CHAR': _unsigned_int('value', 2),
        'VALUE_INT': _signed_int('value', 4),
        'VALUE_LONG': _signed_int('value', 8),
        'VALUE_FLOAT': _float('value', 4),
        'VALUE_DOUBLE': _float('value', 8),
        'VALUE_STRING': _unsigned_int('index', 4),
        'VALUE_TYPE': _unsigned_int('index', 4),
        'VALUE_FIELD': _unsigned_int('index', 4),
        'VALUE_METHOD': _unsigned_int('index', 4),
        'VALUE_ENUM': _unsigned_int('index', 4),
        'VALUE_ARRAY': Embed(Value(None, lambda ctx: encoded_array)),
        'VALUE_ANNOTATION': Embed(Value(None,
            lambda ctx: encoded_annotation)),
        'VALUE_NULL': Pass,
        'VALUE_BOOLEAN': Value('value', lambda ctx: IfThenElse(None,
            lambda ctx: ctx.value_arg, True, False)),
    })))

encoded_array = Struct('encoded_array',
    ULEB128('size'),
    MetaArray(lambda ctx: ctx.size, Rename('values', encoded_value)))

annotation_element = Struct('annotation_element',
    ULEB128('name_idx'),
    Rename('value', encoded_value))

encoded_annotation = Struct('encoded_annotation',
    ULEB128('type_idx'),
    ULEB128('size'),
    MetaArray(lambda ctx: ctx.size, Rename('elements', annotation_element)))

string_data_item = Struct('string_data_item',
    ULEB128('utf16_size'),
    mutf8_string('data'))

string_id_item = Struct('string_id_item',
    ULInt32('string_data_off'),
    Pointer(lambda ctx: ctx.string_data_off, string_data_item))

type_id_item = Struct('type_id_item',
    ULInt32('descriptor_idx'))

proto_id_item = Struct('proto_id_item',
    ULInt32('shorty_idx'),
    ULInt32('return_type_idx'),
    ULInt32('parameters_off'))

field_id_item = Struct('field_id_item',
    ULInt16('class_idx'),
    ULInt16('type_idx'),
    ULInt32('name_idx'))

method_id_item = Struct('method_id_item',
    ULInt16('class_idx'),
    ULInt16('proto_idx'),
    ULInt32('name_idx'))

encoded_field = Struct('encoded_field',
    ULEB128('field_idx_diff'),
    ULEB128('access_flags'))

encoded_method = Struct('encoded_method',
    ULEB128('method_idx_diff'),
    ULEB128('access_flags'),
    ULEB128('code_off'))

class_data_item = Struct('class_data_item',
    ULEB128('static_fields_size'),
    ULEB128('instance_fields_size'),
    ULEB128('direct_methods_size'),
    ULEB128('virtual_methods_size'),
    Rename('static_fields', MetaArray(lambda ctx: ctx.static_fields_size,
        encoded_field)),
    Rename('instance_fields', MetaArray(lambda ctx: ctx.instance_fields_size,
        encoded_field)),
    Rename('direct_methods', MetaArray(lambda ctx: ctx.direct_methods_size,
        encoded_method)),
    Rename('virtual_methods', MetaArray(lambda ctx: ctx.virtual_methods_size,
        encoded_method)))

class_def_item = Struct('class_def_item',
    ULInt32('class_idx'),
    ULInt32('access_flags'),
    ULInt32('superclass_idx'),
    ULInt32('interfaces_off'),
    ULInt32('source_file_idx'),
    ULInt32('annotations_off'),
    ULInt32('class_data_off'),
    Pointer(lambda ctx: ctx.class_data_off, class_data_item),
    ULInt32('static_values_off'))

type_item = Struct('type_item',
    ULInt16('type_idx'))

type_list = Struct('type_list',
    ULInt32('size'),
    MetaArray(lambda ctx: ctx.size, type_item))

try_item = Struct('try_item',
    ULInt32('start_addr'),
    ULInt16('insn_count'),
    ULInt16('handler_off'))

encoded_type_addr_pair = Struct('encoded_type_addr_pair',
    ULEB128('type_idx'),
    ULEB128('addr'))

encoded_catch_handler = Struct('encoded_catch_handler',
    SLEB128('size'),
    MetaArray(lambda ctx: abs(ctx.size), encoded_type_addr_pair),
    If(lambda ctx: ctx.size, ULEB128('catch_all_addr')))

encoded_catch_handler_list = Struct('encoded_catch_handler_list',
    SLEB128('size'),
    MetaArray(lambda ctx: abs(ctx.size), encoded_catch_handler),
    If(lambda ctx: ctx.size, ULEB128('catch_all_addr')))

code_item = Struct('code_item',
    ULInt16('registers_size'),
    ULInt16('ins_size'),
    ULInt16('outs_size'),
    ULInt16('tries_size'),
    ULInt32('debug_info_off'),
    ULInt32('insn_size'),
    MetaArray(lambda ctx: ctx.insn_size, ULInt16('insns')),
    Aligned(MetaArray(lambda ctx: ctx.tries_size, try_item)),
    If(lambda ctx: ctx.tries_size, encoded_catch_handler_list))

field_annotation = Struct('field_annotation',
    ULInt32('field_idx'),
    ULInt32('annotations_off'))

method_annotation = Struct('method_annotation',
    ULInt32('method_idx'),
    ULInt32('annotations_off'))

parameter_annotation = Struct('parameter_annotation',
    ULInt32('method_idx'),
    ULInt32('annotations_off'))

annotations_directory_item = Struct('annotations_directory_item',
    ULInt32('class_annotations_off'),
    ULInt32('fields_size'),
    ULInt32('annotated_methods_size'),
    ULInt32('annotated_parameters_size'),
    MetaArray(lambda ctx: ctx.fields_size, field_annotation),
    MetaArray(lambda ctx: ctx.annotated_methods_size, method_annotation),
    MetaArray(lambda ctx: ctx.annotated_parameters_size,
        parameter_annotation))

annotation_set_ref_item = Struct('annotation_set_ref_item',
    ULInt32('annotations_off'))

annotation_set_ref_list = Struct('annotation_set_ref_list',
    ULInt32('size'),
    MetaArray(lambda ctx: ctx.size, annotation_set_ref_item))

annotation_off_item = Struct('annotation_off_item',
    ULInt32('annotation_off'))

annotation_set_item = Struct('annotation_set_item',
    ULInt32('size'),
    MetaArray(lambda ctx: ctx.size, annotation_off_item))

annotation_item = Struct('annotation_item',
    Enum(Byte('visibility'),
        VISIBILITY_BUILD = 0,
        VISIBILITY_RUNTIME = 1,
        VISIBILITY_SYSTEM = 2),
    encoded_annotation)

encoded_array_item = Struct('encoded_array_item',
    encoded_array)

map_item = Struct('map_item',
    Enum(ULInt16('type'),
        TYPE_HEADER_ITEM = 0x0000,
        TYPE_STRING_ID_ITEM = 0x0001,
        TYPE_TYPE_ID_ITEM = 0x0002,
        TYPE_PROTO_ID_ITEM = 0x0003,
        TYPE_FIELD_ID_ITEM = 0x0004,
        TYPE_METHOD_ID_ITEM = 0x0005,
        TYPE_CLASS_DEF_ITEM = 0x0006,
        TYPE_MAP_LIST = 0x1000,
        TYPE_TYPE_LIST = 0x1001,
        TYPE_ANNOTATION_SET_REF_LIST = 0x1002,
        TYPE_ANNOTATION_SET_ITEM = 0x1003,
        TYPE_CLASS_DATA_ITEM = 0x2000,
        TYPE_CODE_ITEM = 0x2001,
        TYPE_STRING_DATA_ITEM = 0x2002,
        TYPE_DEBUG_INFO_ITEM = 0x2003,
        TYPE_ANNOTATION_ITEM = 0x2004,
        TYPE_ENCODED_ARRAY_ITEM = 0x2005,
        TYPE_ANNOTATIONS_DIRECTORY_ITEM = 0x2006),
    ULInt16('unused'),
    ULInt32('size'),
    ULInt32('offset'))

map_list = Struct('map_list',
    ULInt32('size'),
    MetaArray(lambda ctx: ctx.size, map_item))

ACC_PUBLIC = 0x1
ACC_PRIVATE = 0x2
ACC_PROTECTED = 0x4
ACC_STATIC = 0x8
ACC_FINAL = 0x10
ACC_SYNCHRONIZED = 0x20
ACC_VOLATILE = 0x40
ACC_BRIDGE = 0x40
ACC_TRANSIENT = 0x80
ACC_VARARGS = 0x80
ACC_NATIVE = 0x100
ACC_INTERFACE = 0x200
ACC_ABSTRACT = 0x400
ACC_STRICT = 0x800
ACC_SYNTHETIC = 0x1000
ACC_ANNOTATION = 0x2000
ACC_ENUM = 0x4000
ACC_CONSTRUCTOR = 0x10000
ACC_DECLARED_SYNCHRONIZED = 0x20000

NO_INDEX = 0xffffffff

def id_section(off, size, item):
    return Pointer(lambda ctx: getattr(ctx.header, off),
        MetaArray(lambda ctx: getattr(ctx.header, size), item))

_DexFile = Struct('DexFile',
    Rename('header', header_item),

    id_section('string_ids_off', 'string_ids_size', string_id_item),
    id_section('type_ids_off', 'type_ids_size', type_id_item),
    id_section('proto_ids_off', 'proto_ids_size', proto_id_item),
    id_section('field_ids_off', 'field_ids_size', field_id_item),
    id_section('method_ids_off', 'method_ids_size', method_id_item),
    id_section('class_defs_off', 'class_defs_size', class_def_item),

    OnDemand(Pointer(lambda ctx: ctx.header.data_off,
        MetaField('data', lambda ctx: ctx.header.data_size))))

class DexFile:
    def __init__(self, data):
        self.root = _DexFile.parse(data)

        def _str_(idx):
            return self.root.string_id_item[idx]

        def _proto_(idx):
            return self.root.proto_id_item[idx]

        def _desc_(idx):
            if idx == NO_INDEX:
                return 'Ljava/lang/Object;'
            return self.root.type_id_item[idx]

        # simplify string_id_item
        for idx, x in enumerate(self.root.string_id_item):
            self.root.string_id_item[idx] = x.string_data_item.data

        # resolve & simplify type_id_item
        for idx, x in enumerate(self.root.type_id_item):
            self.root.type_id_item[idx] = _str_(x.descriptor_idx)

        # resolve proto_id_item
        for x in self.root.proto_id_item:
            x.shorty = _str_(x.shorty_idx)
            x.return_type = _desc_(x.return_type_idx)

        # resolve field_id_items
        for x in self.root.field_id_item:
            x.class_ = _desc_(x.class_idx)
            x.type_ = _desc_(x.type_idx)
            x.name = _str_(x.name_idx)

        # resolve method_id_items
        for x in self.root.method_id_item:
            x.class_ = _desc_(x.class_idx)
            x.proto = _proto_(x.proto_idx)
            x.name = _str_(x.name_idx)

        # resolve class_def_item
        for x in self.root.class_def_item:
            x.class_ = _desc_(x.class_idx)
            x.superclass = _desc_(x.superclass_idx)
            x.source_file = _str_(x.source_file_idx)

    def __str__(self):
        return self.root.__str__()

if __name__ == '__main__':
    import sys, jsbeautifier
    if len(sys.argv) < 2:
        print 'Usage: %s <dex-file>' % sys.argv[0]
        exit(0)

    b = DexFile(open(sys.argv[1], 'rb').read())
    a = b.root
    print jsbeautifier.beautify(a.__str__())
