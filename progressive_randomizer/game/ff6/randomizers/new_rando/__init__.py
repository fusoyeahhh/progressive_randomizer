import logging
log = logging.getLogger()

from ...components import (
    FF6Text,
    FF6CharacterTable,
    FF6SRAM,
    FF6BattleRAM,
    ButtonPressed,
    FF6DataTable,
)
from ... import data as flag_data
from .. import FF6ProgressiveRandomizer

from dataclasses import dataclass

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

    def __bytes__(self):
        return bytes([self.actor_index, self.graphic_index]) + \
            FF6Text._encode(self.actor_name) + \
            bytes([self.level]) + \
            bytes(self.hp) + bytes(self.mp) + \
            self.exp.to_bytes(3, byteorder="little") + \
            bytes([int(self.status_1), int(self.status_4) >> 24]) + \
            bytes(self.commands)

    @classmethod
    def decode(cls, data):
        return {
            "actor_index": data[0],
            "graphic_index": data[1],
            "actor_name": FF6Text._decode(data[2:8]),
            "level": data[8],
            "hp": cls.HPMP.from_bytes(data[9:13]),
            "mp": cls.HPMP.from_bytes(data[13:17]),
            "exp": int.from_bytes(data[17:20], byteorder="little"),
            "status_1": flag_data.Status(data[21]),
            "status_4": flag_data.Status(data[22] << 24),
            "commands": [flag_data.Command(cmd) for cmd in data[22:26]],
        }

    @classmethod
    def init_from_slot(cls, slot, bindata, ramdata):
        assert slot >= 0 and slot <= 16
        #romdata = FF6CharacterTable().read(bindata)
        charblk = FF6SRAM()._blocks["section_0x1600_0x1850"]

        cdata = FF6DataTable.from_super(charblk, 37)

        raw_data = cdata.dereference(ramdata)
        if raw_data[slot][0] >= 16:
            log.warning(f"Character in slot {slot} appears to not be initialized yet.")
            return None
        return cls(**cls.decode(raw_data[slot]))

class Action:
    def __init__(self):
        pass

    def __call__(self, rando):
        pass

class SetAttribute(Action):
    def __init__(self, actor, attr, value):
        super().__init__()
        self.actor = actor
        self.attr = attr
        self.value = value

    def __call__(self, rando):
        rando.read_character_info()
        rando.set_actor_attribute(self.actor, self.attr, self.value)

    def __str__(self):
        return f"Set attribute {self.attr} to {self.value} for {self.actor}?"

class GiveItem(Action):
    def __init__(self, item_id, quant=1):
        super().__init__()
        self.item_id = item_id

class ChangeClass(Action):
    def __init__(self, cls):
        super().__init__()

class GameModerator:
    def __init__(self):
        pass

    def generate_reward(self):
        pass


class ProgressiveRandomizer(FF6ProgressiveRandomizer):
    def __init__(self):
        super().__init__()
        self.mode = None
        self.moderator = GameModerator()

        self.team = None

    def check_inputs(self):
        self.scan_memory(0x7E0000, 0x7E0000 + 16)
        return FF6BattleRAM.parse_header_block(self._ram[:0x10])

    def read_character_info(self):
        # TODO: only scan pertinent areas
        self.scan_memory()
        self.team = [CharData.init_from_slot(i, None, self._ram)
                     for i in range(16)]
        # drop uninitialized characters
        self.team = {t.actor_index: t for t in self.team if t is not None}

    def write_character_info(self):
        data = b""
        for i in range(16):
            d = bytes(self.team.get(i, b"\xff" + b"\x00" * 36)).ljust(37, b"\x00")
            data += d

        self.write_memory(0x1600, data)

    def set_actor_attribute(self, slot, attribute, value):
        char = self.team[slot]
        setattr(char, attribute, value)
        self.write_character_info()

    def _run_loop(self):
        accept = None
        log.info("Starting game loop")
        while True:
            """
            if not self._bridge.ping():
                raise RuntimeError("Lost connection to I/O bridge.")
            else:
                log.debug("Connection still alive.")
            """

            if self.mode is None and accept is None:
                #self.moderator.generate_reward()
                reward = SetAttribute(0, "level", 20)
                self.mode = "query"
                self._bridge.display_msg(str(reward))

            info = self.check_inputs()
            if info["buttons_this_frame"] != ButtonPressed.NoButton:
                log.debug(info["buttons_this_frame"])

            input_mode = info["buttons_this_frame"] & ButtonPressed.L
            if self.mode == "query" and input_mode:
                if info["buttons_this_frame"] & ButtonPressed.A:
                    accept = True
                elif info["buttons_this_frame"] & ButtonPressed.B:
                    accept = False

            if self.mode == "query" and accept is not None:
                if accept:
                    log.info("Player accepted.")
                    self._bridge.display_msg("Accepted!")
                    reward(self)
                else:
                    log.info("Player rejected.")
                    self._bridge.display_msg("Rejected!")
                accept = None

            # self.dump()
