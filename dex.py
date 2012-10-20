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
