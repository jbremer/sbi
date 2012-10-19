from construct import *
from pyasm2 import dalvik

def _uleb128(data):
    value = 0
    for x in xrange(5):
        ch = ord(data[x])
        value += (ch & 0x7f) << (7 * x)
        if (ch & 128) == 0:
            break
    return x + 1, value

def _uleb128p1(data):
    length, value = _uleb128(data)
    return length, value - 1

def _sleb128(data):
    length, value = _uleb128(data)
    if value & (2 ** (7 * length - 1)):
        value -= 2 ** (7 * length)
    return length, value
