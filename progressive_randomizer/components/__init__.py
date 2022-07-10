import pprint
import math
import bisect
from functools import total_ordering
from collections import defaultdict

from dataclasses import dataclass, asdict

import logging
log = logging.getLogger()

@dataclass(repr=True, init=True)
class MemoryStructure:
    addr: int
    length: int
    name: str
    descr: str

    @total_ordering
    @dataclass
    class Payload:
        """
        The Payload class is utility object which tracks where and what data should be written from a "patch".
        It has some syntactic sugar (the >> method) to accomplish the actual execution of splicing in data.
        It also orderable (by address) and can be treated as a linked list for multiple non-overlapping writes.
        No check is made that the writes do not overlap (use a WriteQueue for this), so this could introduce bugs if not carefully checked.
        """
        addr: int
        payload: bytes
        link: object = None

        def __lt__(self, right):
            return self.addr < right.addr

        def __eq__(self, right):
            return self.addr == right.addr

        def __iter__(self):
            this = self
            while this is not None:
                yield this
                this = this.link

        def chain(self, other):
            pchain = [*self]
            # NOTE: assumes we're keeping things in sorted order
            # from the beginning
            idx = bisect.bisect_right(pchain, other)
            other.link = pchain[idx] if idx < len(pchain) else None
            if idx > 0:
                pchain[idx - 1].link = other
                return pchain[0]
            # if idx = 0 other is the new head of the chain
            return other

        def __rshift__(self, bindata):
            """
            # rom = struct @ b"\xff\xff" >> rom
            """
            bindata = bytearray(bindata)
            for p in [*self]:
                r = p.addr + len(p.payload)
                bindata[p.addr:r] = p.payload
            return bytes(bindata)

    def as_tuple(self):
        return (self.addr, self.addr + self.length)

    def get_pointer_write(self, dst_addr, ptr_len):
        return MemoryStructure(dst_addr, ptr_len,
                               name=f"ptr_overwrite_{dst_addr}",
                               descr=f"Overwriting pointer to destination "
                                     f"at {dst_addr}, generated from {self.name}"), \
               self.addr.to_bytes(2, byteorder="little")

    def split(self, size, start=None):
        start = start or self.addr
        return (
            MemoryStructure(addr=start, length=size,
                            name=self.name + "_split_1",
                            descr=f"Split from {self.descr}"),
            MemoryStructure(addr=start + size,
                            length=self.length - size,
                            name=self.name + "_split_2",
                            descr=f"Split from {self.descr}")
        )

    def subdivide(self, size):
        nsplit = math.ceil(self.length / size)
        blocks = list(self.split(size))
        for i in range(2, nsplit):
            blk1, blk2 = blocks.pop().split(size)
            blk1.name = self.name + f"_split_{i}"
            blk1.descr = f"Split from {self.descr}"
            blocks.extend([blk1, blk2])

        blk2 = blocks.pop()
        if blk2.length > 0:
            blk2.name = self.name + f"_split_{nsplit}"
            blk2.descr = f"Split from {self.descr}"
            blocks.append(blk2)
        return blocks

    # FIXME: reconcile with use portion interval library
    def compare(self, other):
        lower, upper = self, other
        if self.addr > other.addr:
            lower, upper = upper, lower

        if lower.addr + lower.length == upper.addr:
            # connectable
            return 1

        if lower.addr + lower.length <= upper.addr:
            # disjoint
            return 0

        # Overlapping in some currently non-usable way
        return -1

    def __lt__(self, other):
        return self.addr < other.addr

    def __add__(self, other):
        if self.compare(other) != 1:
            raise ValueError(f"{self} + {other} are not disjoint and adjacent.")
        lower, upper = min(self, other), max(self, other)
        return MemoryStructure(
            addr=lower.addr,
            length=lower.length + upper.length,
            name=lower.name + "_and_" + upper.name,
            descr=f"Union of {lower.name} and {upper.name}"
        )

    def __matmul__(self, bindata):
        return self.patch(bindata)

    def patch(self, data, bindata=None):
        assert len(data) == self.length, f"0x{self.addr:x}+{self.length}"
        if bindata is None:
            return self.Payload(addr=self.addr, payload=data)
        return self.Payload(addr=self.addr, payload=data) >> bindata

    # syntactic sugar for read
    def __lshift__(self, bindata):
        return self.read(bindata)

    def read(self, bindata):
        assert 0 <= self.addr < len(bindata)
        log.debug(f"Reading 0x{self.length:x} bytes of data "
                  f"starting at 0x{self.addr:x}")
        return bytes(bindata[self.addr:self.addr+self.length])

    def deserialize(self, bindata):
        return {**asdict(self),
                "_type": self.__class__.__name__,
                "_data": self.read(bindata)}

    @classmethod
    def chain_write(cls, writes):
        payloads = []
        for addr, data in writes.items():
            blk = cls(addr=addr, length=len(data),
                      name=f"chain_writer_{addr:x}",
                      descr=f"I/O layer for chain writer @ {addr:x}")
            payloads.append(blk @ data)

        payloads = sorted(payloads)
        for p1, p2 in zip(payloads[:-1], payloads[1:]):
            p1.chain(p2)
        return payloads[0]

    @classmethod
    def find_free_space(cls, bindata, min_length=16, empty_byte=0xFF):
        addr = 0
        blocks = []
        while addr < len(bindata):
            try:
                addr = st_addr = bindata.index(empty_byte, addr)
                addr += 1
            except ValueError:
                break
            while addr < len(bindata) and bindata[addr] == empty_byte:
                addr += 1

            blklen = addr - st_addr
            if blklen >= min_length:
                i = len(blocks)
                blocks.append(cls(addr=st_addr, length=blklen, name=f"free_space_{i}",
                                  descr=f"Free space: {blklen} bytes"))

            addr += 1

        return blocks


    @classmethod
    def serialize(cls, json_repr):
        _data = json_repr.pop("_data", None)
        assert isinstance(_data, bytes)
        return _data

    @classmethod
    def from_json(cls, json_repr):
        # TODO: use type information
        _type = json_repr.pop("_type", None)
        _data = json_repr.pop("_data", None)
        return cls(**json_repr)

    # TODO: Need decompress / recompress routine from BC
    def map(self, fcn):
        pass

