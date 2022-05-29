from enum import Enum, IntEnum, IntFlag, unique, auto
import functools

# TODO: move?
def filter_by_value(enum, val, block=0):
    val <<= block * 8
    return [e for e in enum if val & e == e]

def enum_to_bytes(enum):
    return functools.reduce(int.__or__, [e for e in enum])

class ByteEnumeration(Enum):
    @classmethod
    def from_byte(cls, val, block=0):
        val <<= block * 8
        return [e for e in cls if val & e.value == e.value]

    @classmethod
    def enum_to_bytes(cls, enum):
        return functools.reduce(int.__or__, [e.value for e in enum])

    @classmethod
    def from_str(cls, s):
        return [cls[v] for v in s.split("|")]

    def __str__(self):
        return self.name

@unique
class Element(IntFlag):
    Fire = auto()
    Ice = auto()
    Lightning = auto()
    Poison = auto()
    Wind = auto()
    Pearl = auto()
    Earth = auto()
    Water = auto()

    def __str__(self):
        return self.name

@unique
class Status(IntFlag):
    Dark = auto()
    Zombie = auto()
    Poison = auto()
    Magitek = auto()
    Vanish = auto()
    Imp = auto()
    Petrify = auto()
    Death = auto()

    Condemned = auto()
    NearFatal = auto()
    Blink = auto()
    Slience = auto()
    Berserk = auto()
    Confusion = auto()
    Seizure = auto()
    Sleep = auto()

    Dance = auto()
    Regen = auto()
    Slow = auto()
    Haste = auto()
    Stop = auto()
    Shell = auto()
    Safe = auto()
    Reflect = auto()

    Rage = auto()
    Frozen = auto()
    DeathProtection = auto()
    Morph = auto()
    Chanting = auto()
    Removed = auto()
    Interceptor = auto()
    Float = auto()

    def __str__(self):
        return self.name

@unique
class Command(IntEnum):
    Fight = 0
    Item = auto()
    Magic = auto()
    Morph = auto()
    Revert = auto()
    Steal = auto()
    Capture = auto()
    Swdtech = auto()
    Throw = auto()
    Tools = auto()
    Blitz = auto()
    Runic = auto()
    Lore = auto()
    Sketch = auto()
    Control = auto()
    Slot = auto()
    Rage = auto()
    Leap = auto()
    Mimic = auto()
    Dance = auto()
    Row = auto()
    Defend = auto()
    Jump = auto()
    X_Magic = auto()
    GP_Rain = auto()
    Summon = auto()
    Health = auto()
    Shock = auto()
    Possess = auto()
    Magitek = auto()

    def __str__(self):
        return self.name

@unique
class SpellTargeting(IntFlag):
    ST_TARG = auto()
    NO_GROUP_SWITCH = auto()
    TARGET_ALL = auto()
    TARGET_GROUP = auto()
    AUTO_ACCEPT_DEFAULT = auto()
    MT_TARG = auto()
    ENEMY_DEFAULT = auto()
    RANDOM = auto()

    def __str__(self):
        return {
            1 << 0: "ST moveable",
            1 << 1: "cannot switch group",
            1 << 2: "target all",
            1 << 3: "target group",
            1 << 4: "accept default",
            1 << 5: "MT",
            1 << 6: "default enemy",
            1 << 7: "random"
        }[self.value]

@unique
class SpellSpecialFlags(IntEnum):
    PHYS_DMG = auto()
    ID_MISS = auto()
    ONLY_DEAD = auto()
    INV_DMG_UNDEAD = auto()
    RANDOM_TARG = auto()
    IGNORE_DEF = auto()
    NO_MULTI_SPLIT_DMG = auto()
    ABORT_ON_ALLIES = auto()

    FIELD_ENABLED = auto()
    IGNORE_REFLECT = auto()
    LORE_LEARNABLE = auto()
    ALLOW_RUNIC = auto()
    UNK = auto()
    RETARGET_IF_DEAD = auto()
    KILL_USER = auto()
    MP_DMG = auto()

    HEAL_TARG = auto()
    DRAIN_EFFECT = auto()
    LIFT_STATUS = auto()
    TOGGLE_STATUS = auto()
    STM_EVADE = auto()
    CANT_EVADE = auto()
    HIT_RATE_MULT_TARGET = auto()
    FRACT_DMG = auto()

    MISS_IF_STATUS_PROTECT = auto()
    SHOW_TEXT_ON_HIT = auto()

@unique
class Spell(IntEnum):
    Fire = 1
    ...

    @classmethod
    def is_blitz(cls, value):
        return value in range(0x5D, 0x65)

    @classmethod
    def is_swdtech(cls, value):
        return value in range(0x55, 0x5D)

    @classmethod
    def is_esper(cls, value):
        return value in range(0x36, 0x51)

    @classmethod
    def is_slots(cls, value):
        return value in range(0x7D, 0x83)

    @classmethod
    def rank(cls, value):
        pass
