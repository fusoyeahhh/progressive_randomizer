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

from .components import *
from .randomizers import *

def _register(known_games):
    known_games[GAME_NAME] = FF6StaticRandomizer
