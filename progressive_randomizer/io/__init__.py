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

    def ping(self):
        return True