# TODO: should be datatable
class SNESHeader(MemoryStructure):
    def __init__(self):
        self._unpack_schema = self._generate_schema()

    # FIXME: move to be used as a decorator
    # but I think it has to be a class in order to pick up a header_map arg
    @classmethod
    def _generate_schema(cls, header_map="etc/snes_header_map.csv"):
        with open(header_map, "r") as fin:
            return {int(addr, base=16): (int(size), descr)
                    for addr, size, descr in csv.reader(fin.readlines())}

    def read(self, bindata):
        decode_tbl = {}
        for addr, (size, descr) in self._unpack_schema.items():
            decode_tbl[descr] = \
                MemoryStructure(addr, size, descr, descr) << bindata
        return decode_tbl

class Registry:
    @classmethod
    def copy(cls, reg):
        cpy = cls()
        cpy._blocks = reg._blocks
        cpy._tree = reg._tree
        cpy._tags = reg._tags
        return cpy

    def __init__(self):
        self._blocks = {}
        # TODO: make into interval tree
        self._tree = {}
        self._tags = defaultdict(set)

    def register_block(self, addr, length, name, descr, tags=set()):
        if name in self._blocks:
            return self._blocks[name]

        block = MemoryStructure(addr, length, name, descr)
        self._blocks[name] = self._tree[block.as_tuple()] = block

        for tag in tags:
            self._tags[tag].add(name)

        return block

    def deregister_block(self, block):
        self._tree.pop(block.as_tuple())
        for tag, blk_list in self._tags.items():
            blk_list.remove(block.name)

        return self._blocks.pop(block.name)

    def __str__(self):
        return pprint.pformat(self._blocks)

    def find_blks_from_addr(self, addr):
        return {block.name: block for span, block in self._tree.items()
                                  if addr >= span[0] and addr < span[1]}

    def format_tags(self, tag, sort_by=None):
        frmt = {name: self._blocks[name].addr for name in self._tags[tag]}
        frmt = frmt.items()
        if sort_by == "addr":
            frmt = sorted(frmt, key=lambda kv: kv[1])
        elif sort_by == "name":
            frmt = sorted(frmt, key=lambda kv: kv[0])
        return "\n".join([f"{hex(addr).ljust(8)}: {name}" for name, addr in frmt])

from .assembly import *
