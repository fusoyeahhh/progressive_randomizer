import sys
import os
import pathlib
import glob

import pandas

import logging
logging.basicConfig(stream=sys.stdout, level=logging.INFO)

from . import read

_DATA_PATH = pathlib.Path(__file__).parents[0]

def _check_term(term, lookup, info, space_suppress=True, full=False, allow_multiple=False):
    """
    Generic function to check and look up a term in a given lookup table. Assumes there is exactly one match for the term.

    In general, the matching is lenient in so far as partial matches are allowed:
        "Katana" and "KatanaSoul" will match "Katana Soul" when `space_supress` is True and `full` is False (default)

    :param term: (str) term to match against lookup table
    :param lookup: (str) column in lookup table to perform match on
    :param info: (pandas.DataFrame) lookup table to match against
    :param space_suppress: whether to check variations of the term which do not contain spaces
    :param full: require a full match
    :param allow_multiple: allow (and return) multiple matches
    :return: value in column `lookup` matching key `term` from table `info`
    """
    _term = str(term).replace("(", r"\(").replace(")", r"\)")
    found = info[lookup].str.lower().str.contains(_term.lower())
    found = info.loc[found]

    if space_suppress and len(found) == 0:
        found = info[lookup].str.lower().str.replace(" ", "") == _term.lower().replace(" ", "")
        found = info.loc[found]

    if len(found) > 1:
        found = info[lookup].str.lower() == _term.lower()
        found = info.loc[found]

    logging.debug(f"check_term | Found {len(found)} matches for {term} in {lookup}")
    if len(found) == 0:
        raise KeyError(f"No matches found for {term} in {lookup}")
    if len(found) != 1:
        if allow_multiple:
            return [*map(str, found[lookup])]
        else:
            raise KeyError(f"Too many matches found for {term}:\n" + str(found))
    if full:
        return found
    return str(found[lookup].iloc[0])

