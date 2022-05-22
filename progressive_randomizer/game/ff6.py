"""
FF6 specifics
"""
import re

from .. import (
    StaticRandomizer,
    AssemblyObject,
    MemoryStructure,
    MemoryLayoutParser,
    Registry
)

# US game name
GAME_NAME = b'FINAL FANTASY 3      '
ROM_MAP_DATA = "etc/ff6_rom_map.csv"
ROM_DESCR_TAGS = {"unused", "compressed", "pointers", "data", "names",
                  "character", "messages",
                  "descriptions", "program", "code", "ending", "font", "script",
                  "balance", "ruin", "world",
                  "item", "attack", "battle", "scripts", "attack",
                  "esper", "lores", "spell", "magic",
                  "blitz", "swdtech", "dance", "sketch", "rage"}

REGISTER_DATA = {}

def _register(known_games):
    known_games[GAME_NAME] = FF6StaticRandomizer

class FF6SRAM(Registry):
    def __init__(self):
        super().__init__()

        for blk in MemoryLayoutParser.parse("etc/ff6_sram_descr.txt")._blocks.values():
            self.register_block(blk.addr, blk.length, blk.name, blk.descr)

class FF6BattleRAM(Registry):
    def __init__(self, reg):
        super().__init__()
        self._reg = reg

    def _setup(self):
        blks = [
            dict(addr=0x0, length=0x100, name="bttl_dp",
                 descr="$0000-$00FF: Battle Direct Page"),
            dict(addr=0x0100, length=0x100, name="bttl_ram",
                 descr="$0100-$01FF: Battle RAM | Used by battle menus."),
            # ...
            dict(addr=0x1600, length=0x2000 - 0x1600, name="sram",
                 descr="$1600-$1FFF: Save RAM | SRAM"),
            # ...
        ]

        for blk in blks:
            self.register_block(**blk)

class FF6StaticRandomizer(StaticRandomizer):
    def __init__(self):
        super().__init__()
        self._reg = StaticRandomizer.from_rom_map(ROM_MAP_DATA,
                                                  ROM_DESCR_TAGS,
                                                  apply_offset=0xC00000)

    def __getitem__(self, item):
        # semantic behavior --- applying tags will produce different object
        # reads
        if item in REGISTER_DATA:
            return REGISTER_DATA[item]()

        bare = super().__getitem__(item)
        if item in self._reg._tags.get("pointers", set()):
            return FF6PointerTable.from_super(bare)
        elif item in self._reg._tags.get("pointers", set()):
            return FF6PointerTable.from_super(bare)
        elif item in self._reg._tags.get("data", set()):
            return FF6DataTable.from_super(bare)
        elif item in self._reg._tags.get("program", set()):
            return AssemblyObject(bare.addr, bare.length, bare.name, bare.descr)
        elif item in self._reg._tags.get("names", set()) | \
                self._reg._tags.get("descriptions", set()) | \
                self._reg._tags.get("messages", set()):
            return FF6Text.from_super(bare)

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
        # FIXME
        try:
            return word.encode()
        except AttributeError:
            return word

    @classmethod
    def serialize(cls, json_repr):
        _data = json_repr.pop("_data", None)
        return cls._encode(_data)

    def patch(self, text, bindata=None):
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

class FF6EventFlags(FF6DataTable):
    @classmethod
    def parse(cls, filename):
        with open(filename, 'r') as fin:
            lines = fin.readlines()

        # FIXME make constants
        _FF6_EVENT_FLAG_START = 0x1E80
        return {int(line[0], base=16) / 8 + _FF6_EVENT_FLAG_START: " ".join(line[2:])
                for line in map(str.split, lines)}

    def __init__(self):
        super().__init__(1, addr=0x1E80, length=96, name="event_flags",
                         descr="Event Flags")
        self.event_flags = self.parse("etc/ff6_event_flags.txt")

    def read(self, bindata):
        flagblock = super().read(bindata)
        # FIXME: check
        return {descr: int.from_bytes(flagblock, byteorder="little") & (1 << i) != 0
                for i, descr in enumerate(self.event_flags.values())}

class FF6CharacterTable(FF6DataTable):
    _ADDR = 0x2D7CA0
    _ITEM_SIZE = 22
    _N_ITEMS = 64
    _FIELDS = ["+HP", "+MP", "CMD1",  "CMD2", "CMD3", "CMD4",
               "VIG", "SPD", "STM", "MAG",
               "+ATK", "+DEF", "+MDF", "+EVD", "+MEV",
               "RGHT" , "LEFT", "BODY", "HEAD", "RLC1", "RLC2", "RUN"]

    @classmethod
    def _register(cls, datatypes):
        datatypes["chrct_intl_prprt"] = FF6CharacterTable
        return datatypes

    def __init__(self, **kwargs):
        super().__init__(item_size=self._ITEM_SIZE, addr=self._ADDR,
                         length=self._N_ITEMS * self._ITEM_SIZE,
                         name="init_char_data", descr="Initial Character Data",
                         **kwargs)

    def dereference(self, bindata):
        return [{descr: data
                 for descr, data in zip(self._FIELDS, raw_data)}
                    for raw_data in super().dereference(bindata)]

    def read(self, bindata):
        return self.dereference(bindata)
REGISTER_DATA = FF6CharacterTable._register(REGISTER_DATA)

from .. import ProgressiveRandomizer
class FF6ProgressiveRandomizer(ProgressiveRandomizer):
    def __init__(self):
        super().__init__()
        # replace our registry with one specific to RAM
        self._reg = FF6SRAM()

    _EVENT_BITS = {

    }
    def check_events(self):
        pass

    def watch_location(self):
        import time
        for _ in range(100):
            time.sleep(1)
            self.scan_memory()
            print(self._ram[0x1EA5:0x1EA7])

    def watch_event_flags(self):
        import time
        event_flags = FF6EventFlags()
        self.scan_memory()
        events = event_flags << self._ram
        for _ in range(1000):
            time.sleep(1)
            self.scan_memory()
            _events = event_flags << self._ram
            diff = {k for k in events if _events[k] ^ events[k]}
            if len(diff) > 0:
                print(diff)
            else:
                print(f"No change: {sum(events.values())} {sum(_events.values())}")
            events = _events
