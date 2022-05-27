import logging
log = logging.getLogger()

from ..components import SNESHeader
from ..components.randomizers import StaticRandomizer
from ..game import KNOWN_GAMES

from ..game.ff6.randomizers.beyondchaos import detect_bc
NON_STD_GAMES = [
    detect_bc
]

def _read_header(filename):
    with open(filename, "rb") as fin:
        romdata = fin.read(0x10000)

    return SNESHeader() << romdata

def autodetect_and_load_game(filename):
    header_data = _read_header(filename)
    game_name = header_data["Game Title Registration"]

    # Get first registered non-standard game
    is_nonstd_game = [fn(game_name) for fn in NON_STD_GAMES if fn(game_name)]

    if game_name not in KNOWN_GAMES and len(is_nonstd_game) == 0:
        log.warning("Game does not have a registered randomizer, "
                    "using default --- some functions may not be available.")
    if len(is_nonstd_game) > 0:
        rando = is_nonstd_game[0]
    else:
        rando = KNOWN_GAMES.get(game_name, StaticRandomizer)
    log.info(f"Read header, game name: {game_name} -> {rando}")

    with open(filename, "rb") as fin:
        romdata = fin.read()

    return romdata, rando()

