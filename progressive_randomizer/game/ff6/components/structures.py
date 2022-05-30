import re
import struct

from ....components import MemoryStructure

# dataclass?
class FF6PointerTable(MemoryStructure):
    def __init__(self, ptr_size=2, **kwargs):
        super().__init__(**kwargs)
        self.ptr_size = ptr_size

    # FIXME: this shouldn't know or care about its offset
    # it might need to know if we did automatic linkage...
    # We also need to find a more consistent way to handle the 0xC00000
    @classmethod
    def maybe_parse_offset(cls, descr):
        try:
            return int(re.search(r'\$([C-F][0-9A-Fa-f]+)', descr).group(1), base=16) - 0xC00000
        except (AttributeError, IndexError):
            pass
        return 0

    @classmethod
    def from_super(cls, mem_struct, ptr_size=2):
        return cls(ptr_size,
                   addr=mem_struct.addr, length=mem_struct.length,
                   name=mem_struct.name, descr=mem_struct.descr)

    def read(self, bindata):
        raw_data = super().read(bindata)
        return struct.unpack("<" + "H" * (len(raw_data) // 2), raw_data)

class FF6DataTable(MemoryStructure):
    def __init__(self, item_size=None, **kwargs):
        super().__init__(**kwargs)
        self.item_size = item_size

    @classmethod
    def maybe_parse_size(cls, descr):
        try:
            return int(re.search(r'([0-9]+) bytes', descr).group(1))
        except (AttributeError, IndexError):
            pass
        return None

    @classmethod
    def from_super(cls, mem_struct, item_size=None):
        return cls(item_size or cls.maybe_parse_size(mem_struct.descr),
                   addr=mem_struct.addr, length=mem_struct.length,
                   name=mem_struct.name, descr=mem_struct.descr)

    # make a PointerTable object
    def to_ptr_table(self, addr):
        # FIXME: won't work for variable length
        tbl_length = self.length // self.item_size
        return FF6PointerTable(addr=addr, length=tbl_length, name="", descr="")

    def dereference(self, bindata, ptr_tbl=None, offset=None):
        assert self.item_size is not None or ptr_tbl is not None
        bindata = self << bindata

        if self.item_size is not None:
            nitems = self.length // self.item_size
            itrs = [i * self.item_size for i in range(nitems + 1)]
        else:
            itrs = [ptr + offset for ptr in ptr_tbl.read(bindata)] + [self.length + offset]

        return [bytes(bindata[i:j]) for i, j in zip(itrs[:-1], itrs[1:])]
