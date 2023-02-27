import sys
import os
import time
import pprint
import pathlib
import json
import datetime
import textwrap
import random
from collections import Counter
from io import StringIO
from zipfile import ZipFile
from dataclasses import dataclass, asdict, field

import pandas

import logging
logging.basicConfig(stream=sys.stdout, level=logging.INFO)
log = logging.getLogger()

from ...data import Character, Status
from ...components import FF6Text
from ...randomizers import FF6ProgressiveRandomizer

from .data import InfoProvider, _check_term
from ..common import PlayState

from .utils import infer_spoiler_file_name
try:
    from .utils import export_to_gsheet
except ImportError:
    log.warning("`gspread` and related libraries not found, "
                "will not be able to sync to online sheets.")
    export_to_gsheet = None

# TODO: Parse battle RAM description and generate observer

# or bridge?
class BattleState(FF6ProgressiveRandomizer):
    def __init__(self):
        super().__init__()
        self._eform_id = None
        self._is_boss = False
        self._actors = {}
        self._party_status = None
        self._enemy_status = None

        self._pdeaths = Counter()
        self._pkills = Counter()

    def init_battle(self, boss_check=None):
        # Calling properties stores the value
        self.party_status
        self.enemy_status

        if boss_check is not None:
            self._is_boss = boss_check(self.eform_id)

    def process_battle_change(self, on_player_kill=None, on_player_death=None):
        # FIXME: This should detect game state and abort outside of battle
        chars = self.actors
        log.debug(f"Actors: {self.actors}")

        if len(chars) == 0:
            log.warning("Actor listing is empty. This will not end well.")

        stat_change = self.party_status_changed
        for i, stat_change in enumerate(stat_change):
            if stat_change is Status.NoStatus:
                continue

            try:
                # FIXME: this might need to detect actor 0xFF (guest)
                actor = chars[2 * i]
            except KeyError as e:
                log.info(f"Party status:\n{str(self.party_status)}")
                log.info(f"Party status change:\n{str(stat_change)}")
                log.error(f"Lookup for character slot {2 * i} failed. "
                          f"Known actors are: {chars}")
                raise e

            if stat_change & (Status.Death | Status.Zombie | Status.Petrify):
                self._pdeaths[actor] += 1
                if on_player_death is not None:
                    on_player_death(actor)

        # FIXME: does this discard spell targeting?
        last_target = [*self.read_ram(0x3298, 0x32A4)][::2]
        stat_change = self.enemy_status_changed
        for i, (change, targ) in enumerate(zip(stat_change, last_target)):
            if change is Status.NoStatus:
                continue

            if (change & (Status.Death | Status.Zombie | Status.Petrify)) \
                    and targ != 0xFF:
                actor = chars.get(targ, "guest")
                self._pkills[actor] += 1
                # FIXME: if we want to score guests, we have to add
                # special logic into the pkill tracker and a row in the
                # character score sheet
                if on_player_kill is not None and actor != "guest":
                    on_player_kill(actor)
                elif actor == "guest":
                    log.info("Ignoring kill for guest character.")

    @property
    def actors(self):
        actor_map = {}
        slots = self.read_ram(0x3000, 0x3010)
        for i, char in enumerate(Character):
            cslot = slots[i]
            # Strange mapping here
            if cslot <= 0xF:
                actor_map[cslot] = char
            elif cslot != 0xFF:
                raise ValueError(f"Invalid slot designation: {i} -> {cslot}.")
        self._actors = actor_map
        return actor_map

    @property
    def last_targetted(self):
        return [*self.read_ram(0x3290, 0x3294)]

    @property
    def eform_id(self):
        self._eform_id = self.read_ram(0x11E0, 0x11E2, width=2)
        return self._eform_id

    @property
    def battle_party(self):
        return [cid for cid in self.read_ram(0x3ED8, 0x3EE0)[::2]]

    @property
    def party_status(self):
        self._party_status = [Status(stat) for stat in self.read_ram(0x2E98, 0x2E98 + 8, width=2)]
        return self._party_status

    @property
    def party_status_changed(self):
        prev = self._party_status[:]
        return [(s1 & ~s2) for s1, s2 in zip(self.party_status, prev)]

    @property
    def enemy_status(self):
        self._enemy_status = [Status(stat)
                              for stat in self.read_ram(0x3EEC, 0x3EEC + 12, width=2)]
        return self._enemy_status

    @property
    def enemy_status_changed(self):
        prev = self._enemy_status[:]
        return [(s1 & ~s2) for s1, s2 in zip(self.enemy_status, prev)]

    def __str__(self):
        pstatus = [p.name for p in self._party_status] + ["", ""]
        estatus = [e.name for e in self._enemy_status]
        statuses = "\t\t\n".join([f"{a} {b}" for a, b in zip(estatus, pstatus)])
        return textwrap.dedent(f"""
        Actors: {self._actors}
        Formation ID: {self._eform_id} | Boss: {self._is_boss}
        Party deaths: {self._pdeaths}
        Party kills: {self._pkills}
        Party status | Enemy status:
        {statuses}
        """)

