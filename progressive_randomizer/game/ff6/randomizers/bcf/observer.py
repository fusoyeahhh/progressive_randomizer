import sys
import os
import time
import pprint
import json
import datetime
from collections import Counter

import logging
logging.basicConfig(stream=sys.stdout, level=logging.INFO)
log = logging.getLogger()

from ...randomizers import FF6ProgressiveRandomizer
from ...data import Character, Status

from .data import InfoProvider, _check_term
from ..common import PlayState

# TODO: Parse battle RAM description and generate observer

# or bridge?
class BattleState(FF6ProgressiveRandomizer):
    def __init__(self):
        super().__init__()
        self._eform_id = None
        self._party_status = None
        self._enemy_status = None

        self._pdeaths = Counter()
        self._pkills = Counter()

    def init_battle(self):
        # Calling properties stores the value
        self.party_status
        self.enemy_status

    def process_battle_change(self, on_player_kill=None, on_player_death=None):
        chars = self.actors
        log.debug(f"Actors: {self.actors}")

        stat_change = self.party_status_changed
        for i, stat_change in enumerate(stat_change):
            if stat_change is Status.NoStatus:
                continue
            actor = chars[2 * i]
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
                actor = chars[targ]
                self._pkills[actor] += 1
                if on_player_kill is not None:
                    on_player_kill(actor)

    @property
    def actors(self):
        actor_map = {}
        slots = self.read_ram(0x3000, 0x3010)
        for i, char in enumerate(Character):
            cslot = slots[i]
            # Strange mapping here
            if cslot < 0xF:
                actor_map[cslot] = char
            elif cslot != 0xFF:
                raise ValueError("Invalid slot designation.")
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
        slots = [Character(cslot)
                 for cslot in self.read_ram(0x3000, 0x3010)
                 if cslot != 0xFF]
        return slots

    @property
    def party_status(self):
        self._party_status = [Status(stat)
                              for stat in self.read_ram(0x2E98, 0x2E98 + 8, width=2)]
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


class GameState(FF6ProgressiveRandomizer):
    def __init__(self):
        super().__init__()
        self.play_state = None
        self._map_id, self._music_id = None, None

    @property
    def party(self):
        party_check = [*self.read_ram(0x3000, 0x3010)]
        chars = {slot: Character(i) for i, slot in enumerate(party_check) if slot != 0xFF}
        return chars

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
        miab_id = self.read_ram(0x00D0)
        return miab_id == 0x0B90

    @property
    def map_id(self):
        self._map_id = self.read_ram(0x1F64) & 0x1FF
        return self._map_id

    @property
    def map_changed(self):
        prev = self._map_id
        return prev != self.map_id

    @property
    def music_id(self):
        # Music id detection, from Myriachan
        # "if 0x1304 is 0x10, 0x11, 0x14, or 0x15, then 0x1305 should contain a song ID."
        mbit = self.read_ram(0x1304)
        if mbit == 0x10 or mbit == 0x11 or mbit == 0x14 or mbit == 0x15:
            self._music_id = self.read_ram(0x1305)
        return self._music_id

    @property
    def music_changed(self):
        prev = self._music_id
        return prev != self.music_id

    @property
    def game_state(self):
        self.read_game_state()
        return self.play_state

    @property
    def game_state_changed(self):
        prev = self.play_state
        return self.play_state != self.game_state

    def read_game_state(self):
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

    def _battle_check(self):
        # probably intro scene or something similar
        _battle_check = self.read_ram(0x3000, 0x3010)
        if set(_battle_check) == {0}:
            return False
        log.debug(f"_battle_check {_battle_check}")
        char_slots = [i for i in _battle_check if i != 0xFF]
        return len(char_slots) > 0 and all([i <= 0xF for i in char_slots])

    def _menu_check(self):
        s1, s2, s3 = self.read_ram(0x91, 0x97, width=2)
        sram_chksum = self.read_ram(0x1FFE, 0x2000, width=2)

        save_screen = sram_chksum in {s1, s2, s3}
        log.debug(f"sram checksum: {sram_chksum} {s1} {s2} {s3}: {save_screen}")

        p1, p2, p3, p4 = self.read_ram(0x6D, 0x75, width=2)

        slot_ptrs = any([p >= 0x1600 and p < 0x1850 for p in [p1, p2, p3, p4]])
        log.debug(f"slot ptrs: {p1} {p2} {p3} {p4}: {slot_ptrs}")

        return save_screen or slot_ptrs

    def _field_check(self):
        on_world_map = self.map_id in {0, 1}
        log.debug(f"on world map: {self.map_id}, {on_world_map}")
        battle_actor_check = self.read_ram(0x3000, 0x3010)
        log.debug(f"battle actor check: {battle_actor_check}")
        return set(battle_actor_check) == {0xFF} or on_world_map

