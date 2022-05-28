from enum import Enum, unique
import functools

# TODO: move?
def filter_by_value(enum, val):
    return [e for e in enum if val & e.value == e.value]

def enum_to_bytes(enum):
    return functools.reduce(int.__or__, [e.value for e in enum])

class ByteEnumeration:
    @classmethod
    def from_byte(cls, val, block=None):
        return [e for e in cls if val & e.value == e.value]

    @classmethod
    def enum_to_bytes(cls, enum):
        return functools.reduce(int.__or__, [e.value for e in enum])

    def __str__(self):
        return self.name

@unique
class Element(Enum):
    Fire = 1 << 0
    Ice = 1 << 1
    Lightning = 1 << 2
    Poison = 1 << 3
    Wind = 1 << 4
    Pearl = 1 << 5
    Earth = 1 << 6
    Water = 1 << 7

    def __str__(self):
        return self.name

@unique
class Status(Enum):
    Dark = 1 << 0
    Zombie = 1 << 1
    Poison = 1 << 2
    Magitek = 1 << 3
    Vanish = 1 << 4
    Imp = 1 << 5
    Petrify = 1 << 6
    Death = 1 << 7

    Condemned = 0x100 << 0
    NearFatal = 0x100 << 1
    Blink = 0x100 << 2
    Slience = 0x100 << 3
    Berserk = 0x100 << 4
    Confusion = 0x100 << 5
    Seizure = 0x100 << 6
    Sleep = 0x100 << 7

    Dance = 0x10000 << 0
    Regen = 0x10000 << 1
    Slow = 0x10000 << 2
    Haste = 0x10000 << 3
    Stop = 0x10000 << 4
    Shell = 0x10000 << 5
    Safe = 0x10000 << 6
    Reflect = 0x10000 << 7

    Rage = 0x1000000 << 0
    Frozen = 0x1000000 << 1
    DeathProtection = 0x1000000 << 2
    Morph = 0x1000000 << 3
    Chanting = 0x1000000 << 4
    Removed = 0x1000000 << 5
    Interceptor = 0x1000000 << 6
    Float = 0x1000000 << 7

    def __str__(self):
        return self.name

@unique
class SpellTargeting(Enum):
    ST_TARG = 1 << 0
    NO_GROUP_SWITCH = 1 << 1
    TARGET_ALL = 1 << 2
    TARGET_GROUP = 1 << 3
    AUTO_ACCEPT_DEFAULT = 1 << 4
    MT_TARG = 1 << 5
    ENEMY_DEFAULT = 1 << 6
    RANDOM = 1 << 7

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
class SpellSpecialFlags(Enum):
    PHYS_DMG = 1 << 0
    ID_MISS = 1 << 1
    ONLY_DEAD = 1 << 2
    INV_DMG_UNDEAD = 1 << 3
    RANDOM_TARG = 1 << 4
    IGNORE_DEF = 1 << 5
    NO_MULTI_SPLIT_DMG = 1 << 6
    ABORT_ON_ALLIES = 1 << 7

    FIELD_ENABLED = 0x100 << 0
    IGNORE_REFLECT = 0x100 << 1
    LORE_LEARNABLE = 0x100 << 2
    ALLOW_RUNIC = 0x100 << 3
    UNK = 0x100 << 4
    RETARGET_IF_DEAD = 0x100 << 5
    KILL_USER = 0x100 << 6
    MP_DMG = 0x100 << 7

    HEAL_TARG = 0x10000 << 0
    DRAIN_EFFECT = 0x10000 << 1
    LIFT_STATUS = 0x10000 << 2
    TOGGLE_STATUS = 0x10000 << 3
    STM_EVADE = 0x10000 << 4
    CANT_EVADE = 0x10000 << 5
    HIT_RATE_MULT_TARGET = 0x10000 << 6
    FRACT_DMG = 0x10000 << 7

    MISS_IF_STATUS_PROTECT = 0x1000000 << 0
    SHOW_TEXT_ON_HIT = 0x1000000 << 1

@unique
class Spell(Enum):
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
