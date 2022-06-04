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

class FF6ItemTable(FF6DataTable):
    @classmethod
    def _register(cls, datatypes):
        datatypes["itm_dt"] = FF6ItemTable
        return datatypes

    @dataclass
    class ItemEntry:
        item_type: data.ItemType
        equipped_by: data.EquipCharacter
        learn_rate: int
        learned_spell: data.Spell
        field_effect: int
        status_1: data.Status
        status_2: data.Status
        equip_status: data.Status
        equip_flags: data.EquipmentFlags
        targeting: data.SpellTargeting
        elemental_data: int
        vigor: int
        speed: int
        stamina: int
        magic: int
        # FIXME: This is also ItemFlags
        special_flags: int
        power_def: int
        # actor status 1? also magdef
        actor_status_1: data.Status
        # actor status 2? also elem absorb
        actor_status_2: data.Status
        # actor status 3? also elem null
        actor_status_3: data.Status
        # actor status 4? also elem weak
        actor_status_4: data.Status
        # ????
        _equipment_status: int
        evade: int
        magic_evade: int
        special_effect: int
        price: int

        # secondary stuff
        throwable: bool
        battle_useable: bool
        menu_useable: bool

        cast_spell: data.Spell
        random_cast: bool
        inv_remove: bool

        #enable_swdtech: bool
        #back_row: bool
        #two_handed: bool
        #dmg_rev: bool
        #affect_hp: bool
        #affect_mp: bool
        #remove_status: bool

        @classmethod
        def decode_item_meta(cls, value):
            """
            Decode the item metadata byte
            :param value: byte value
            :return: item type, throwability, battle usability, menu usability
            """
            return value & 0x7, bool(value & 0x10), \
                   bool(value & 0x20), bool(value & 0x40)

        @classmethod
        def encode_item_meta(cls, item_type, throwability, bat_use, menu_use):
            return menu_use << 7 | bat_use << 6 | throwability << 5 | item_type

        @classmethod
        def decode_evd(cls, value):
            """
            Decodes low and high nibbles for evade and magic evade
            :param value:
            :return:
            """
            return value & 0xF, value & 0xF0 >> 4

        @classmethod
        def decode_dual(cls, value):
            """
            Decodes dual variables like vig/spd and stm/mgc, determining whether they have pos/neg influence.
            :param value: byte value
            :return: var1, var2
            """
            return -(value & 0x8 >> 3) * value & 0x7, \
                   -(value >> 7) * value & 0x70 >> 4

        @classmethod
        def decode_wpn_spell_data(cls, value):
            """
            Decodes weapon spell data
            :param value: byte value
            :return: spell id, casts randomly, inventory removal
            """
            return data.Spell(value & 0x3F), value & 0x40 >> 6, value & 0x80 >> 7

        @classmethod
        def parse_from_bytes(cls, _data):
            args = dict(zip(["item_type", "throwable", "battle_useable", "menu_useable"],
                             cls.decode_item_meta(_data[0])))
            args.update(dict(zip(["vigor", "speed"], cls.decode_dual(_data[16]))))
            args.update(dict(zip(["stamina", "magic"], cls.decode_dual(_data[17]))))
            args.update(dict(zip(["evade", "magic_evade"], cls.decode_dual(_data[23]))))

            # FIXME: need a switch on item type
            args.update(dict(zip(["cast_spell", "random_cast", "inv_remove"],
                                 cls.decode_wpn_spell_data(_data[18]))))

            return cls(**{
                "equipped_by": data.EquipCharacter.from_bytes(_data[1:3], byteorder="little"),
                "learn_rate": _data[3],
                "learned_spell": data.Spell(_data[4]),
                "field_effect": _data[5],
                "status_1": data.Status(_data[6]),
                # FIXME: needs to be shifted?
                "status_2": data.Status(_data[7] << 8),
                "equip_status": data.Status(_data[8]),
                "equip_flags": data.EquipmentFlags.from_bytes(_data[9:14], byteorder="little"),
                "targeting": data.SpellTargeting(_data[14]),
                "elemental_data": data.Element(_data[15]),
                "special_flags": data.ItemFlags.from_bytes(_data[19:22], byteorder="little"),
                "power_def": _data[20],
                # ???
                "actor_status_1": data.Status(_data[21]),
                "actor_status_2": data.Status(_data[22]),
                "actor_status_3": data.Status(_data[23]),
                "actor_status_4": data.Status(_data[24]),
                "_equipment_status": data.Status(_data[25]),
                "special_effect": _data[27],
                "price": int.from_bytes(_data[27:29], byteorder="little"),
                **args
            })

        def __bytes__(self):
            meta = self.encode_item_meta(self.item_type, self.throwable,
                                         self.battle_useable, self.menu_useable)
            #args.update(dict(zip(["vigor", "speed"], cls.decode_dual(_data[10:12]))))
            #args.update(dict(zip(["stamina", "magic"], cls.decode_dual(_data[12:14]))))
            #args.update(dict(zip(["evade", "magic_evade"], cls.decode_dual(_data[23:25]))))

            return bytes([
                meta,
                self.equipped_by,
                self.learn_rate, self.learned_spell,
                self.field_effect,
                self.status_1, self.status_2,
                self.equip_status, self.targeting,
                self.vigor, self.speed, self.stamina,
                self.magic,
                self.item_flags,
                self.power_def,
                self.actor_status_1, self.actor_status_2,
                self.actor_status_3, self.actor_status_4,
                self.equipment_status,
                self.evade, self.magic_evade,
                self.special_effect,
                self.price
            ])

    def __init__(self):
        super().__init__(0x1E, addr=0x85000, length=0x1E00, name="item_table",
                         descr="Item Data")

    def read(self, bindata):
        return [self.ItemEntry.parse_from_bytes(data)
                for data in self.dereference(super().read(bindata))]
REGISTER_DATA = FF6ItemTable._register(REGISTER_DATA)

# FIXME: DO NOT USE, IS INCOMPLETE: USE WC'S VERSION
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
