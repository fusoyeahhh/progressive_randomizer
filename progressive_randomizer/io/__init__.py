import json
from dataclasses import asdict
from ..utils import ByteUtils

class DataclassJSONEncoder(json.JSONEncoder):
    def default(self, o):
        try:
            return super().default(0)
        except TypeError:
            return asdict(o)

class BaseEmuIO:
    def __init__(self):
        pass

    def _send_msg(self, msg):
        pass

    def _recv_msg(self, msg):
        pass

    def read_memory(self, st, en):
        pass

    def read_memory_as(self, st, en=None, width=None, unpack=True):
        data = self.read_memory(st, en or st + 1)
        if len(data) == 1 and unpack:
            return data[0]

        if width == 1:
            return ByteUtils.as_uint_8(data, unpack)
        elif width == 2:
            return ByteUtils.as_uint_16(data, unpack)
        elif width is not None:
            return ByteUtils.as_uint_arb(data, width, unpack)

        return data

    def write_memory(self, st, val):
        pass

    def read_rom(self, st, en):
        pass

    def write_rom(self, st, en, val):
        pass

    def ping(self, visual=False):
        return True

class MemRead:

    @classmethod
    def _to_int(cls, value, byteorder="little"):
        return int.from_bytes(value, byteorder=byteorder)

    def _to_xy(cls, value):
        return (int.from_bytes(value[0][0], byteorder="little"),
                int.from_bytes(value[1][0], byteorder="little"))

    def __init__(self, addr, length=1, width=None, cls=None):
        self._cache = None
        self._addr = addr
        self._length = length
        self._width = width
        self._changed = True
        self._cls = cls

    def __get__(self, instance, owner):
        mem = instance.read_ram(self._addr,
                                self._addr + self._length,
                                width=self._width)
        if self._cls is not None:
            mem = self._cls(mem)
        self._changed = self._cache != mem
        self._cache = mem
        return self._cache
        
    def changed(self):
        return self._changed

class MemReadWrite(MemRead):
    def __set__(self, instance, value):
        instance.write_memory(self._addr, value)

    def to_bytes(self, value):
        return int.to_bytes(self._length, byteorder="little")

