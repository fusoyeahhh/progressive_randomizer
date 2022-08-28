from dataclasses import dataclass, asdict
from enum import IntFlag, auto
import logging
log = logging.getLogger()

from ....components import MemoryStructure
from ....tasks import WriteBytes

from .. import data as flag_data
from ..components import (
    FF6Text,
    FF6SRAM,
    FF6BattleRAM,
    FF6DataTable,
    FF6CharacterTable,
)

from ..randomizers import FF6StaticRandomizer, FF6ProgressiveRandomizer
from ..data import Character, Command, Status, Item

class PartyFlags(IntFlag):
    NOFLAGS = 0
    PARTY_1 = 1
    PARTY_2 = 1 << 1
    PARTY_3 = 1 << 2
    BACK_ROW = 1 << 5
    ENABLED = 1 << 6
    VISIBLE = 1 << 7


@dataclass
class CharData:
    @dataclass
    class HPMP:
        value: int
        max_value: int
        boost: int = 0
        min_value: int = 0

        def set_value(self, val):
            self.value = max(self.min_value, min(self.max_value, val))

        def set_bound(self, lower=None, upper=None):
            self.min_value = lower or self.min_value
            self.max_value = upper or self.max_value

            # reset to bounds if needed
            self.set_value(self.value)

        def __bytes__(self):
            val = self.value.to_bytes(2, byteorder="little")
            val += (self.max_value | self.boost << 14).to_bytes(2, byteorder="little")
            return val

        def str(self):
            return f"{self.value} / {self.max_value} (boost: {self.boost})"

        @classmethod
        def from_bytes(cls, data):
            return cls(*cls.decode_hpmp(data))

        @classmethod
        def decode_hpmp(cls, data):
            assert len(data) == 4
            current_val = int.from_bytes(data[:2], byteorder="little")
            data = int.from_bytes(data[2:], byteorder="little")
            boost = data >> 14
            return current_val, data & 0x3FFF, boost

    actor_name: str
    actor_index: int
    graphic_index: int
    level: int
    hp: HPMP
    mp: HPMP
    exp: int
    status_1: flag_data.Status
    status_4: flag_data.Status
    commands: list
    vigor: int
    speed: int
    stamina: int
    mag_pwr: int
    esper: int
    weapon: Item
    shield: Item
    helmet: Item
    armor: Item
    relic_1: Item
    relic_2: Item

    def __bytes__(self):
        return bytes([self.actor_index, self.graphic_index]) + \
               FF6Text._encode(self.actor_name.ljust(6)) + \
               bytes([self.level]) + \
               bytes(self.hp) + bytes(self.mp) + \
               self.exp.to_bytes(3, byteorder="little") + \
               bytes([int(self.status_1), int(self.status_4) >> 24]) + \
               bytes(self.commands) + \
               bytes([self.vigor, self.speed, self.stamina, self.mag_pwr]) + \
               bytes([self.esper]) + \
               bytes([self.weapon, self.shield, self.helmet, self.armor]) + \
               bytes([self.relic_1, self.relic_2])

    def __str__(self):
        return f"""
[{self.actor_index}|{self.graphic_index}] {self.actor_name}
level: {self.level:4d} exp: {self.exp:6d}
HP: {self.hp.str().rjust(20)} MP: {self.mp.str().rjust(20)}
vigor:   {self.vigor:6d} speed:   {self.speed:6d}
stamina: {self.stamina:6d} mag_pwr: {self.mag_pwr:6d}
Status: {self.status_1}
Status: {self.status_4}
---
weapon:  {str(self.weapon).ljust(10)}
shield:  {str(self.shield).ljust(10)}
armor:   {str(self.armor).ljust(10)}
helmet:  {str(self.helmet).ljust(10)}
relic 1: {str(self.relic_1).ljust(10)}
relic 2: {str(self.relic_2).ljust(10)}
---
commands: {', '.join(map(str, self.commands))}
esper: {self.esper}
        """

    @classmethod
    def decode(cls, data):
        stats = dict(zip(["vigor", "speed", "stamina", "mag_pwr"],
                         data[26:30]))
        equip = dict(zip(["weapon", "shield", "helmet", "armor", "relic_1", "relic_2"],
                         map(Item, data[31:])))

        return {
            "actor_index": data[0],
            "graphic_index": data[1],
            "actor_name": FF6Text._decode(bytes(data[2:8])),
            "level": data[8],
            "hp": cls.HPMP.from_bytes(data[9:13]),
            "mp": cls.HPMP.from_bytes(data[13:17]),
            "exp": int.from_bytes(data[17:20], byteorder="little"),
            "status_1": flag_data.Status(data[21]),
            "status_4": flag_data.Status(data[22] << 24),
            "commands": [flag_data.Command(cmd) for cmd in data[22:26]],
            **stats,
            "esper": 0,
            **equip
        }

    @classmethod
    def init_from_slot(cls, slot, bindata, ramdata):
        assert slot >= 0 and slot <= 16
        #romdata = FF6CharacterTable().read(bindata)
        charblk = FF6SRAM()._blocks["section_0x1600_0x1850"]

        cdata = FF6DataTable.from_super(charblk, 37)

        raw_data = cdata.dereference(cdata << ramdata)
        if raw_data[slot][0] >= 16:
            log.warning(f"Character in slot {slot} appears to not be initialized yet.")
            return None
        return cls(**cls.decode(raw_data[slot]))

