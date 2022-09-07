
import enum
class PlayState(enum.IntEnum):
    DISCONNECTED = 0
    CONNECTED = enum.auto()
    IN_BATTLE = enum.auto()
    ON_FIELD = enum.auto()
    IN_MENU = enum.auto()
