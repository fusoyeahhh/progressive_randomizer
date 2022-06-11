import pprint
import csv

from dataclasses import dataclass, asdict

import logging
log = logging.getLogger()

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
            # rom = struct @ b"\xff\xff" >> rom
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

    def deserialize(self, bindata):
        return {**asdict(self),
                "_type": self.__class__.__name__,
                "_data": self.read(bindata)}

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

class AssemblyObject(MemoryStructure):
    OP_REF = {}
    with open("etc/snes_op_code_ref.csv", "r") as fin:
        OP_REF = {int(item[3], base=16): (item[0], int(item[-2][0]))
                  for item in csv.reader(fin.readlines())}

    @classmethod
    def _from_mem_structure(cls, memstruct):
        return cls(memstruct.addr, memstruct.length,
                   memstruct.name, memstruct.descr)

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

    FLOW_OPS = {"JSR", "JSL", "RTS", "RTL", "JMP", "JML",
                "BEQ", "BNE", "BMI", "BPL", "BCS", "BCC", "BVS", "BVC", "BRA", "BRL"}

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