#
# Templates
#
class BaseTmplt(CharData):
    _TMPLT = {
        "actor_index": 0,
        "graphic_index": 0,
        "actor_name": "Base",
        "level": 1,
        "hp": CharData.HPMP(100, 100),
        "mp": CharData.HPMP(0, 0),
        "exp": 0,
        "status_1": Status.NoStatus,
        "status_4": Status.NoStatus,
        "commands": [
            Command.Fight,
            Command.Nothing,
            Command.Nothing,
            Command.Item
        ],
        "vigor": 30, "speed": 30, "stamina": 30, "mag_pwr": 30,
        "esper": 0,
        "weapon": Item.Blank, "shield": Item.Blank,
        "helmet": Item.Blank, "armor": Item.Blank,
        "relic_1": Item.Blank, "relic_2": Item.Blank
    }

    @classmethod
    def from_rom_data(cls, actor_idx, bindata, **kwargs):
        romdata = FF6CharacterTable().read(bindata)
        cdata = asdict(romdata[actor_idx])
        cdata.pop("idx")
        # FIXME: use this?
        cdata.pop("run")
        # FIXME: ???
        for attr in ["attack", "defense", "magic", "mag_def", "evade", "mag_evade"]:
            cdata.pop(attr)
        hp = cdata.pop("hp")
        cdata["hp"] = cls.HPMP(hp, hp)
        mp = cdata.pop("mp")
        cdata["mp"] = cls.HPMP(mp, mp)
        cdata["weapon"] = Item(cdata.pop("right"))
        cdata["shield"] = Item(cdata.pop("left"))
        cdata["helmet"] = Item(cdata.pop("head"))
        cdata["armor"] = Item(cdata.pop("body"))

        cdata["actor_index"] = actor_idx
        cdata["graphic_index"] = actor_idx
        cdata = {**cdata, **kwargs}

        # TODO: get name
        cdata["actor_name"] = Character(actor_idx).name

        return cls(**cdata)

    def __init__(self, **kwargs):
        super().__init__(**{
            **BaseTmplt._TMPLT,
            **kwargs
        })

# TODO: from JSON?
# TODO: classmethods?
class BlackMage(BaseTmplt):
    _TMPLT = {
        "hp": CharData.HPMP(50, 50),
        "mp": CharData.HPMP(20, 20),
        "actor_name": "BlkMag",
        "commands": [
            Command.Fight,
            Command.Nothing,
            Command.Magic,
            Command.Item
        ],
        "vigor": 30, "speed": 25, "stamina": 25, "mag_pwr": 40,
        "esper": 0,
        "weapon": Item.Dirk, "shield": Item.Blank,
        "helmet": Item.Bards_Hat, "armor": Item.Cotton_Robe,
        "relic_1": Item.Blank, "relic_2": Item.Blank
    }

    def __init__(self):
        super().__init__(**BlackMage._TMPLT)

