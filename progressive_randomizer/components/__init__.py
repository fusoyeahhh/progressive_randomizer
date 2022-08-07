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
    """
    The MemoryStructure object is the root of most of the component hierarchy.
    It is a generic container describing a contiguous stretch of byte data, having some metadata associated with it for tracking.
    """
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

        # less than and equals are minimum definitions needed for
        # total ordering
        def __lt__(self, right):
            return self.addr < right.addr

        def __eq__(self, right):
            return self.addr == right.addr

        def __iter__(self):
            """
            Iterate over the payload writes as if it were a linked list
            """
            this = self
            while this is not None:
                yield this
                this = this.link

        def chain(self, other):
            """
            Apppends one payload to another for chained writes. Payloads combined in this fashion act as linked lists.
            Ordering in the list is determined by payload order (by address)
            """
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
            Syntactic sugar to have the payload data be inserted into a byte stream.
            i.e.
            rom = struct @ b"\xff\xff" >> rom

            Note that this will do *all* writes starting from this link in the chain.
            """
            bindata = bytearray(bindata)
            for p in [*self]:
                r = p.addr + len(p.payload)
                bindata[p.addr:r] = p.payload
            return bytes(bindata)

    def as_tuple(self):
        """
        Get the beginning and end addresses of the structure.
        """
        return (self.addr, self.addr + self.length)

    def get_pointer_write(self, dst_addr, ptr_len):
        """
        Generates a new MemoryStructure, pointing to `dst_addr` which will write the address of this structure to that location.
        `ptr_len` is required to determine the size of the pointer to be written.
        """
        return MemoryStructure(dst_addr, ptr_len,
                               name=f"ptr_overwrite_{dst_addr}",
                               descr=f"Overwriting pointer to destination "
                                     f"at {dst_addr}, generated from {self.name}"), \
               self.addr.to_bytes(2, byteorder="little")

    def split(self, size, start=None):
        """
        Split a Memory structure into two, one starting at `start` with size `size`, and the remainder starting thereafter and running to the end of the block.
        NOTE: If `start` is not specified, then it defaults to the parent block address. If a `start` other than this address is provided, the lower part of the block not addressed will be "lost" in the split.
        The caller is responsible for tracking the "missing" stretch.
        """
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
        """
        Split this block into equally sized blocks with length `size`. The remainder after equal subdivision, if any, is returned as well.
        """
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

    def compare(self, other):
        """
        Basic interval comparison. Checks if two blocks are joinable, e.g., adjacent.
        FIXME: reconcile with use portion interval library
        """
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
        """
        Convenience operator to compare blocks.
        Note that equality is not handled, because of interval math.
        """
        return self.addr < other.addr

    def __add__(self, other):
        """
        If this and `other` are joinable (compare returns 1), then create a new block as their union.
        """
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
        """
        Syntactic sugar for `patch`.
        """
        return self.patch(bindata)

    def patch(self, data, bindata=None):
        """
        Create and deploy the `Payload` object. If `bindata` is provided, deploy immediately, else return the payload.
        """
        assert len(data) == self.length, f"0x{self.addr:x}+{self.length}"
        if bindata is None:
            return self.Payload(addr=self.addr, payload=data)
        return self.Payload(addr=self.addr, payload=data) >> bindata

    def copy_to(self, dst, bindata):
        log.debug(f"{self.name}: Copying 0x{self.length:x} bytes of data "
                  f"starting at 0x{self.addr:x} to {dst:x}")
        bindata[dst:dst + self.length] = bindata[self.addr:self.addr + self.length]
        return bindata

    def fill(self, bindata, fill_byte=0x0):
        log.debug(f"{self.name}: Filling 0x{self.length:x} bytes of data "
                  f"with {fill_byte:x} to 0x{self.addr:x}")
        bindata[self.addr:self.addr + self.length] = bytes(fill_byte) * self.length
        return bindata

    def read(self, bindata):
        """
        Base class io to get data.
        Child classes should override to provide component-specific output.
        """
        return self << bindata

    def __lshift__(self, bindata):
        """
        Raw byte reader.
        """
        assert 0 <= self.addr < len(bindata)
        log.debug(f"{self.name}: Reading 0x{self.length:x} bytes of data "
                  f"starting at 0x{self.addr:x}")
        return bytes(bindata[self.addr:self.addr+self.length])

    def deserialize(self, bindata):
        """
        Return a dictionary representation of this object with some metadata. Designed for use with JSON serialization.
        """
        return {**asdict(self),
                "_type": self.__class__.__name__,
                "_data": self.read(bindata)}

    @classmethod
    def chain_write(cls, writes):
        """
        Convenience method to generate several chained writes from a list.
        """
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
        """
        Looks for stretches of `min_length` or greater repetitions of `empty_byte` in `bindata`.
        Returns blocks describing these stretches.
        """
        addr, blocks = 0, []
        while addr < len(bindata):
            # Find the next position of an empty_byte, starting one
            # beyond the current address. If none is found, we're done.
            try:
                addr = st_addr = bindata.index(empty_byte, addr)
                addr += 1
            except ValueError:
                break
            # Count up the length of this stretch
            while addr < len(bindata) and bindata[addr] == empty_byte:
                addr += 1

            # If it meets the condition, define a new block
            blklen = addr - st_addr
            if blklen >= min_length:
                i = len(blocks)
                blocks.append(cls(addr=st_addr, length=blklen, name=f"free_space_{i}",
                                  descr=f"Free space: {blklen} bytes"))

            # move pointer to next byte for next search
            addr += 1

        return blocks


    @classmethod
    def serialize(cls, json_repr):
        """
        Helper method for serialization purposes.
        In coordination with `deserialize`, pops the "raw data" out of the JSON object and attempts to recreate the object.
        """
        _data = json_repr.pop("_data", None)
        assert isinstance(_data, bytes)
        return _data

    @classmethod
    def from_json(cls, json_repr):
        """
        Generate a new MemoryStructure from a JSON representation. See `serialize` and `deserialize`.
        TODO: use type information
        """
        _type = json_repr.pop("_type", None)
        _data = json_repr.pop("_data", None)
        return cls(**json_repr)

    # TODO: Need decompress / recompress routine from BC
    def map(self, fcn):
        pass

# TODO: should be datatable
class SNESHeader(MemoryStructure):
    """
    Structure representing a standard SNES header. It is used to identify the cartridge by Nintendo and manufacturers.
    NOTE: this is not the 0x200 byte "header" attached to the rom image, but an internal memory block at a specific address in all SNES images, holding metadata in a specific format.
    """
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
    """
    The `Registry` object is a container for MemoryStructures and related constructs.
    It also has a tagging mechanism to be able to retrieve related stuctures easily.
    """
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
        """
        Register a new `MemoryStructure` from metadata, potentially with `tags`.
        """
        if name in self._blocks:
            return self._blocks[name]

        block = MemoryStructure(addr, length, name, descr)
        self._blocks[name] = self._tree[block.as_tuple()] = block

        for tag in tags:
            self._tags[tag].add(name)

        return block

    def deregister_block(self, block):
        """
        Removes the block from the registry and its associated metadata, returning it.
        """
        self._tree.pop(block.as_tuple())
        for tag, blk_list in self._tags.items():
            blk_list.discard(block.name)

        return self._blocks.pop(block.name)

    def __str__(self):
        return pprint.pformat(self._blocks)

    def find_blks_from_addr(self, addr):
        """
        From a given address, find all blocks that contain this address and return them.
        """
        return {block.name: block for span, block in self._tree.items()
                                  if addr >= span[0] and addr < span[1]}

    def format_tags(self, tag, sort_by=None):
        """
        String formatting helper for tags, with optional `sort_by == {addr, name}`.
        """
        frmt = {name: self._blocks[name].addr for name in self._tags[tag]}
        frmt = frmt.items()
        if sort_by == "addr":
            frmt = sorted(frmt, key=lambda kv: kv[1])
        elif sort_by == "name":
            frmt = sorted(frmt, key=lambda kv: kv[0])
        return "\n".join([f"{hex(addr).ljust(8)}: {name}" for name, addr in frmt])

from .assembly import *
