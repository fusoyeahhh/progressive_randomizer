import random
from dataclasses import dataclass, asdict
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
from ...managers.character import CharData

class Action:
    def __init__(self):
        self.rank = None
        self.gp_cost = None

    def __call__(self, rando):
        pass

def poisson(mean=1, exclude_zero=False, nmax=100):
    s = 0
    for n in range(1 if exclude_zero else 0, nmax):
        s += random.expovariate(mean)
        if s > 1:
            break
    return n

class SetAttribute(Action):
    @classmethod
    def generate_random_at_rank(cls, chr, attr=None, boost=None, rank=None):
        # pick an attribute
        attr = random.choice(asdict(chr))
        boost = poisson(1, exclude_zero=True)
        old_value = getattr(chr, attr)
        return cls(chr.actor_id, attr, old_value + boost)

    def __init__(self, actor, attr, value):
        super().__init__()
        self.actor = actor
        self.attr = attr
        self.value = value

    def __call__(self, rando):
        rando.read_character_info()
        log.info(f"set attribute: {self.actor} : {self.attr} -> {self.value}")
        rando.set_actor_attribute(self.actor, self.attr, self.value)

    def __str__(self):
        return f"Set attribute {self.attr} to {self.value} for {self.actor}"

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

import enum
class PlayState(enum.IntEnum):
    DISCONNECTED = 0
    CONNECTED = enum.auto()
    IN_BATTLE = enum.auto()
    ON_FIELD = enum.auto()
    IN_MENU = enum.auto()

import hashlib
class ProgressiveRandomizer(FF6ProgressiveRandomizer):
    def __init__(self):
        self.play_state = PlayState.DISCONNECTED
        super().__init__()

        self.mode = None
        self.moderator = GameModerator()

        self.team = None

        self.check_state()

    def check_state(self):
        log.debug(f"Scanning memory. Current state: {str(self.play_state)}")
        self.scan_memory()

        if self._menu_check():
            self.play_state = PlayState.IN_MENU
            return

        if self._battle_check():
            self.play_state = PlayState.IN_BATTLE
            return

        if self._field_check():
            self.play_state = PlayState.ON_FIELD
            return

        if self._bridge.ping(visual=False):
            self.play_state = PlayState.CONNECTED
            return

        self.play_state = PlayState.DISCONNECTED

    def _field_check(self):
        """
        On non-world maps, RAM between 0x3000-0x3010 == 0xff. On the world map, we check the map id.
        """
        #self._ram[0x1F60:0x1F70] = self._bridge.read_memory(0x1F60, 0x1F70)
        #self._ram[0x3000:0x3010] = self._bridge.read_memory(0x3000, 0x3010)
        # Only true on non-world maps
        map_id = int.from_bytes(self._ram[0x1F64:0x1F66], byteorder="little") & 0x1FF
        on_world_map = map_id in {0, 1}
        #log.debug(f"map id: {map_id:x}")
        #log.debug(f"_field_check {self._ram[0x3000:0x3010]}")
        return set(self._ram[0x3000:0x3010]) == {0xFF} or on_world_map

    def _battle_check(self):
        #self._ram[0x3000:0x3010] = self._bridge.read_memory(0x3000, 0x3010)
        # probably intro scene or something similar
        if set(self._ram[0x3000:0x3010]) == {0}:
            return False
        #log.info(f"_battle_check {self._ram[0x3000:0x3010]}")
        char_slots = [i for i in self._ram[0x3000:0x3010] if i != 0xFF]
        return len(char_slots) > 0 and all([i <= 0xF for i in char_slots])
    
    def _menu_check(self):
        #self._ram[0x0:0xFF] = self._bridge.read_memory(0x0, 0xFF)
        sram_checksums = self._ram[0x91:0x97]
        s1 = int.from_bytes(sram_checksums[:2], byteorder="little")
        s2 = int.from_bytes(sram_checksums[2:4], byteorder="little")
        s3 = int.from_bytes(sram_checksums[4:6], byteorder="little")
        sram_chksum = int.from_bytes(self._ram[0x1FFE:0x2000], byteorder="little")
        save_screen = sram_chksum in {s1, s2, s3}
        #log.debug(f"{sram_chksum} {s1} {s2} {s3}: {save_screen}")

        p1 = int.from_bytes(self._ram[0x6D:0x70], byteorder="little")
        p2 = int.from_bytes(self._ram[0x70:0x72], byteorder="little")
        p3 = int.from_bytes(self._ram[0x72:0x74], byteorder="little")
        p4 = int.from_bytes(self._ram[0x74:0x76], byteorder="little")

        slot_ptrs = any([p >= 0x1600 and p < 0x1850 for p in [p1, p2, p3, p4]])
        #log.debug(f"{p1} {p2} {p3} {p4}: {slot_ptrs}")

        return save_screen or slot_ptrs

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

    def manage_event_flags(self):
        pass

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
            state = self.play_state
            self.check_state()
            if self.play_state != state:
                log.info(f"{str(state)} -> {str(self.play_state)}")

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