class GameState(FF6ProgressiveRandomizer):
    def __init__(self):
        super().__init__()
        self.play_state = None
        self._map_id, self._music_id = None, None

        self._last_known_party = {}

    @property
    def party(self):
        party_check = [*self.read_ram(0x3000, 0x3010)]
        chars = {slot: Character(i) for i, slot in enumerate(party_check) if slot != 0xFF}
        return chars

    @property
    def party_names(self):
        return self._last_known_party

    @property
    def on_veldt(self):
        # Another from Myriachan
        return self.read_ram(0x11F9) & 0x40 == 0x40 and self.map_id == 0

    @property
    def is_gameover(self):
        # Game over detection
        # Another from Myria: "another way to identify game over is reading the 24-bit value at 0x00E5.
        # 0xCCE5C5 is one of the event script pointers for the game over script."
        script_ptr = self.read_ram(0x00E5, 0x00E9, width=4)
        return (script_ptr & 0xFFFFFF) == 0xCCE5C5

    @property
    def is_miab(self):
        # MIAB detection, thanks to Myriachan
        miab_id = self.read_ram(0x00D0, 0x00D2, width=2)
        return miab_id == 0x0B90

    def get_map_id(self, force_update=False):
        _map_id = self.read_ram(0x1F64, 0x1F66, width=2) & 0x1FF
        if force_update or self.play_state is PlayState.ON_FIELD:
            self._map_id = _map_id
            log.debug(f"Map id updated {self._map_id}")
        else:
            log.debug(f"Cannot update map id, not on field.")
        return _map_id

    @property
    def map_id(self):
        return self._map_id

    @property
    def map_changed(self):
        prev = self._map_id
        self.get_map_id()
        log.debug(f"Map id changed? {prev} =?= {self._map_id}")
        return prev != self._map_id

    def read_party_names(self):
        # FIXME: use sram structure
        begin, stride = 0x1602, 37
        slot_names = [FF6Text._decode(self.read_ram(i, i + 6)).strip()
                      for i in range(begin, begin + stride * 16, stride)]
        slots = {char.name: slot_names[int(char)]
                 for char, cslot in zip(Character, self.read_ram(0x3000, 0x3010))
                 if cslot != 0xFF}
        self._last_known_party = slots
        return slots

    def get_music_id(self):
        # Music id detection, from Myriachan
        # "if 0x1304 is 0x10, 0x11, 0x14, or 0x15, then 0x1305 should contain a song ID."
        mbit = self.read_ram(0x1304)
        if mbit == 0x10 or mbit == 0x11 or mbit == 0x14 or mbit == 0x15:
            self._music_id = self.read_ram(0x1305)
        return self._music_id

    @property
    def music_id(self):
        return self._music_id

    @property
    def music_changed(self):
        prev = self._music_id
        self.get_music_id()
        return prev != self.music_id

    @property
    def game_state(self):
        return self.play_state

    @property
    def game_state_changed(self):
        prev = self.play_state
        self.read_game_state()
        return prev != self.play_state

    def read_game_state(self):
        if not self._bridge.ping(visual=False):
            self.play_state = PlayState.DISCONNECTED
            return

        if self._menu_check():
            self.play_state = PlayState.IN_MENU
            return

        if self._battle_check():
            self.play_state = PlayState.IN_BATTLE
            return

        if self._field_check():
            self.play_state = PlayState.ON_FIELD
            return

        self.play_state = PlayState.CONNECTED

    def _battle_check(self):
        # NOTE: This is unable to determine when we've entered
        # a battle with *only* guest characters, field and battle
        # RAM both are filled with 0xFF in the addresses below
        # this can only happen in the Narshe mines multi-party
        # battle sequence
        _battle_check = self.read_ram(0x3000, 0x3010)
        # probably intro scene or something similar
        if set(_battle_check) == {0}:
            return False
        log.debug(f"_battle_check {_battle_check}")
        char_slots = [i for i in _battle_check if i != 0xFF]
        return len(char_slots) > 0 and all([i <= 0xF for i in char_slots])

    def _menu_check(self):
        s1, s2, s3 = self.read_ram(0x91, 0x97, width=2)
        sram_chksum = self.read_ram(0x1FFE, 0x2000, width=2)

        sram_chksum_data = {s1, s2, s3}
        # Zero is a strong, though not definite, indicator that the slot is empty
        sram_chksum_data.discard(0)
        save_screen = sram_chksum in sram_chksum_data
        log.debug(f"sram checksum: {sram_chksum} {s1} {s2} {s3}: {save_screen}")
        p1, p2, p3, p4 = self.read_ram(0x6D, 0x75, width=2)

        slot_ptrs = any([p >= 0x1600 and p < 0x1850 for p in [p1, p2, p3, p4]])
        log.debug(f"slot ptrs: {p1} {p2} {p3} {p4}: {slot_ptrs}")

        return save_screen or slot_ptrs

    def _field_check(self):
        map_id = self.read_ram(0x1F64) & 0x1FF
        on_world_map = map_id in {0, 1}
        log.debug(f"on world map: {map_id}, {on_world_map}")
        battle_actor_check = self.read_ram(0x3000, 0x3010)
        log.debug(f"battle actor check: {battle_actor_check}")
        battle_actor_data_check = self.read_ram(0x3010, 0x3018, width=2)
        battle_actor_data_check = {d for d in battle_actor_data_check if 0x0 <= d <= 250}
        return (len(battle_actor_data_check) == 0 or
                set(battle_actor_check) == {0xFF}) or on_world_map

    def __str__(self):
        return textwrap.dedent(f"""
        Play state: {self.play_state.name}
        music id: {self._music_id}
        map id: {self._map_id}""")

