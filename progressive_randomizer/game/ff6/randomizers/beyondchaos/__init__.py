from ... import FF6StaticRandomizer

GAME_NAME = b'FF6 BCCE'

def detect_bc(game_name):
    if game_name.startswith(GAME_NAME):
        return FF6StaticRandomizer
    return None