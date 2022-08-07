"""
Generic randomization tasks.
"""
import json

import logging
log = logging.getLogger()

from ..components import MemoryStructure, AssemblyObject
from ..utils import (
    Utils,
    ips_patcher
)

class RandomizationTask:
    def __init__(self, memblk):
        self._memblk = memblk

    def __str__(self):
        return f"{self.__class__.__name__} -> {self._memblk}"

    def __call__(self, bindata):
        # FIXME: we have to ensure this binary data, because our read method returns
        # different things
        # TODO: we need to have a base "raw" read and then deserialization / dereferencing
        try:
            return bytes(self._memblk << bindata, encoding='utf8')
        except TypeError:
            pass
        return self._memblk << bindata

    def __rshift__(self, bindata):
        data = self(bindata)
        return self._memblk @ bytes(data) >> bindata

    # Determines whether two randomizations could collide
    def __and__(self, rhs):
        import portion
        lhs = portion.closedopen(*self.affected_blocks())
        rhs = portion.closedopen(*rhs.affected_blocks())
        return lhs.intersection(rhs) != portion.empty()

    def diff(self, bindata):
        orig = self._memblk << bindata
        new = self(bindata)

        return Utils.bindiff(new, orig, self._memblk.addr)

    def affected_blocks(self):
        return (self._memblk.addr, self._memblk.addr + self._memblk.length)

    def to_ips(self, bindata):
        max_len = 0xFFFF
        start = self._memblk.addr

        to_write = self(bindata)
        buffer = b""
        while len(to_write) > 0:
            len_to_write = min(max_len, len(to_write))
            start += len_to_write
            buffer += start.to_bytes(3) + len_to_write.to_bytes(2) + to_write[:len_to_write]
            to_write = to_write[len_to_write:]

        return buffer

class WriteBytes(RandomizationTask):
    def __init__(self, memblk, data):
        super().__init__(memblk)
        assert len(data) == memblk.length, f"{memblk}, {len(data)}"
        self._data = data

    def __call__(self, bindata):
        log.debug(f"Bytes: writing {len(self._data)} bytes to ROM")
        return self._data

    def __str__(self):
        return f"{self.__class__.__name__} -> Write {len(self._data)} bytes to {self._memblk}"

    def __add__(self, other):
        lower, upper = min(self._memblk, other._memblk), \
                       max(self._memblk, other._memblk)
        try:
            new_blk = lower + upper
        except ValueError:
            raise ValueError("Incompatible patches, cannot add non-adjacent "
                             "or overlapping patches.")

        lower = self._data if self._memblk == lower else other._data
        upper = self._data if self._memblk == upper else other._data
        return WriteBytes(new_blk, lower + upper)

class ExpandImage(RandomizationTask):
    def __init__(self, memblk, size):
        super().__init__(memblk)
        self._size = size

    def __str__(self):
        return f"{self.__class__.__name__} -> Append {len(self._size)} bytes to {self._memblk}"

    def __call__(self, bindata):
        log.debug(f"Expand: appending {self._size} bytes to ROM")
        return bindata + b"\x00" * self._size

class ShuffleBytes(RandomizationTask):
    def __call__(self, bindata):
        data = super().__call__(bindata)
        log.debug(f"ShuffleBytes: read {len(data)} bytes from ROM, shuffling...")
        from ..utils.randomization import shuffle
        return bytes(shuffle(data))

class PatchFromJSON(RandomizationTask):
    def __init__(self, memblk, jsonf):
        super().__init__(memblk)
        with open(jsonf, "r") as fin:
            self._data = json.load(fin)

    def __call__(self, bindata):
        return self._memblk.serialize(self._data)

class PatchFromIPS(RandomizationTask, ips_patcher.IPSReader):
    def __init__(self, ipsfile, memblk=None):
        super().__init__(memblk)
        super(RandomizationTask, self).__init__(ipsfile)

    def __str__(self):
        stats = "\n".join([f"\t0x{a:x} -> {d}" for a, d in self.contents.items()])
        if stats:
            stats = "\n" + stats
        return f"{self.__class__.__name__} ->" + stats

    # FIXME: this expects to return a blob of binary data
    def __call__(self, bindata):
        return self.contents

    def __rshift__(self, bindata):
        patch_writer = MemoryStructure.chain_write(self.contents)
        return patch_writer >> bindata

    def affected_blocks(self):
        # FIXME: this will cause unnecessary conflicts
        min_addr = min(self.contents)
        max_addr = max([a + len(d) for a, d in self.contents.items()])
        return (min_addr, max_addr)

TASKS = {
    "shuffle_bytes": ShuffleBytes,
    "write_bytes": WriteBytes,
    "patch_from_json": PatchFromJSON
}