class FF6CharacterManager(FF6StaticRandomizer):
    _MORPH_MEMBLK = MemoryStructure(addr=0x25E32, length=2, name="morph_data",
                                    descr="Character specific morph byte data")

    @classmethod
    def validate(cls, chr_data):
        if len(chr_data) != 16:
            log.warning("Attempting to modify more or less than all 16 characters.")

        # FIXME: does this always have to be fight?
        if not all([c.commands[0] is Command.Fight for c in chr_data.values()
                    if c.idx < Character.Gau]):
            log.error("All characters must have Fight as the first command.")
            raise RuntimeError()

        # evidently gogo has to have mimic?
        gogo = [c for c in chr_data.values() if c.idx == Character.Gogo][0]
        if gogo.commands[0] is not Command.Mimic:
            log.error("Gogo must have Mimic as the first command.")
            raise RuntimeError()

    @classmethod
    def package(cls, chr_data):
        # TODO: names
        cls.validate(chr_data)
        raw_data = b""
        for cdata in sorted(chr_data.values(), key=lambda c: c.idx):
            raw_data += bytes(cdata)

        return raw_data

    def __init__(self):
        super().__init__()
        # FIXME: We may need a parent rando to reconfigure this one in the future
        #self._rando = rando
        self.chr_data = {}

    def populate(self, bindata):
        # Gather command data
        self.chr_names = FF6Text._decode(self["chrct_nms"] << bindata, 6)
        #chr_ids = [Character(i) for i in range(len(self.chr_names))]
        # FIXME:
        chr_ids = [Character(i) for i in range(16)]
        chr_data = self["chrct_intl_prprt"] << bindata
        self.chr_data = dict(zip(chr_ids, chr_data))

    def randomize_commands(self, invalid, cmd_mgr, shuffle_cmds=False, replace_cmds=False,
                           unique_xmagic=True, force_only_cmd=None, force_skill_cmd=None,
                           **kwargs):
        # populate pool
        cmd_pool = {Command(c.idx) for n, c in cmd_mgr.cmd_data.items() if c.idx not in invalid}
        xmagic_used = False

        for char in self.chr_data.values():
            # "fix" Gau
            if shuffle_cmds or replace_cmds and char.idx is Character.Gau:
                char.commands[0] = Command.Fight

            # example: this is used in "metronome" in BC to set skill to Magitek
            if force_skill_cmd is not None:
                char.commands = [Command.Fight, Command(force_skill_cmd),
                                 Command.Magic, Command.Item]
                continue

            # Force the menu to have only one command (I think?)
            # TODO: why does BC only fill the last three slots?
            if force_only_cmd is not None:
                char.commands = [char.command[0], Command.Nothing,
                                 Command.Nothing, Command(force_only_cmd)]
                continue

            # Handle "special characters differently
            if char.idx > Character.Gau:
                char.commands = [char.commands[0], Command.Nothing,
                                 Command.Nothing, char.commands[-1]]
                continue

            # zero out X-magic probability if we have and we're unique
            xmagic_prob = kwargs.pop("xmagic_prob", 0.5) \
                if not (xmagic_used and unique_xmagic) else 0
            char.commands[1:] = cmd_mgr._get_random_commands(cmd_pool,
                                                             xmagic_prob=xmagic_prob,
                                                             **kwargs)
            xmagic_used |= Command.X_Magic

            log.info(f"New commands for {str(Character(char.idx))}: {char.commands}")

        tasks = [WriteBytes(self["chrct_intl_prprt"], self.package(self.chr_data))]
        return tasks + self._handle_morph_changes()

    def _handle_morph_changes(self):
        for c in self.chr_data.values():
            if Command.Morph in c.commands:
                return [WriteBytes(self._MORPH_MEMBLK, bytes([0xC9, c.idx]))]
        return []

class CharacterManager(FF6ProgressiveRandomizer):
    def read_characters(self):
        self.scan_memory()
        self.chr_data = {
            Character(ci): CharData.init_from_slot(ci, None, self._ram)
            for ci in range(16)
        }
        self.read_party_data()

    def read_party_data(self):
        self.scan_memory()
        self.party_data = [*map(PartyFlags, self._ram[0x1850:0x1860])]

    def find_empty_slot(self, party_id=1):
        party_id = PartyFlags(1 << (party_id - 1))
        slots = {0, 1, 2, 3}
        for pdata in self.party_data:
            if pdata & party_id:
                slots.remove(pdata & 0x18)

        return slots.pop()

    def add_actor_to_party(self, actor_index, slot=None, party_flags=None, party_id=1):
        party_flags = party_flags or self.party_data[actor_index]
        party_flags |= PartyFlags.PARTY_1 << (party_id - 1)
        party_flags |= (slot or self.find_empty_slot(party_id)) << 3
        log.info(f"Adding to party with with flags {str(party_flags)}")
        self.write_memory(0x1850 + actor_index, bytes([party_flags]))
        return party_flags

    def first_available_slot(self):
        for ci in sorted(self.chr_data):
            if self.chr_data[ci] is None:
                return ci

        raise RuntimeError("No available uninitialized actor slots.")

    def init_char(self, new_char=BaseTmplt(), actor_idx=None, enable=True, insert=False,
                  party_flags=PartyFlags.VISIBLE, party_id=1):

        new_char.actor_index = actor_idx or self.first_available_slot()
        log.info(f"Generating character data for actor slot {new_char.actor_index}")
        log.info(new_char)
        #new_char.esper = 1
        #rando.write_memory(0x1600 + 37 * 2, bytes(new_char))
        self.chr_data[new_char.actor_index] = new_char

        if enable:
            party_flags |= PartyFlags.ENABLED
        log.info(f"Generating with flags {str(party_flags)}")

        if insert is not False:
            party_flags = self.add_actor_to_party(new_char.actor_index, slot=insert,
                                                  party_flags=party_flags, party_id=party_id)
        log.info(f"Generating with flags {str(party_flags)}")
        self.write_memory(0x1850 + new_char.actor_index, bytes([party_flags]))

    def format_team(self, suppress_empty=True):
        team = "\n".join([str(char) for actor, char in self.chr_data.items()
                          if not (suppress_empty and char is None)])
        return team

    def write_character_info(self):
        #self.write_memory(0x1600, bytes(self))
        for ci, chr in self.chr_data.items():
            if chr is None:
                continue
            data = bytes(chr)
            st = 0x1600 + ci * len(data)
            log.debug(f"Writing the following ({len(data)} bytes) to {st:x}")
            #log.debug(str(chr))
            self.write_memory(st, data)

    def __bytes__(self):
        return b"".join([bytes(self.chr_data[ci]) for ci in sorted(self.chr_data)])

if __name__ == "__main__":
    mngr = FF6CharacterManager()
    # Print out some stuff from args
