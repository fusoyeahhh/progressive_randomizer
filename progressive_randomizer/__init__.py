import logging
log = logging.getLogger()

from .components import Registry

# FIXME: send to `io.parser` module
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