# TODO: Replace with rom reading components
class InfoProvider:

    def __init__(self, spoiler_log=None, remonstrate_log=None):
        self._area_info = None
        self._boss_info = None
        self._char_info = None
        self._map_info = None

        # Given a category, what column should be used to look up a selection against which table
        self._lookups = self._init()

        self._music_info, self._char_map = None, None
        self._remonstrate_map = None

        if spoiler_log is not None:
            self.read_spoiler(spoiler_log)
        if remonstrate_log is not None:
            self.read_remonstrate(remonstrate_log)

    def _init(self):
        # FIXME: do this in function for easier reloading
        self._area_info = pandas.read_csv(_DATA_PATH / "bc_fantasy_data_areas.csv")
        self._boss_info = pandas.read_csv(_DATA_PATH / "bc_fantasy_data_bosses.csv")
        self._char_info = pandas.read_csv(_DATA_PATH / "bc_fantasy_data_chars.csv")

        self._map_info = pandas.read_csv(_DATA_PATH / "map_ids.csv")
        self._map_info["id"] = [int(n, 16) for n in self._map_info["id"]]
        self._map_info = self._map_info.set_index("id")

        return {
            "area": ("Area", self._area_info),
            "char": ("Character", self._char_info),
            "boss": ("Boss", self._boss_info),
        }

    def read_spoiler(self, spoiler_log):
        if os.path.isdir(spoiler_log):
            try:
                spoiler_log = glob.glob(os.path.join(spoiler_log, "*.txt"))[0]
            except IndexError:
                logging.warning(f"Directory of spoiler log is not valid, "
                                f"no spoiler texts found: {spoiler_log}")

        if os.path.exists(spoiler_log):
            _, _, maps = read.read_spoiler(spoiler_log)
            mmaps, cmaps = maps
            self._music_info = pandas.DataFrame(mmaps).dropna()
            self._char_map = pandas.DataFrame(cmaps).dropna()
        else:
            logging.warning(f"Path to spoiler log is not valid and "
                            f"was not read: {spoiler_log}")

    def read_remonstrate(self, remonstrate_log):
        if os.path.isdir(remonstrate_log):
            try:
                remonstrate_log = glob.glob(os.path.join(remonstrate_log, "*.txt"))[0]
            except IndexError:
                logging.warning(f"Directory of remonstrate log is not valid, "
                                f"no texts found: {remonstrate_log}")

        if os.path.exists(remonstrate_log):
            self._remonstrate_map = pandas.DataFrame(read.read_remonstrate(remonstrate_log))
        else:
            logging.warning(f"Path to remonstrate log is not valid "
                            f"and was not read: {remonstrate_log}")

    def search(self, term, lookup, cat):
        """
        Do a look up for a given term in the lookup column against a lookup table.

        FIXME: Should we merge this with `check_term`?

        :param term: (str) item to match
        :param lookup: (str) column in lookup table to match against
        :param cat: (str) look up table to match against
        :return: Result of search in English, or the exact match (in the case of one)
        """
        def_lookup, info = self._lookups[cat]
        lookup = lookup or def_lookup

        # escape parens
        _term = term.replace("(", r"\(").replace(")", r"\)")
        # Lower case searched column and term, then get partial match against term
        found = info[lookup].str.lower().str.contains(_term.lower())
        # retrieve partial matches
        found = info.loc[found]

        # Narrow to exact matches, if there is one
        if len(found) > 1:
            _found = info[lookup].str.lower() == _term.lower()
            if _found.sum() == 1:
                found = info.loc[_found]

        if len(found) > 1:
            # Still have more than one match, concatenate
            found = ", ".join(found[lookup])
            return f"Found more than one entry ({found}) for {term}"
        elif len(found) == 0:
            # No matches at all
            return f"Found nothing matching {term}"
        else:
            # Exactly one match
            return str(found.to_dict(orient='records')[0])[1:-1]

    def get_next(self, current, cat):
        key, lookup = self._lookup(cat)

        _list = list(lookup[key])
        idx = _list.index(current) + 1

        # Last item
        if idx > len(_list):
            return None
        return _list[idx]

    def lookup_music(self, by_name=None, by_id=None):
        if self._music_info is None or (by_name is None and by_id is None) \
                or by_name.startswith("Unknown"):
            return None

        song = None
        if by_id is not None:
            try:
                song = self._music_info.set_index("song_id")[int(by_id)]
            except KeyError:
                song = self._music_info.loc[self._music_info["orig"] == by_id]
        else:
            song = self._music_info.loc[self._music_info["new"] == by_name]

        if len(song) != 0:
            return None
        return song.iloc[0]

    def list_music(self):
        if self._music_info is None:
            return None
        return self._music_info["orig"].to_list()

    def list_cat(self, cat, with_fields=None):
        return self._lookups[cat][-1][with_fields].iterrows()

    def lookup_map(self, by_id, get_area=False):
        if by_id not in self._map_info.index:
            return None
        if not get_area:
            return self._map_info.loc[by_id]

        map_area = self._map_info["scoring_area"].loc[by_id]
        return self._area_info.loc[map_area == self._area_info["Area"]].iloc[0]

    def lookup_char(self, by_id):
        if by_id not in self._char_info.index:
            return None
        return self._char_info.loc[by_id]

    def lookup_boss(self, by_id=None, by_name=None):
        boss = None
        if by_id in set(self._boss_info["Id"]):
            # Look up numeric id and get canonical boss name
            boss = self._boss_info.set_index("Id").loc[by_id]["Boss"]
        else:
            # It's possible it's intended, so the caller will just get False instead
            #log.warning(f"No valid boss mapping for id {by_id} (this may be intended)")
            pass

        #return self._boss_info.loc[by_id]
        return boss

    def lookup_monster_sprite(self, by_id):
        if self._remonstrate_map is None:
            return None
        search = self._remonstrate_map["enemy_id"].astype(str) == by_id
        return self._remonstrate_map.loc[search]

    def lookup_sprite(self, by_id):
        if self._char_map is None:
            return None
        search = self._char_map["orig"].astype(str) == by_id
        return self._char_map.loc[search]

    def list_sprites(self):
        if self._char_map is None:
            return None
        return self._char_map["orig"].to_list()
