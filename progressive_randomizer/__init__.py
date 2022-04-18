import pprint

import csv
import random
import re

from dataclasses import dataclass

import logging
log = logging.getLogger()

class WriteQueue:
    def __init__(self, seed=0):
        self._write_queue = []
        self._history = {}

        # TODO: make this consistent
        self._seed = seed

    def flush(self, bindata):
        # FIXME: use decompile / compile, e.g., JSON schematic
        while len(self._write_queue) > 0:
            patcher = self._write_queue.pop(0)
            # TODO: detect collisions (has to be done in rando)
            # TODO: need a way to chain splice
            bindata = patcher >> bindata
            # TODO: annotate history
        return bindata

    def queue_write(self, patcher):
        self._write_queue.append(patcher)

@dataclass(repr=True, init=True)
class MemoryStructure:
    addr: int
    length: int
    name: str
    descr: str

    # syntactic sugar for write
    @dataclass
    class Payload:
        addr: int
        payload: bytes

        def __rshift__(self, bindata):
            """
            # rom = struct | b"\xff\xff" >> rom
            """
            left = bindata[:self.addr]
            right = bindata[self.addr + len(self.payload):]
            return bytes(left + self.payload + right)

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

    # TODO: Need decompress / recompress routine from BC
    def map(self, fcn):
        pass

# TODO: should be datatable
class SNESHeader(MemoryStructure):
    def __init__(self):
        self._unpack_schema = self._generate_schema()

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

class AssemblyObject(MemoryStructure):
    OP_REF = {}
    with open("etc/snes_op_code_ref.csv", "r") as fin:
        OP_REF = {int(item[3], base=16): (item[0], int(item[-2][0]))
                  for item in csv.reader(fin.readlines())}

    @classmethod
    def _disassemble(cls, prg_bytes):
        disassembly = []
        prg_bytes = [*prg_bytes]
        while len(prg_bytes) > 0:
            op = prg_bytes.pop(0)
            oplen = cls.OP_REF[op][-1]
            args, prg_bytes = prg_bytes[:oplen], prg_bytes[oplen:]
            disassembly.append([op, args])

        return disassembly

    def annotate(self, bindata):
        prg = ""
        pad = max([len(op[0]) for op in self.OP_REF.values()])
        for op, args in self._disassemble(self.read(bindata)):
            op_name = self.OP_REF[op][0]
            args = " ".join([str(arg).rjust(3) for arg in args])
            prg += f"{op_name.ljust(pad)} {args}\n"
        return prg

    def identify_pointers(self, bindata):
        pass

class Registry:
    def __init__(self):
        self._blocks = {}
        # TODO: make into interval tree
        self._tree = {}
        from collections import defaultdict
        self._tags = defaultdict(set)

    def register_block(self, addr, length, name, descr, tags=set()):
        if name in self._blocks:
            return self._blocks[name]

        block = MemoryStructure(addr, length, name, descr)
        span = (addr, addr + length)
        self._blocks[name] = self._tree[span] = block

        for tag in tags:
            self._tags[tag].add(name)

        return block

    def __str__(self):
        return pprint.pformat(self._blocks)

class StaticRandomizer:
    def __init__(self):
        self._reg = Registry()

    def __getitem__(self, item):
        if not isinstance(item, tuple):
            item = (item,)

        if item[0] in self._reg._blocks:
            return self._reg._blocks[item[0]]
        elif len(item) != 3:
            raise KeyError(f"Block key {item[0]} not found in registry.")

        beg, end = item[1:]
        name = f"0x{beg:x}_0x{end:x}"
        descr = f"Autogenerated alias for block {name}"

        return self._reg.register_block(beg=beg, length=end - beg,
                                        name=name, descr=descr)

    @classmethod
    def from_rom_map(cls, rommap, tags=set(), apply_offset=0):
        reg = Registry()
        with open(rommap, "r", encoding="utf-8") as fin:
            for beg, end, descr in csv.reader(fin.readlines()):
                beg = int(beg, base=16) - apply_offset
                end = int(end, base=16) - apply_offset + 1

                # make a shorter memorable name
                name = re.sub(r'\([^()]*\)', "", descr)
                name = "_".join([word[0] + re.sub(r"[aeiou]", "", word[1:], flags=re.I)[:4]
                                 for word in name.lower().strip().split(" ")])
                name = re.sub(r"[/']", "_", name, flags=re.I)
                _tags = set(descr.lower().split()) & tags

                if name in reg._blocks:
                    i = 0
                    while name + str(i) in reg._blocks:
                        i += 1
                    name = name + str(i)

                reg.register_block(beg, end - beg, name, descr, _tags)

        return reg

    def decompile(self, bindata, fill_gaps=True):
        known = {name: blk << bindata for name, blk in self._reg._blocks.items()}
        # TODO: get all undocumented sections
        return known

    def compile(self, mmap, fill=b'\x00', binsize=None):
        # TODO: check full coverage of all blocks
        # TODO: fill gaps
        # TODO: remap pointers
        bindata = b""
        for name, blk in sorted(mmap, key=lambda blk: len(blk[-1])):
            log.debug(f"Writing {len(blk)} bytes for section {name}")
            bindata += bytes(blk)

        pad = (binsize or len(bindata)) - len(bindata)
        assert pad >= 0
        return bindata + fill * pad

class MemoryLayoutParser:
    def __init__(self):
        pass

    @classmethod
    def parse(cls, filename):
        with open(filename, 'r') as fin:
            lines = fin.readlines()

        section_name, blk = None, None
        reg = Registry()
        while len(lines) > 0:
            line = lines.pop(0).strip()
            if len(line.replace("-", "").strip()) == 0:
                # comment or blank line
                blk = None
                continue

            if line.count("$") > 1:
                addr, *remainder = line.replace("$", "").strip().split(" ")
                beg, end, *_ = [int(a, base=16) for a in addr.split("-")]
                blk = reg.register_block(beg, end - beg,
                                         f"section_{hex(beg)}_{hex(end)}", line)
                continue
            elif line.count("$") > 0:
                blen = 1 + line.count("+")
                addr, *remainder = line.replace("+", "").strip().split(" ")
                addr = int(addr.replace("$", ""), base=16)
                blk = reg.register_block(addr, blen,
                                         f"section_{hex(beg)}_{hex(end)}", line)
            else:
                # Maybe consume option documentation
                blk.descr += "\n" + lines.pop(0)[:-1]

        return reg

#
# Progressive stuff
#
class QueueController(WriteQueue):
    pass

class ProgressiveRandomizer(StaticRandomizer):
    def __init__(self):
        self._q = QueueController()