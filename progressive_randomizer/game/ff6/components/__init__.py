"""
FF6 specifics
"""
import math
from dataclasses import dataclass

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

    @dataclass
    class CharacterEntry:
        idx: int
        hp: int
        mp: int
        commands: list
        vigor: int
        speed: int
        stamina: int
        magic: int
        attack: int
        defense: int
        mag_def: int
        evade: int
        mag_evade: int
        right: int
        left: int
        body: int
        head: int
        relic_1: int
        relic_2: int

        run: int
        #run_success: int
        #run_alter: int

        @classmethod
        def parse_commands(cls, value):
            """
            :return: command list
            """
            return [*map(data.Command, value)]

        @classmethod
        def parse_from_bytes(cls, _data, **kwargs):
            return cls(**{
                "hp": _data[0], "mp": _data[1],
                "commands": cls.parse_commands(_data[2:6]),
                "vigor": _data[6], "speed": _data[7], "stamina": _data[8],
                "magic": _data[9], "attack": _data[10], "defense": _data[11],
                "mag_def": _data[12], "evade": _data[13], "mag_evade": _data[14],
                "right": _data[15], "left": _data[16],
                "body": _data[17], "head": _data[18],
                "relic_1": _data[19], "relic_2": _data[20],
                "run": _data[21],
                **kwargs
            })

        def __bytes__(self):
            return bytes([self.hp, self.mp,
                          *self.commands,
                          self.vigor, self.speed, self.stamina, self.magic,
                          self.attack, self.defense, self.mag_def, self.evade,
                          self.mag_evade, self.right, self.left, self.body,
                          self.head, self.relic_1, self.relic_2])

    @classmethod
    def _register(cls, datatypes):
        datatypes["chrct_intl_prprt"] = FF6CharacterTable
        return datatypes

    def __init__(self, **kwargs):
        super().__init__(item_size=self._ITEM_SIZE, addr=self._ADDR,
                         length=self._N_ITEMS * self._ITEM_SIZE,
                         name="init_char_data", descr="Initial Character Data",
                         **kwargs)

    def read(self, bindata):
        return [self.CharacterEntry.parse_from_bytes(data, idx=i)
                for i, data in enumerate(self.dereference(super().read(bindata)))]
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
        datatypes["bttl_cmmnd_dt"] = FF6CommandTable
        return datatypes

    @dataclass
    class CommandEntry:
        idx: int
        can_mimic: bool
        can_imp: bool

        targeting: data.SpellTargeting

        @classmethod
        def parse_preference(cls, value):
            """
            :return: mimic, imp
            """
            return bool(value & 0x2), bool(value & 0x4)

        @classmethod
        def parse_from_bytes(cls, _data, **kwargs):
            mimic, imp = cls.parse_preference(_data[0])
            return cls(**{
                "can_mimic": mimic,
                "can_imp": imp,
                "targeting": data.SpellTargeting(_data[1]),
                **kwargs
            })

        def __bytes__(self):
            pref = int(self.can_mimic) << 1 | int(self.can_imp) << 2
            return bytes([pref, self.targeting])

    def __init__(self):
        super().__init__(0x2, addr=0xFFE00, length=0x40, name="command_table",
                         descr="Command Data")

    def read(self, bindata):
        return [self.CommandEntry.parse_from_bytes(data, idx=i)
                for i, data in enumerate(self.dereference(super().read(bindata)))]
REGISTER_DATA = FF6CommandTable._register(REGISTER_DATA)