class BCFObserver(FF6ProgressiveRandomizer):
    # Default starting points
    _DEFAULT_START = 1000

    @classmethod
    def generate_default_config(cls, fname=None, **kwargs):
        opts = {
            "spoiler": None,
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

    def __init__(self, romfile_path=None):
        self._rom_path = romfile_path

        # FIXME: Move these back into kwargs
        #self.load_config(config)
        self.reset()

    def reset(self):
        self._spoiler_log = None
        self._remonstrate_log = None
        self._flags, self._seed = None, None

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
        self._remonstrate_log = opts.pop("remonsterate", None)
        self._provider = InfoProvider(self._spoiler_log, self._remonstrate_log)

        # If the flags are listed in the configuration file, they override all else
        self._flags = opts.pop("flags", None)
        # Same for seed
        self._seed = opts.pop("seed", None)
        # Season label is used for archival and tracking purposes
        self._season_label = opts.pop("season", None)
        # Where we keep our checkpointed user and game data
        self._chkpt_dir = opts.pop("checkpoint_directory", "./checkpoint/")

    def _can_change_area(self, area_id):
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
        return self._provider.lookup_boss(by_id=self._context.get("boss", eform_id)) is not None

    def set_context(self, music=None, area=None, boss=None):
        log.info(f"Setting new context: {music} {area} {boss}")

        if self._can_change_area(area):
            self._context["area"] = self._context.get("area", None) if area is None else area
        if self._can_change_boss(boss):
            self._context["boss"] = self._context.get("boss", None) if boss is None else boss
        self._context["music"] = self._context.get("music", None) if music is None else music

        log.debug(self._context)
        return self._context

    @property
    def context(self):
        # Translate to English names, where available
        _music_info = self._provider.lookup_music(by_id=self._context.get("music", None))
        _area_info = self._provider.lookup_map(by_id=self._context.get("area", None))
        #logging.info(f"Area: {self._context.get('area', None)} => {_area_info}")
        _boss_info = self._provider.lookup_boss(by_id=self._context.get("boss", None))
        ctx = {
            "music": _music_info if _music_info is None else _music_info["name"],
            "area": _area_info if _area_info is None else _area_info["scoring_area"],
            "boss": _boss_info if _boss_info is None else _boss_info["Boss"]
        }
        return ctx

    def process_change(self):
        if self._game_state is None:
            log.info("Game state halted. No changes will be processed.")
            return

        if self._game_state.music_changed:
            self.set_context(music=self._game_state.music_id)
        if self._game_state.map_changed:
            self.set_context(area=self._game_state.map_id)

        if self._game_state.game_state_changed \
            and self._game_state.play_state is PlayState.IN_BATTLE:
            self._battle_state = BattleState()
            self._battle_state.init_battle()

            # TODO: check for boss
            self.set_context(boss=self._battle_state.eform_id)

            if self._game_state.is_miab:
                self.handle_miab()
        elif self._game_state.play_state is not PlayState.IN_BATTLE:
            if self._battle_state is not None:
                print(self._battle_state._pkills)
                print(self._battle_state._pdeaths)
                self._battle_state = None

        if self._battle_state is not None:
            # we do this immediately with call backs
            self._battle_state.process_battle_change(self.score_pkill,
                                                     self.score_pdeath)

        if self._game_state.is_gameover:
            self.handle_gameover()

    def halt(self, end_of_game=False):
        if end_of_game:
            self._sell_all()
            # Possibly do a report?
            self.serialize(pth=self._chkpt_dir, season_update=True)
        else:
            self.serialize(pth=self._chkpt_dir)
        self._game_state = None

    def handle_gameover(self):
        self.score_gameover()
        self.halt(end_of_game=True)

    def score_gameover(self, area=None):
        area = self._provider.lookup_map(by_id=area or self._context["area"], get_area=True)

        for name, scoring in self._users.items():
            if scoring.get("area", None) != area["Area"]:
                continue
            score_diff = area["Gameover"]
            scoring["score"] += area["Gameover"]
            self._msg_buf["scoring"].append(f"{name} +{score_diff}")

        self._msg_buf["events"].append(f"gameover: {area['Area']}")

    def score_miab(self, area=None):
        area = self._provider.lookup_map(by_id=area or self._context["area"], get_area=True)

        for name, scoring in self._users.items():
            if scoring.get("area", None) != area["Area"]:
                continue
            score_diff = area["MIAB"]
            scoring["score"] += area["MIAB"]
            self._msg_buf["scoring"].append(f"{name} +{score_diff}")

        self._msg_buf["events"].append(f"miab: {area['Area']}")

    def score_pkill(self, actor, n=1, eform_id=None):
        actor = Character(actor)
        log.debug(f"Scoring pkill {actor.name}")

        current_form = self._provider.lookup_boss(by_id=eform_id or self._battle_state.eform_id)
        char = self._provider.lookup_char(by_id=actor)
        opt = "Kills Enemy" if current_form is None else "Kills Boss"

        for name, scoring in self._users.items():
            if scoring.get("char", "").lower() != actor.name.lower():
                continue
            score_diff = char[opt] * n
            scoring["score"] += char[opt] * n
            self._msg_buf["scoring"].append(f"{name} +{score_diff}")

        self._msg_buf["events"].append(f"pkill: {actor.name} {n:d} {opt} {eform_id:d}")

    def score_pdeath(self, char, n=1, area=None):
        actor = Character(char)
        area = self._provider.lookup_map(by_id=area or self._context["area"], get_area=True)

        for name, scoring in self._users.items():
            if scoring.get("char", "").lower() != actor.name.lower() \
                or scoring.get("area", None) != area["Area"]:
                continue
            score_diff = area["Kills Character"] * n
            scoring["score"] += area["Kills Character"] * n
            self._msg_buf["scoring"].append(f"{name} +{score_diff}")

        self._msg_buf["events"].append(f"pdeath: {actor.name} {n:d}")

    def register_user(self, user):
        self._users[user] = {"score": self._DEFAULT_START}

    def unregister_user(self, user):
        del self._users[user]

    def check_user(self, user):
        return user in self._users

    def format_user(self, user):
        return " | ".join([f"{k}: {v}"
                         for k, v in self._users[user].items()])

    def whohas(self, item):
        _users = pandas.DataFrame(self._users).T

        # Initial scan
        # FIXME: implement a fuzzy match as well
        found = _users.loc[(_users == item).any(axis=1)]
        if len(found) == 0:
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
        if cost <= inv["score"]:
            inv["score"] -= int(cost)
            inv[cat] = item
            self._msg_buf["events"].append(f"{user} bought {item} ({cat}, {int(cost)})")
        else:
            raise ValueError(f"@{user}: insufficient funds.")

        return cost

    def sell(self, user, cat):
        lookup, info = self._provider._lookups[cat]
        item = self._users[user].pop(cat)
        value = int(info.set_index(lookup).loc[item]["Sell"])

        # Add the sale price back to the score
        self._users[user]["score"] += value

        self._msg_buf["events"].append(f"{user} sold {item} ({cat}, {int(value)})")
        return value

    def _sell_all(self):
        """
        Iterate through the user database and sell all salable items. Generally invoked at the end of a seed.

        :return: None
        """
        for user, inv in self._users.items():
            _inv = inv.copy()
            for cat, item in _inv.items():
                # Omit categories that don't have salable items (e.g. score)
                if cat not in {"char", "area", "boss"}:
                    continue
                try:
                    # We assume the user hasn't somehow managed to buy an item not in the lookup table
                    self.sell(user, cat)
                except Exception as e:
                    logging.error("Problem in sell_all:\n" + str(e) + "\nUser table:\n" + str(_USERS))
            self._users[user] = _inv

            # Clear out the user selections, drop all categories which aren't the score
            self._users[user] = {k: max(v, self._DEFAULT_START)
                                 for k, v in inv.items() if k == "score"}
            logging.info(f"Sold {user}'s items. Current score "
                         f"{self._users[user]['score']}")
        logging.info("Sold all users items.")

    def write_stream_status(self, status_string=None, scoring_file="_scoring.txt"):
        status = " | ".join([f"{cat.capitalize()}: {val}" for cat, val in self.context.items()])
        status = status.replace("Boss: ", "Last enc. boss: ")
        map_id = self._context.get("area", None)
        # Append map info
        map_info = self._provider.lookup_map(map_id)
        if map_info is not None:
            status += f" | Map: ({map_id}), {map_info['name']}"
        # Append party info
        # FIXME: need party aliases
        #party = [f"{name[1:-1]}: {alias}"
                 #for name, alias in bot._last_status.get("party", {}).items() if name.startswith("(")]
        party = [Character(p).name for p in self._game_state.party]
        if party:
            status += " | Party: " + ", ".join(party)

        # Append leaderboard
        leaderboard = sorted(self._users.items(), key=lambda kv: -kv[1].get("score", 0))
        leaderboard = " | ".join([f"{user}: {inv.get('score', None)}"
                                  for user, inv in leaderboard])

        current_time = datetime.datetime.now().strftime("%H:%M:%S")

        last_3 = ""
        events, self._msg_buf["events"] = self._msg_buf["events"][:3], self._msg_buf["events"][3:]
        if len(events) > 0:
            last_3 += f"--- [{current_time}] Last three events:\n" + "\n".join(events)
        score, self._msg_buf["scoring"] = self._msg_buf["scoring"][:3], self._msg_buf["scoring"][3:]
        if len(events) > 0:
            last_3 += f"\n--- [{current_time}] Last three scores:\n" + "\n".join(score)

        if not status_string:
            status_string = status + "\n\n" + leaderboard + "\n\n" + last_3 + "\n"
            status_string = status_string.strip()

        if scoring_file is None:
            log.info(status_string)
            return

        with open(scoring_file, "w") as f:
            print(status_string, file=f, flush=True)
            logging.debug("Wrote specifics to stream status.")
        # Let the message persist for a bit longer
        #bot._last_state_drop = int(time.time())

    def serialize(self, pth="./", season_update=False, online_sync=False):
        """
        Serialize (write to file) several of the vital bookkeeping structures attached to the bot.

        Optionally archive the entire information set to a directory (usually the seed).
        Optionally send checkpoint to trash and reset the bot state.
        Optionally update a season-tracking file with user scores.

        :param pth: path to checkpoint information to
        :param reset: whether or not to reset bot state (default is False)
        :param archive: path to archive the checkpoint (default is None)
        :param season_update: whether or not to update the season scores (default is False)
        :return: None
        """

        from io import StringIO
        import pandas
        import pathlib
        from zipfile import ZipFile
        zfile_name = f"{self._season_label or 'NOSEASON'}.zip"
        pth = pathlib.Path(pth).resolve()
        pth = pth / zfile_name

        write_data = {}

        if season_update:
            season_scoring = None
            sfile = "season_scoring.csv"
            # We may also update the season tracker
            with ZipFile(zfile_name, "r") as src:
                if sfile in src.namelist():
                    season_scoring = src.read(sfile).decode()

            logging.info(f"Adding season tracking information to {sfile}")
            try:
                # Convert the user data into rows of a CSV table
                this_seed = pandas.DataFrame(self._users)
                logging.debug(f"Users: {self._users},\nseed database: {this_seed.T}")
                # Drop everything but the score (the other purchase information is extraneous)
                this_seed = this_seed.T[["score"]].T
                # We alias the score to a unique identifier for each seed
                this_seed.index = [self._seed + "." + self._flags]
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

            if online_sync:
                season.index.name = "Seed Number"
                logging.info("Synching season scores to Google sheet...")
                export_to_gsheet(season.reset_index())
                logging.info("...done")

        prefix = self._flags.replace(' ', '') or "NOFLAGS"
        prefix += "_" + (self._seed or "NOSEED")

        write_data[f"{prefix}_user_data.json"] = json.dumps(self._users, indent=2)

        # Unfortunately, we can't ovewrite in a zipfile, so we have to copy
        import os
        import tempfile
        tmpfile = tempfile.NamedTemporaryFile(delete=False)
        # FIXME: We should convert this to JSON instead
        with ZipFile(zfile_name, "a") as src:
            with ZipFile(tmpfile.name, "a") as zipf:
                for name in set((src.namelist() + list(write_data.keys()))):
                    if name in write_data:
                        zipf.writestr(name, write_data[name])
                    else:
                        zipf.writestr(name, src.read(name))

        tmpfile.close()
        os.unlink(zfile_name)
        os.rename(tmpfile.name, zfile_name)

    def snapshot(self, fname=None):
        self.scan_memory()
        fname = fname or "ram_dump_{int(time.time())}.dat"
        with open(fname, "wb") as fout:
            fout.write(self._ram)