"""
FF6 specifics
"""
from .. import StaticRandomizer, AssemblyObject, MemoryStructure

# US game name
GAME_NAME = b'FINAL FANTASY 3      '
ROM_MAP_DATA = "etc/ff6_rom_map.csv"
ROM_DESCR_TAGS = {"unused", "compressed", "pointers", "data", "names",
                  "descriptions", "program", "code", "ending", "font", "script",
                  "balance", "ruin", "world",
                  "item", "attack", "battle", "scripts", "attack",
                  "esper", "lores", "spell", "magic",
                  "blitz", "swdtech", "dance", "sketch", "rage"}


class FF6StaticRandomizer(StaticRandomizer):
    def __init__(self):
        super().__init__()
        self._reg = StaticRandomizer.from_rom_map(ROM_MAP_DATA,
                                                  ROM_DESCR_TAGS,
                                                  apply_offset=0xC00000)

    def __getitem__(self, item):
        # semantic behavior --- applying tags will produce different object
        # reads
        bare = super().__getitem__(item)
        if item in self._reg._tags.get("names", set()) | \
                self._reg._tags.get("descriptions", set()):
            return FF6Text.from_super(bare)
        elif item in self._reg._tags.get("pointers", set()):
            return FF6PointerTable.from_super(bare)
        elif item in self._reg._tags.get("data", set()):
            return FF6DataTable.from_super(bare)
        elif item in self._reg._tags.get("program", set()):
            return AssemblyObject(bare.addr, bare.length, bare.name, bare.descr)

        return bare

    def write(self, *args):
        # section, data, section, data, etc...
        pass

    # utils
    CHAR_NAME_LEN = 6
    def get_char_names(self, bindata, nbytes=CHAR_NAME_LEN):
        cnames_raw = self["chrct_nms"] << bindata
        return [cnames_raw[i * nbytes: (i + 1) * nbytes]
                for i in range(len(cnames_raw) // nbytes)]

    def get_unused_space_blks(self):
        return [self[k] for k in self._reg._tags.get("unused", [])]

class FF6Text(MemoryStructure):
    # Upper case
    _CHARS = {128 + i: chr(j) for i, j in enumerate(range(65, 65 + 26))}
    # Lower case
    _CHARS.update({154 + i: chr(j) for i, j in enumerate(range(97, 97 + 26))})
    # Numbers
    _CHARS.update({180 + i: chr(j) for i, j in enumerate(range(48, 48 + 10))})
    # FIXME: Will probably need symbols at some point
    _CHARS[190] = "!"
    _CHARS[191] = "?"
    _CHARS[193] = ":"
    _CHARS[195] = "'"
    _CHARS[196] = "-"
    _CHARS[197] = "."
    _CHARS[198] = ","
    _CHARS[0xd3] = "["
    _CHARS[0xc2] = "]"
    _CHARS[199] = "..."  # ellipsis character
    _CHARS[255] = " "

    @classmethod
    def from_super(cls, mem_struct):
        return cls(mem_struct.addr, mem_struct.length,
                   mem_struct.name, mem_struct.descr)

    @classmethod
    def _decode(cls, word):
        return "".join([cls._CHARS.get(i, "?") for i in word])

    #@classmethod
    #def _decode_stream(cls, words, sep=None):
    #return [cls._deocde(word) for word in words.split(sep)]

    @classmethod
    def _encode(cls, word):
        pass

    def patch(self, text, bindata):
        return super().patch(self._encode(text), bindata)

    def read(self, bindata):
        return self._decode(super().read(bindata))

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
        import struct
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

    def dereference(self, bindata, ptr_tbl=None):
        assert self.item_size is not None or ptr_tbl is not None
        raw_data = super().read(bindata)

        if self.item_size is not None:
            nitems = self.length // self.item_size
            itrs = [i * self.item_size for i in range(nitems + 1)]
        else:
            itrs = [ptr for ptr in ptr_tbl.read(bindata)] + [self.length]

        return [bytes(raw_data[i:j]) for i, j in zip(itrs[:-1], itrs[1:])]