class FF6SpellTable(FF6DataTable):
    @classmethod
    def _register(cls, datatypes):
        datatypes["spll_dt"] = FF6SpellTable
        return datatypes

    @dataclass
    class SpellEntry:
        idx: int
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
        def parse_from_bytes(cls, _data, **kwargs):
            return cls(**{
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
                # Use kwargs to override initializations from bytes
                **kwargs
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
        return [self.SpellEntry.parse_from_bytes(data, idx=i)
            for i, data in enumerate(self.dereference(super().read(bindata)))]
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
        field_effect: data.FieldEffects
        status_1: data.Status
        status_2: data.Status
        equip_status: data.Status
        equip_flags: data.EquipmentFlags
        targeting: data.SpellTargeting
        elemental_data: data.Element
        vigor: int
        speed: int
        stamina: int
        magic: int
        # FIXME: This is also *SpecialFlags
        special_flags: int
        power: int
        # actor status 1? also magdef
        actor_status_1: int
        # actor status 2? also elem absorb
        actor_status_2: int
        # actor status 3? also elem null
        actor_status_3: int
        # actor status 4? also elem weak
        actor_status_4: int
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

        name: str = ""
        descr: str = ""

        @classmethod
        def decode_item_meta(cls, value):
            """
            Decode the item metadata byte
            :param value: byte value
            :return: item type, throwability, battle usability, menu usability
            """
            return data.InventoryType(value & 0x7), bool(value & 0x10), \
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
            return int(math.copysign(value & 0x7, -((value & 0x8) >> 3) + 0.5)), \
                   int(math.copysign((value & 0x70) >> 4, -(value >> 7) + 0.5))

        @classmethod
        def encode_dual(cls, low, high):
            lsign = int(bool(math.copysign(1, low) == -1)) << 3
            hsign = int(bool(math.copysign(1, high) == -1)) << 7
            return abs(low) + lsign + (abs(high) << 4) + hsign

        @classmethod
        def decode_wpn_spell_data(cls, value):
            """
            Decodes weapon spell data
            :param value: byte value
            :return: spell id, casts randomly, inventory removal
            """
            return data.Spell(value & 0x3F), bool(value & 0x40 >> 6), bool(value & 0x80 >> 7)

        @classmethod
        def encode_wpn_spell_data(cls, spell, random_cast, inv_remove):
            """
            Decodes weapon spell data
            :param value: byte value
            :return: spell id, casts randomly, inventory removal
            """
            # FIXME: assert that the spell <= 0x3F
            return (spell & 0x3F) + (int(random_cast) << 6) + (int(inv_remove) << 7)

        @classmethod
        def parse_from_bytes(cls, _data):
            args = dict(zip(["item_type", "throwable", "battle_useable", "menu_useable"],
                             cls.decode_item_meta(_data[0])))
            args.update(dict(zip(["vigor", "speed"], cls.decode_dual(_data[16]))))
            args.update(dict(zip(["stamina", "magic"], cls.decode_dual(_data[17]))))
            args.update(dict(zip(["evade", "magic_evade"], cls.decode_evd(_data[23]))))

            # FIXME: need a switch on item type
            args.update(dict(zip(["cast_spell", "random_cast", "inv_remove"],
                                 cls.decode_wpn_spell_data(_data[18]))))

            return cls(**{
                "equipped_by": data.EquipCharacter.from_bytes(_data[1:3], byteorder="little"),
                "learn_rate": _data[3],
                "learned_spell": data.Spell(_data[4]),
                "field_effect": _data[5],
                "status_1": data.Status(_data[6]),
                "status_2": data.Status(_data[7] << 8),
                "equip_status": data.Status(_data[8] << 16),
                "equip_flags": data.EquipmentFlags.from_bytes(_data[9:14], byteorder="little"),
                "targeting": data.SpellTargeting(_data[14]),
                "elemental_data": data.Element(_data[15]),
                "special_flags": _data[19],
                "power": _data[20],
                "actor_status_1": data.Status(_data[21]),
                "actor_status_2": data.Status(_data[22] << 8),
                "actor_status_3": data.Status(_data[23] << 16),
                "actor_status_4": data.Status(_data[24] << 24),
                "_equipment_status": data.Status(_data[25] << 8),
                "special_effect": _data[27],
                "price": int.from_bytes(_data[28:30], byteorder="little"),
                **args
            })

        def __bytes__(self):
            meta = self.encode_item_meta(self.item_type, self.throwable,
                                         self.battle_useable, self.menu_useable)
            wpn_spell_data = self.encode_wpn_spell_data(self.cast_spell,
                                                        self.random_cast,
                                                        self.inv_remove)

            # special treatment for the actor_status
            if self.item_type == data.InventoryType.Item \
               or self.name == " Empty".ljust(13):
                status_blk = bytes([self.actor_status_1,
                                    self.actor_status_2 >> 8,
                                    self.actor_status_3 >> 16,
                                    self.actor_status_4 >> 24])
            else:
                status_blk = bytes([self.actor_status_1, self.actor_status_2,
                                    self.actor_status_3, self.actor_status_4])

            return bytes([
                meta,
                *self.equipped_by.to_bytes(2, byteorder="little"),
                self.learn_rate, self.learned_spell,
                self.field_effect,
                self.status_1 >> 8,
                self.status_2 >> 16,
                self.equip_status >> 16,
                *self.equip_flags.to_bytes(5, byteorder="little"),
                self.targeting,
                self.elemental_data,
                self.encode_dual(self.vigor, self.speed),
                self.encode_dual(self.stamina, self.magic),
                wpn_spell_data,
                self.special_flags,
                self.power,
                *status_blk,
                self._equipment_status.as_sngl_byte(),
                self.evade + (self.magic_evade << 4),
                self.special_effect,
                *self.price.to_bytes(2, byteorder="little")
            ])

        def decode_special_flags(self):
            if self.item_type == data.InventoryType.Weapon:
                return data.WeaponSpecialFlags(self.special_flags)
            elif self.item_type == data.InventoryType.Item:
                return data.ItemSpecialFlags(self.special_flags)

        def decode_special_effect(self):
            if self.item_type == data.InventoryType.Item:
                return data.SpecialEffects._as_item_flag(self.special_effect)
            return data.SpecialEffects._as_nonitem_flag(self.special_effect)

        def _se_to_str(self):
            if int(self.special_effect) not in {0, 0xE, 0xFF}:
                return ""
            if self.item_type == data.InventoryType.Item:
                return data.SpecialEffects._as_item_flag(self.special_effect).name

            anim, blk = data.SpecialEffects._as_nonitem_flag(self.special_effect)
            nanim, nblk = anim.name if anim else "", blk.name if blk else ""
            return f"{nanim} {nblk}".strip()

        def spoiler_text(self, idnum=None):
            idnum = "" if idnum is None else str(idnum).ljust(3) + ". "

            stat_blk = ""
            if self.item_type == data.InventoryType.Item and self.power > 0:
                stat_blk += f"Heal Power: {self.power}"
            elif self.item_type == data.InventoryType.Weapon:
                stat_blk += f"Weapon Power: {self.power}"
            elif self.item_type in {data.InventoryType.Armor,
                                    data.InventoryType.Helmet,
                                    data.InventoryType.Shield}:
                stat_blk += f"Defense Power: {self.power} Mag. Defense Power: {int(self.actor_status_1)}"

            #if self.item_type not in {data.InventoryType.Item, data.InventoryType.Relic}:
            if self.item_type not in {data.InventoryType.Item}:
                stat_blk += f"\nVigor:        {self.vigor:+2d}  Speed:       {self.speed:+2d}"
                stat_blk += f"\nStamina:      {self.stamina:+2d}  Magic:       {self.magic:+2d}"
                stat_blk += f"\nEvade:        {self.evade:+2d}  Magic Evade: {self.magic_evade:+2d}"

            special_blk = ""
            if self.equip_flags != data.EquipmentFlags.NoEffect:
                flags = data.format_flags(self.equip_flags)
                special_blk += f"Special Effects: {flags}"

            attr_blk = ""
            if self.item_type == data.InventoryType.Weapon and self.special_flags != 0:
                flags = data.format_flags(data.WeaponSpecialFlags(self.special_flags))
                attr_blk += f"Weapon Attributes: {flags}"
            elif self.special_flags != 0:
                flags = data.format_flags(data.ItemSpecialFlags(self.special_flags))
                attr_blk += f"Special Attributes: {flags}"
            if self.special_flags != 0:
                attr_blk += f"\nSpecial Effects: {self._se_to_str()}"

            elem_blk = ""
            if self.elemental_data != data.Element.NoElement:
                flags = data.format_flags(self.elemental_data)
                elem_blk += f"Elements: {flags}"
            #elif self.item_type == data.InventoryType.Weapon and self.

            status_blk = ""
            if (self.status_1 | self.status_2) != data.Status.NoStatus:
                flags = data.format_flags(self.status_1 | self.status_2)
                status_blk += f"Prevents: {flags} "
            if (self.equip_status | self._equipment_status) != data.Status.NoStatus:
                flags = data.format_flags(self.equip_status | self._equipment_status)
                status_blk += f"Equip Status: {flags} "

            cure_status = self.actor_status_1 | self.actor_status_2 \
                        | self.actor_status_3 | self.actor_status_4
            if self.item_type == data.InventoryType.Item and cure_status != data.Status.NoStatus:
                status_blk += f"Removes: {data.format_flags(cure_status)}"

            if self.item_type != data.InventoryType.Item and self.actor_status_2 != data.Element.NoElement:
                flags = data.format_flags(data.Element(self.actor_status_2 >> 8))
                elem_blk += f"\nAbsorb: {flags}"
            if self.item_type != data.InventoryType.Item and self.actor_status_3 != data.Element.NoElement:
                flags = data.format_flags(data.Element(self.actor_status_3 >> 16))
                elem_blk += f"\nNull: {flags}"
            if self.item_type != data.InventoryType.Item and self.actor_status_4 != data.Element.NoElement:
                flags = data.format_flags(data.Element(self.actor_status_4 >> 24))
                elem_blk += f"\nWeak: {flags}"

            spell_blk = ""
            if self.learn_rate > 0:
                spell_blk += f"Spell learned: {self.learned_spell.name} x{self.learn_rate}"
            if self.random_cast or self.inv_remove:
                spell_blk += f"Spell proc: {self.cast_spell.name} | random proc: {self.random_cast} | breaks: {self.inv_remove}"

            equip_blk = ""
            if self.item_type != data.InventoryType.Item:
                equip_blk = f"Equipped by: {data.format_flags(self.equipped_by)}"

            table = "\n".join(filter(lambda k: k, [equip_blk, stat_blk, elem_blk,
                                                   status_blk, attr_blk, special_blk,
                                                   spell_blk]))
            return f"""
{idnum}[{self.item_type.name}] {self.name.strip()}: {self.descr}
In menu: {self.menu_useable} | In battle: {self.battle_useable} | Throwable: {self.throwable}
Price: {self.price}
{table}""".strip()

    def __init__(self):
        super().__init__(0x1E, addr=0x185000, length=0x1E00, name="item_table",
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
