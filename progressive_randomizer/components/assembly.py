import csv
import functools

import logging
log = logging.getLogger()

from . import MemoryStructure

def _int_from_asm_not(val, prefix="$"):
    return int(val.replace(prefix, "0x"), base=16)

def detect_header(text):
    return any([kw in text for kw in {"hirom", "lorom"}])

def strip_comments(text, comment=";"):
    try:
        idx = text.index(comment)
        text = text[:idx].strip()
    except ValueError:
        pass
    return text

def parse_chunks(text, separators):
    tok = [text]
    for sep in separators:
        for _ in range(len(tok)):
            t = tok.pop(0)
            if detect_header(t):
                continue
            tok.append(t.split(sep))
        tok = functools.reduce(list.__add__, tok, [])

    return tok

def handle_org(tok):
    return _int_from_asm_not(tok.replace("org", ""))

def handle_db(tok, seps=","):
    tok = tok.replace("db", "").strip()
    return handle_data(tok, seps)

def handle_data(text, sep=","):
    return bytes(map(_int_from_asm_not, text.strip().split(sep)))

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
    def _annotate(cls, bindata):
        prg = ""
        pad = max([len(op[0]) for op in cls.OP_REF.values()])
        for op, args in cls._disassemble(bindata):
            op_name = cls.OP_REF[op][0]
            args = " ".join([f"{arg:02x}".rjust(3) for arg in args])
            prg += f"{op_name.ljust(pad)} {args}\n"
        return prg

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
        return self._annotate(self.read(bindata))

    FLOW_OPS = {"JSR", "JSL", "RTS", "RTL", "JMP", "JML",
                "BEQ", "BNE", "BMI", "BPL", "BCS", "BCC", "BVS", "BVC", "BRA", "BRL"}

    def identify_pointers(self, bindata):
        pass

class AssemblyEditor(AssemblyObject):
    @classmethod
    def from_asm(cls, asm_file, seps="\n:", db_sep=",", comment=";"):
        with open(asm_file, "r") as fin:
            asm = fin.readlines()

        addr, data = None, b""
        for _ in range(len(asm)):
            line = strip_comments(asm.pop(0).strip(), comment=comment)
            tokens = parse_chunks(line, separators=seps)

            for tok in tokens:
                if tok == "":
                    continue
                if "org" in tok:
                    if addr is not None:
                        obj = cls(addr, len(data), name="", descr="")
                        yield obj, data
                    addr = handle_org(tok)
                    data = b""
                elif "db" in tok:
                    data += handle_db(tok, seps=db_sep)
                else:
                    raise SyntaxError(f"Unparsed token: {tok}")