class BCFObserver(FF6ProgressiveRandomizer):
    # This is the name of the event which needs to fire in order
    # for someone to register
    _EVENT_REG_ALLOWED = "Locke is covered by the shop and item menus and Gogo's Status screen"
    # Default starting points
    _DEFAULT_START = 1000

    @dataclass(repr=True)
    class PlayerState:
        score: int = 0
        party: list = field(default_factory=list)
        area: str = None
        boss: str = None

        def has_char(self, c):
            return c in self.party

        def drop_cat(self, cat):
            return type(self)(**{k: v for k, v in asdict(self).items() if k != cat})

        def __str__(self):
            drepr = asdict(self)
            drepr["party"] = ", ".join([c.name for c in drepr.get("party", [])])
            return " | ".join(f"{k}: {v}" for k, v in drepr.items())

    @classmethod
    def generate_default_config(cls, fname=None, **kwargs):
        opts = {
            "spoiler": None,
            "no_spoiler_check": False,
            "remonsterate": None,

            "flags": None,
            "seed": None,

            "season": None,
            "checkpoint_directory": "./checkpoint/",
            **kwargs
        }

        if os.path.exists(fname or ""):
            with open(fname, "w") as fout:
                json.dump(opts, fout, indent=2)
        else:
            pprint.pprint(opts)

        return opts

    @classmethod
    def filter_flags(cls, flag_dict):
        _drop = ["Facing", "Pressing"]
        return {k: v for k, v in flag_dict.items()
                if not any([d in k for d in _drop])}

    def __init__(self, romfile_path=None):
        super().__init__()
        self._rom_path = romfile_path

        # FIXME: Move these back into kwargs
        #self.load_config(config)
        self.reset()

    def reset(self):
        self._spoiler_log = None
        self._remonstrate_log = None
        self._flags, self._seed = None, None

        self._season_label = "NOSEASON"

        self._users = {}
        self._context = {}
        self._msg_buf = {
            "scoring": [],
            "events": [],
        }

        self._provider = InfoProvider()

        self._game_state = GameState()
        self._battle_state = None

    def load_config(self, config):
        with open(config, "r") as fin:
            opts = json.load(fin)

        # Optional mappings derived from spoiler
        self._spoiler_log = opts.pop("spoiler", None)
        if self._spoiler_log is None and not opts.get("no_spoiler_check", False):
            log.info(f"Checking for spoiler in {os.getcwd()}")
            self._spoiler_log = infer_spoiler_file_name()
        log.info(f"Spoiler log: {self._spoiler_log}")

        self._remonstrate_log = opts.pop("remonsterate", None)

        self._provider = InfoProvider(self._spoiler_log, self._remonstrate_log)

        # If the flags are listed in the configuration file, they override all else
        self._flags = opts.pop("flags", None)
        # Same for seed
        self._seed = opts.pop("seed", None)
        # Season label is used for archival and tracking purposes
        self._season_label = opts.pop("season", self._season_label)
        # Where we keep our checkpointed user and game data
        self._chkpt_dir = opts.pop("checkpoint_directory", "./checkpoint/")

    def _can_purchase_area(self, item):
        return self.context["area"] != item

    def _can_purchase_boss(self, item):
        return self.context["boss"] != item

    def _can_purchase_char(self, user, char):
        return not user.has_char(char) and len(user.party) < 4

    def _can_change_area(self, area_id):
        #if self._game_state is not None and self._game_state.play_state is not PlayState.ON_FIELD:
            #logging.info("Attempting to change maps outside of the field, ignoring.")
            #return False
        if area_id == 5:
            # We don't change the context if on this map, since it can indicate a gameover
            logging.info("Map id 5 detected, not changing area.")
            return False
        elif area_id == 89:
            # South Figaro basement split map
            # FIXME: There is assuredly more of these, so they should be captured in a function
            logging.info("Map id 89 (SF basement) detected, not changing area.")
            return False

        # This map id exists, but is not mapped to an area
        # FIXME: This shouldn't be needed once we're set on the area mappings
        #_area_info = self._provider.lookup_map(by_id=self._context.get("area", None))
        #if _area_info is None:
            #return False
        return True

    def _can_change_boss(self, eform_id=None):
        return self._provider.lookup_boss(by_id=eform_id) is not None

    def set_context(self, music=None, area=None, boss=None, force=False):
        log.debug(f"Attempting to set new value in context (None is no change):\n"
                  f"music: {music} area: {area} boss: {boss}")

        if force or self._can_change_area(area):
            self._context["area"] = self._context.get("area", None) if area is None else area
        if force or self._can_change_boss(boss):
            self._context["boss"] = self._context.get("boss", None) if boss is None else boss
        self._context["music"] = self._context.get("music", None) if music is None else music

        log.debug(self._context)
        return self._context

    @property
    def context(self):
        # Translate to English names, where available
        _music_id = self._context.get("music", None)
        _music_info = self._provider.lookup_music(by_id=_music_id)
        _area_id = self._context.get("area", None)
        _area_info = self._provider.lookup_map(by_id=_area_id)
        _boss_id = self._context.get("boss", None)
        _boss_info = self._provider.lookup_boss(by_id=self._context.get("boss", None))
        ctx = {
            "music": _music_id if _music_info is None else _music_info["new"],
            "area": _area_id if _area_info is None else _area_info["scoring_area"],
            "boss": _boss_id if _boss_info is None else _boss_info["Boss"]
        }
        return ctx

    @property
    def game_state_valid(self):
        return self._game_state.play_state in \
            {PlayState.CONNECTED, PlayState.IN_BATTLE, PlayState.ON_FIELD, PlayState.IN_MENU}

    @property
    def in_battle(self):
        return self._game_state.play_state is PlayState.IN_BATTLE

    def _can_register(self):
        return not self.event_flags[self._EVENT_REG_ALLOWED]

    def process_change(self):
        if self._game_state is None:
            log.info("Game state halted. No changes will be processed.")
            return

        if self._game_state.play_state is not None:
            log.debug(f"Play state: {self._game_state.play_state.name}")
        gs_changed = self._game_state.game_state_changed
        if gs_changed:
            logging.info(f"Play state -> {self._game_state.game_state.name}")

        if self._game_state.play_state is PlayState.DISCONNECTED:
            log.warn("Observer appears to be disconnected, cannot process changes.")
            return

        event_flags = self.filter_flags(self._event_flags) or {}
        if self.event_flags_changed:
            new_flags = self.filter_flags(self.event_flags)
            for flag in event_flags:
                if new_flags[flag] != event_flags[flag]:
                    log.info(f"Event flag set: {flag} -> {new_flags[flag]}")
            log.debug(f"Total events set: {sum(new_flags.values())}")

        #log.info(self._game_state.music_id)
        if self._game_state.music_changed:
            log.info(f"Music changed -> {self._game_state.music_id}")
            self.set_context(music=self._game_state.music_id)
        #log.info(self._game_state.map_id)
        if self._game_state.map_changed:
            log.info(f"Map changed -> {self._game_state.map_id}")
            self.set_context(area=self._game_state.map_id)

        if self.in_battle:
            if self._battle_state is None:
                self._battle_state = BattleState()
                self._battle_state.init_battle()
                logging.info(f"Starting new battle: {self._battle_state.eform_id}")

                # Take the opportunity to update the party names
                self._game_state.read_party_names()

                # TODO: check for boss
                self.set_context(boss=self._battle_state.eform_id)

                if self._game_state.is_miab:
                    self.score_miab()
            else:
                # we do this immediately with call backs
                try:
                    self._battle_state.process_battle_change(self.score_pkill,
                                                             self.score_pdeath)
                except KeyError as e:
                    log.error(str(e))
                    log.warning("Caught a bad status during battle checks. "
                                f"Current play state = {self._game_state.play_state.name} "
                                "Ignoring the check this round.")

        elif self._battle_state is not None:
            logging.info(f"Ending battle:\n{str(self._battle_state)}")
            self._battle_state = None

        if self._game_state.is_gameover:
            self.handle_gameover()

    def monitor(self, time_limit=None, query_rate=1):
        time_limit = time_limit or float("inf")
        while time_limit > 0:
            t = time.time()

            self.process_change()
            print(self)

            time.sleep(query_rate)
            time_limit -= time.time() - t

    def __str__(self):
        gstate = str(self._game_state)
        bstate = str(self._battle_state) if self._battle_state else ""
        return gstate + "\n" + bstate

    def halt(self, end_of_game=False, online_sync=False):
        log.info(f"Halting observer, end_of_game={end_of_game}, "
                 f"should sync? {online_sync}")
        if end_of_game:
            self._sell_all()
            # Possibly do a report?
            self.serialize(pth=self._chkpt_dir, season_update=True, online_sync=online_sync)
        else:
            self.serialize(pth=self._chkpt_dir)
        self._game_state = None

    def handle_gameover(self):
        self.score_gameover()
        self.halt(end_of_game=True)

    def score_gameover(self, area=None):
        area = self._provider.lookup_map(by_id=area or self._context["area"], get_area=True)

        for name, scoring in self._users.items():
            if scoring.area != area["Area"]:
                continue
            score_diff = area["Gameover"]
            scoring.score += int(area["Gameover"])
            log.info(f"gameover {name} +{score_diff}")
            self._msg_buf["scoring"].append(f"{name} +{score_diff}")

        log.info(f"gameover: {area['Area']}")
        self._msg_buf["events"].append(f"gameover: {area['Area']}")

    def score_miab(self, area=None):
        area = self._provider.lookup_map(by_id=area or self._context["area"], get_area=True)

        for name, scoring in self._users.items():
            if scoring.area != area["Area"]:
                continue
            score_diff = area["MIAB"]
            scoring.score += int(area["MIAB"])
            log.info(f"miab {name} +{score_diff}")
            self._msg_buf["scoring"].append(f"{name} +{score_diff}")

        log.info(f"miab: {area['Area']}")
        self._msg_buf["events"].append(f"miab: {area['Area']}")

    def score_pkill(self, actor, n=1, eform_id=None):
        actor = Character(actor)
        log.debug(f"Scoring pkill {actor.name}")

        current_form = self._provider.lookup_boss(by_id=eform_id or self._battle_state.eform_id)
        char = self._provider.lookup_char(by_id=actor)
        opt = "Kills Enemy" if current_form is None else "Kills Boss"

        for name, scoring in self._users.items():
            if not scoring.has_char(actor):
                continue
            score_diff = char[opt] * n
            scoring.score += int(char[opt] * n)
            log.info(f"pkill {name} +{score_diff}")
            self._msg_buf["scoring"].append(f"{name} +{score_diff}")

        log.info(f"pkill: {actor.name} {n} {opt} {eform_id}")
        self._msg_buf["events"].append(f"pkill: {actor.name} {n} {opt} {eform_id}")

    def score_pdeath(self, char, n=1, area=None):
        actor = Character(char)
        area = self._provider.lookup_map(by_id=area or self._context["area"], get_area=True)

        for name, scoring in self._users.items():
            if not scoring.has_char(actor):
                continue
            score_diff = area["Kills Character"] * n
            scoring.score += int(area["Kills Character"] * n)
            log.info(f"pdeath {name} +{score_diff}")
            self._msg_buf["scoring"].append(f"{name} +{score_diff}")

        log.info(f"pdeath: {actor.name} {n:d}")
        self._msg_buf["events"].append(f"pdeath: {actor.name} {n:d}")

    def register_user(self, user, only_current_party=True):
        user_data = self.PlayerState(self._DEFAULT_START)

        choices = [c for c in Character if int(c) < 14]
        if only_current_party:
            choices = list(set(choices) & set(self._game_state.party.values()))
            assert len(choices) >= 1, "No party members to choose from in user registration."
        # Everyone gets a free random party member
        pmember = random.choice(choices)
        user_data.party.append(pmember)

        self._users[user] = user_data
        return user_data

    def unregister_user(self, user):
        del self._users[user]

    def check_user(self, user):
        return user in self._users

    def format_user(self, user):
        return str(self._users[user])

    def whohas(self, item):
        found = {"char": [], "area": [], "boss": []}

        # Initial scan
        # FIXME: implement a fuzzy match as well
        for user, inv in self._users.items():
            for cat, _item in asdict(inv).items():
                if cat == "char" and inv.party.has_char(_item):
                    found[cat].append(user)
                elif item == _item:
                    found[cat].append(user)
            
        if sum(map(len, found.values())) == 0:
            return None
        return found

    def buy(self, user, cat, item):
        lookup, info = self._provider._lookups[cat]
        item = _check_term(item, lookup, info, allow_multiple=True)
        if not isinstance(item, str):
            logging.debug(f"Multiple items found for {item}")
            matches = ', '.join(item)
            raise IndexError(f"@{user}: that {cat} selection is invalid. Possible matches: {matches}")

        inv = self._users[user]
        cost = info.set_index(lookup).loc[item]["Cost"]

        if cat == "area" and not self._can_purchase_area(item):
            raise ValueError(f"@{user}: cannot buy the current area.")
        elif cat == "boss" and not self._can_purchase_boss(item):
            raise ValueError(f"@{user}: cannot buy the current boss.")
        elif cat == "char":
            item = [c for c in list(Character) if item.capitalize() == c.name][0]
            if not self._can_purchase_char(inv, item):
                raise ValueError(f"@{user}: cannot buy the character "
                                 f"--- probably either your party is full "
                                 f"or you already have this character in your party.")

        if cost <= inv.score:
            if cat == "char":
                inv.party.append(item)
            else:
                setattr(inv, cat, item)
            inv.score -= int(cost)
            self._msg_buf["events"].append(f"{user} bought {item} ({cat}, {int(cost)})")
        else:
            raise ValueError(f"@{user}: insufficient funds.")

        return cost

    def _sell(self, user, cat, item=None):
        item = item if item is not None else getattr(user, cat)
        lookup, info = self._provider._lookups[cat]
        value = int(info.set_index(lookup).loc[item]["Sell"])
        # Add the sale price back to the score
        user.score += value

        self._msg_buf["events"].append(f"{user} sold {item} ({cat}, {int(value)})")
        return value

    def sell(self, user, cat):
        user_data = self._users[user]

        if cat == "party":
            user_data.party, party = [], user_data.party
            # First party member is free, no sale value
            value = sum([self._sell(user_data, "char", c.name)
                         for c in party[1:]])
            return value

        value = self._sell(user_data, cat)
        self._users[user] = user_data.drop_cat(cat)
        return value

    def _sell_all(self):
        """
        Iterate through the user database and sell all salable items. Generally invoked at the end of a seed.

        :return: None
        """
        for user, inv in self._users.items():
            for cat, item in asdict(inv).items():
                # Omit categories that don't have salable items (e.g. score)
                if cat not in {"char", "area", "boss", "party"}:
                    continue

                try:
                    # We assume the user hasn't somehow managed to buy an item not in the lookup table
                    self.sell(user, cat)
                except Exception as e:
                    logging.error(f"Problem in sell_all:\n{str(e)}\n"
                                  f"User table:\n{pprint.pformat(self._users)}")

            # Clear out the user selections, drop all categories which aren't the score
            self._users[user] = self.PlayerState(score=max(inv.score, self._DEFAULT_START))
            logging.info(f"Sold {user}'s items. Current score "
                         f"{self._users[user].score}")
        logging.info("Sold all users items.")

    def write_stream_status(self, status_string=None, scoring_file="_scoring.txt"):
        if self._game_state is None \
               or self._game_state.play_state is PlayState.DISCONNECTED:
            logging.warn("Cannot write stream status while disconnected.")
            return

        current_time = datetime.datetime.now().strftime("%H:%M:%S")
        pstate = self._game_state.play_state
        pstate = "Unknown" if pstate is None else pstate.name
        status = f"{current_time} | {pstate}\n" 
        status += " | ".join([f"{cat.capitalize()}: {val}" for cat, val in self.context.items()])
        status = status.replace("Boss: ", "Last enc. boss: ")
        map_id = self._context.get("area", None)

        # Append map info
        map_info = self._provider.lookup_map(map_id)
        if map_info is not None:
            status += f" | Map: ({map_id}), {map_info['name']}"

        # Append party info
        party = [f"{name}: {alias}"
                 for name, alias in self._game_state.party_names.items()]
        if party:
            status += " | Party: " + ", ".join(party)

        # Append leaderboard
        leaderboard = sorted(self._users.items(), key=lambda kv: -kv[1].score)
        leaderboard = " | ".join([f"{user}: {inv.score}"
                                  for user, inv in leaderboard])

        last_3 = ""
        events, self._msg_buf["events"] = self._msg_buf["events"][:3], self._msg_buf["events"][3:]
        if len(events) > 0:
            last_3 += f"--- [{current_time}] Last three events:\n" + "\n".join(events)
        score, self._msg_buf["scoring"] = self._msg_buf["scoring"][:3], self._msg_buf["scoring"][3:]
        if len(events) > 0:
            last_3 += f"\n--- [{current_time}] Last three scores:\n" + "\n".join(score)

        battle_status = ""
        if self.in_battle and self._battle_state is not None:
            battle_status = f"{str(self._battle_state)}"

        if not status_string:
            status_string = status + "\n\n" + leaderboard + "\n\n" \
                            + last_3 + "\n" + battle_status
            status_string = status_string.strip()

        if scoring_file is None:
            log.info(status_string)
            return

        with open(scoring_file, "w") as f:
            print(status_string, file=f, flush=True)
            logging.debug("Wrote specifics to stream status.")
        # Let the message persist for a bit longer
        #bot._last_state_drop = int(time.time())

    def unserialize(self, pth="./"):
        zfile_name = f"{self._season_label}.zip"
        pth = pathlib.Path(pth).resolve()
        zfile_name = pth / zfile_name

        if not zfile_name.exists():
            return None

        prefix = (self._flags or "NOFLAGS").replace(' ', '')
        prefix += "_" + (self._seed or "NOSEED")

        user_data_file = f"{prefix}_user_data.json"

        with ZipFile(zfile_name, "r") as src:
            if user_data_file in src.namelist():
                log.info(f"Reading {user_data_file}")
                log.info(pprint.pformat(json.loads(src.read(user_data_file).decode())))
                return [self.PlayerState(**data) for data in
                        json.loads(src.read(user_data_file).decode())]

        return None

    def serialize(self, pth="./", season_update=False, online_sync=False):
        """
        Serialize (write to file) the vital bookkeeping structures attached to the bot.
        Optionally update a season-tracking file with user scores.

        :param pth: path to checkpoint information to
        :param reset: whether or not to reset bot state (default is False)
        :param archive: path to archive the checkpoint (default is None)
        :param season_update: whether or not to update the season scores (default is False)
        :return: None
        """

        zfile_name = f"{self._season_label}.zip"
        pth = pathlib.Path(pth).resolve()
        if not pth.exists():
            os.makedirs(pth)
        zfile_name = pth / zfile_name

        write_data = {}

        user_dict = {k: asdict(v) for k, v in self._users.items()}

        if season_update and len(user_dict) == 0:
            logging.info("Can't update season with no players.")
        elif season_update:
            season_scoring = None
            sfile = "season_scoring.csv"
            # We may also update the season tracker
            with ZipFile(zfile_name, "a") as src:
                if sfile in src.namelist():
                    season_scoring = src.read(sfile).decode()

            logging.info(f"Adding season tracking information to {sfile}")
            try:
                # Convert the user data into rows of a CSV table
                this_seed = pandas.DataFrame(user_dict)
                logging.debug(f"Users: {self._users},\nseed database: {this_seed.T}")
                # Drop everything but the score (the other purchase information is extraneous)
                this_seed = this_seed.T[["score"]].T
                # We alias the score to a unique identifier for each seed
                this_seed.index = [f"{self._seed}.{self._flags}"]
            except KeyError as e:
                logging.error("Encountered error in serializing user scores to update season-long scores. "
                              f"Current user table:\n{self._users}")
                raise e

            if season_scoring is not None:
                logging.info(f"Concatenating new table to {sfile}")
                prev = pandas.read_csv(StringIO(season_scoring)).set_index("index")
                logging.debug(f"Current season has {len(prev)} (possibly including totals) entries.")
                # If the season CSV already exists, we concatenate this seed data to it
                season = pandas.concat((prev, this_seed))
            else:
                logging.info(f"Creating new table at {sfile}")
                # Otherwise, we create a new table
                season = this_seed

            if "Total" in season.index:
                season.drop("Total", inplace=True)
            season.loc["Total"] = season.fillna(0).sum()

            write_data[sfile] = season.reset_index().to_csv(index=False)

            if online_sync and export_to_gsheet:
                season.index.name = "Seed Number"
                logging.info("Synching season scores to Google sheet...")
                export_to_gsheet(season.reset_index())
                logging.info("...done")
            elif online_sync and export_to_gsheet is None:
                logging.warning("Cannot synch season scores, gsheet libraries not available.")

        prefix = (self._flags or "NOFLAGS").replace(' ', '')
        prefix += "_" + (self._seed or "NOSEED")

        write_data[f"{prefix}_user_data.json"] = json.dumps(user_dict, indent=2)

        # Unfortunately, we can't ovewrite in a zipfile, so we have to copy
        tmpfile = str(zfile_name.stem) + ".bkp.zip"
        # FIXME: We should convert this to JSON instead
        with ZipFile(zfile_name, "a") as src:
            with ZipFile(tmpfile, "a") as zipf:
                for name in set((src.namelist() + list(write_data.keys()))):
                    if name in write_data:
                        zipf.writestr(name, write_data[name])
                    else:
                        zipf.writestr(name, src.read(name))

        os.unlink(zfile_name)
        os.rename(tmpfile, zfile_name)

    def snapshot(self, fname=None):
        self.scan_memory()
        fname = fname or "ram_dump_{int(time.time())}.dat"
        with open(fname, "wb") as fout:
            fout.write(self._ram)
