"""
FF6 specifics
"""
from dataclasses import dataclass, asdict

from .. import data

from .text import *
from .structures import *
from .ram import *

REGISTER_DATA = {}

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

class FF6BattleMessages(FF6Text):
    _ADDR = 0x11F000
    _TERM_CHAR = b"\x00"
    @classmethod
    def _register(cls, datatypes):
        datatypes["bttl_mssgs"] = FF6BattleMessages
        return datatypes

    def __init__(self, **kwargs):
        super().__init__(addr=self._ADDR, length=0x7A0,
                         name="battle_messages", descr="Short Battle Messages",
                         **kwargs)

    def read(self, bindata):
        raw_data = super().read(bindata)
        return [self._decode(msg) for msg in raw_data.split(self._TERM_CHAR)]
REGISTER_DATA = FF6BattleMessages._register(REGISTER_DATA)

class FF6CommandTable(FF6DataTable):
    @classmethod
    def _register(cls, datatypes):
        datatypes["cmmd_dt"] = FF6CommandTable
        return datatypes

    @dataclass
    class CommandEntry:
        preference: list
        targeting: list

        @classmethod
        def parse_from_bytes(cls, _data):
            return cls(**{
                "preference": ...,
                "targeting": ...,
            })

        def __bytes__(self):
            return bytes([self.preference, self.targeting])

    def __init__(self):
        super().__init__(0x2, addr=0xFFE00, length=0x40, name="command_table",
                         descr="Command Data")

    def read(self, bindata):
        return [self.CommandEntry.parse_from_bytes(data)
                for data in self.dereference(super().read(bindata))]
REGISTER_DATA = FF6CommandTable._register(REGISTER_DATA)

class FF6SpellTable(FF6DataTable):
    @classmethod
    def _register(cls, datatypes):
        datatypes["spll_dt"] = FF6SpellTable
        return datatypes

    @dataclass
    class SpellEntry:
        targeting: list
        element: list
        spell_flags_1: list
        spell_flags_2: list
        spell_flags_3: list
        mp_cost: int
        spell_power: int
        spell_flags_4: list
        hit_rate: int
        status_1: list
        status_2: list
        status_3: list
        status_4: list

        @classmethod
        def parse_from_bytes(cls, _data):
            return cls(**{
                #"idx": ...
                "targeting": data.SpellTargeting(_data[0]),
                "element": data.Element(_data[1]),
                # FIXME: CHECK ORDER
                "spell_flags_1": data.SpellSpecialFlags(_data[2]),
                "spell_flags_2": data.SpellSpecialFlags(_data[3] << 8),
                "spell_flags_3": data.SpellSpecialFlags(_data[4] << 16),
                "mp_cost": _data[5],
                "spell_power": _data[6],
                "spell_flags_4": data.SpellSpecialFlags(_data[7] << 24),
                "hit_rate": _data[8],
                "status_1": data.Status(_data[8]),
                "status_2": data.Status(_data[8] << 8),
                "status_3": data.Status(_data[8] << 16),
                "status_4": data.Status(_data[8] << 24),
            })

        def __bytes__(self):
            return bytes([self.targeting, self.element,
                          self.spell_flags_1, self.spell_flags_2,
                          self.spell_flags_3,
                          self.mp_cost, self.spell_power,
                          self.spell_flags_4,
                          self.hit_rate,
                          self.status_1, self.status_2,
                          self.status_3, self.status_4])

    def __init__(self):
        super().__init__(0xE, addr=0x46AC0, length=0xE00, name="spell_table",
                         descr="Spell Data")

    def read(self, bindata):
        return [self.SpellEntry.parse_from_bytes(data)
                for data in self.dereference(super().read(bindata))]
REGISTER_DATA = FF6SpellTable._register(REGISTER_DATA)

class FF6CompressionCodec(MemoryStructure):
    def __init__(self):
        pass

    def read(self, bindata):
        """
        https://datacrystal.romhacking.net/wiki/Final_Fantasy_VI:Compression_Format

        https://en.wikipedia.org/wiki/LZ77_and_LZ78#LZ77
        """
        data = super().read(bindata)
        # This is zero for our emulated buffers
        #start_f3 = self.addr
        # Technically this is the destination in RAM, but we're emulating it
        dst_f6 = 0
        dsize = int.from_bytes(data[:2], byteorder="little")
        data = data[2:]

        buffer = bytearray([0] * 2048)
        dst_buf = bytearray([0] * 2048)
        bptr = 0

        i = 0
        while dsize >= 0:
            if i % 8 == 0:
                flags, data = data[0], data[1:]
                continue
            else:
                bit = 1 << ((i % 8) + 1)
            i += 1

            if flags & bit == bit:
                dst_buf[dst_f6] = buffer[bptr] = data[0]
                data = data[1:]

                bptr += 1
                dsize -= 1
            else:
                cpy = int.from_bytes(data[:2], byteorder="little")
                data = data[2:]
                # FIXME: check shift
                ptr = cpy & (1 << 12 - 1)
                nbytes = cpy & (1 << 6 - 1) << 16 + 3
                # Is this copying the data or the bindata?
                # data crystal claims it goes into both buffers?
                #buffer[ptr:ptr + nbytes] = data[:nbytes]
                dst_buf[dst_f6:dst_f6 + nbytes] = buffer[ptr:ptr + nbytes]
                data = data[nbytes:]
                bptr += nbytes
                dsize -= nbytes + 2
