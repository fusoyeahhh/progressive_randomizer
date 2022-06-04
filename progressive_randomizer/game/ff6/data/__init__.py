from enum import Enum, IntEnum, IntFlag, unique, auto
import functools

def from_str(cls, s):
    return [cls[v] for v in s.split("|")]

@unique
class Character(IntEnum):
    Terra = 0
    Locke = auto()
    Cyan = auto()
    Shadow = auto()
    Edgar = auto()
    Sabin = auto()
    Celes = auto()
    Strago = auto()
    Relm = auto()
    Setzer = auto()
    Mog = auto()
    Gau = auto()
    Gogo = auto()
    Umaro = auto()
    Guest_1 = auto()
    Guest_2 = auto()

class EquipCharacter(IntFlag):
    Terra = 1
    Locke = auto()
    Cyan = auto()
    Shadow = auto()
    Edgar = auto()
    Sabin = auto()
    Celes = auto()
    Strago = auto()
    Relm = auto()
    Setzer = auto()
    Mog = auto()
    Gau = auto()
    Gogo = auto()
    Umaro = auto()
    Guest_1 = auto()
    Guest_2 = auto()


class EquipmentFlags(IntFlag):
    pass

@unique
class Element(IntFlag):
    NoElement = 0
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
    NoStatus = 0
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
class ItemType(IntEnum):
    pass

@unique
class ItemFlags(IntFlag):
    pass

@unique
class SpellSpecialFlags(IntFlag):
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


# TODO: somewhat unsatisfactory
class SkillSets:
    _MAGIC = set(range(0x0, 0x36))
    _BLITZES = set(range(0x5E, 0x66))
    _SWDTECH = set(range(0x55, 0x5D))
    _ESPER = set(range(0x36, 0x51))
    _SLOTS = set(range(0x7D, 0x83))
    _DESPERATION = set(range(0xF0, 0xFE))
    #_DANCE =
    # ...

    def is_blitz(cls, value):
        return value in cls._BLITZES

    def is_swdtech(cls, value):
        return value in cls._SWDTECH

    def is_esper(cls, value):
        return value in cls._ESPER

    def is_slots(cls, value):
        return value in cls._SLOTS

    def is_desperation(cls, value):
        return value in cls._DESPERATION

@unique
class Spell(SkillSets, IntEnum):
    Fire = 0
    Ice = auto()
    Bolt = auto()
    Poison = auto()
    Drain = auto()
    Fire_2 = auto()
    Ice_2 = auto()
    Bolt_2 = auto()
    Bio = auto()
    Fire_3 = auto()
    Ice_3 = auto()
    Bolt_3 = auto()
    Break = auto()
    Doom = auto()
    Pearl = auto()
    Flare = auto()
    Demi = auto()
    Quartr = auto()
    X_Zone = auto()
    Meteor = auto()
    Ultima = auto()
    Quake = auto()
    W_Wind = auto()
    Merton = auto()
    Scan = auto()
    Slow = auto()
    Rasp = auto()
    Mute = auto()
    Safe = auto()
    Sleep = auto()
    Muddle = auto()
    Haste = auto()
    Stop = auto()
    Bserk = auto()
    Float = auto()
    Imp = auto()
    Rflect = auto()
    Shell = auto()
    Vanish = auto()
    Haste2 = auto()
    Slow_2 = auto()
    Osmose = auto()
    Warp = auto()
    Quick = auto()
    Dispel = auto()
    Cure = auto()
    Cure_2 = auto()
    Cure_3 = auto()
    Life = auto()
    Life_2 = auto()
    Antdot = auto()
    Remedy = auto()
    Regen = auto()
    Life_3 = auto()

    # espers
    Ramuh = auto()
    Ifrit = auto()
    Shiva = auto()
    Siren = auto()
    Terrato = auto()
    Shoat = auto()
    Maduin = auto()
    Bismark = auto()
    Stray = auto()
    Palidor = auto()
    Tritoch = auto()
    Odin = auto()
    Raiden = auto()
    Bahamut = auto()
    Alexandr = auto()
    Crusader = auto()
    Ragnarok = auto()
    Kirin = auto()
    ZoneSeek = auto()
    Carbunkl = auto()
    Phantom = auto()
    Sraphim = auto()
    Golem = auto()
    Unicorn = auto()
    Fenrir = auto()
    Starlet = auto()
    Phoenix = auto()

    # player skills
    Fire_Skean = auto()
    Water_Edge = auto()
    Bolt_Edge = auto()
    Storm = auto()
    Joker_Doom = auto()

    # 8 swdtech names
    Dispatch = auto()
    Retort = auto()
    Slash = auto()
    Quadra_Slam = auto()
    Empowerer = auto()
    Stunner = auto()
    Quadra_Slice = auto()
    Cleave = auto()

    Pummel = auto()
    AuraBolt = auto()
    Suplex = auto()
    Fire_Dance = auto()
    Mantra = auto()
    Air_Blade = auto()
    Spiraler = auto()
    Bum_Rush = auto()
    Wind_Slash = auto()
    Sun_Bath = auto()
    Rage = auto()
    Harvester = auto()
    Sand_Storm = auto()
    Antlion = auto()
    Elf_Fire = auto()
    Specter = auto()
    Land_Slide = auto()
    Sonic_Boom = auto()
    El_Nino = auto()
    Plasma = auto()
    Snare = auto()
    Cave_In = auto()
    Snowball = auto()
    Surge = auto()
    Cokatrice = auto()
    Wombat = auto()
    Kitty = auto()
    Tapir = auto()
    Whump = auto()
    Wild_Bear = auto()
    Pois__Frog = auto()
    Ice_Rabbit = auto()
    # superball?
    Super_Ball = auto()
    Flash = auto()
    Chocobop = auto()
    H_Bomb = auto()
    _7_Flush = auto()
    Megahit = auto()
    Fire_Beam = auto()
    Bolt_Beam = auto()
    Ice_Beam = auto()
    Bio_Blast = auto()
    Heal_Force = auto()
    Confuser = auto()
    X_fer = auto()
    TekMissile = auto()
    Condemned = auto()
    Roulette = auto()
    CleanSweep = auto()
    Aqua_Rake = auto()
    Aero = auto()
    Blow_Fish = auto()
    Big_Guard = auto()
    Revenge = auto()
    Pearl_Wind = auto()
    L_5_Doom = auto()
    L_4_Flare = auto()
    L_3_Muddle = auto()
    Reflect___ = auto()
    L__Pearl = auto()
    Step_Mine = auto()
    ForceField = auto()
    Dischord = auto()
    Sour_Mouth = auto()
    Pep_Up = auto()
    Rippler = auto()
    Stone = auto()
    Quasar = auto()
    GrandTrain = auto()
    Exploder = auto()
    Imp_Song = auto()
    Clear = auto()
    Virite = auto()
    ChokeSmoke = auto()
    Schiller = auto()
    Lullaby = auto()
    Acid_Rain = auto()
    Confusion = auto()
    Megazerk = auto()
    Mute_ = auto()
    Net = auto()
    Slimer = auto()
    Delta_Hit = auto()
    Entwine = auto()
    Blaster = auto()
    Cyclonic = auto()
    Fire_Ball = auto()
    Atomic_Ray = auto()
    Tek_Laser = auto()
    Diffuser = auto()
    WaveCannon = auto()
    Mega_Volt = auto()
    Giga_Volt = auto()
    Blizzard = auto()
    Absolute_0 = auto()
    Magnitude8 = auto()
    Raid = auto()
    Flash_Rain = auto()
    TekBarrier = auto()
    Fallen_One = auto()
    WallChange = auto()
    Escape = auto()
    _50_Gs = auto()
    Mind_Blast = auto()
    N__Cross = auto()
    Flare_Star = auto()
    Love_Token = auto()
    Seize = auto()
    R_Polarity = auto()
    Targetting = auto()
    Sneeze = auto()
    S__Cross = auto()
    Launcher = auto()
    Charm = auto()
    Cold_Dust = auto()
    Tentacle = auto()
    HyperDrive = auto()
    Train = auto()
    Evil_Toot = auto()
    Grav_Bomb = auto()
    Engulf = auto()
    Disaster = auto()
    Shrapnel = auto()
    Bomblet = auto()
    Heart_Burn = auto()
    Zinger = auto()
    Discard = auto()
    Overcast = auto()
    Missile = auto()
    Goner = auto()
    Meteo = auto()
    Revenger = auto()
    Phantasm = auto()
    Dread = auto()
    Shock_Wave = auto()
    Blaze = auto()
    Soul_Out = auto()
    Gale_Cut = auto()
    Shimsham = auto()
    Lode_Stone = auto()
    Scar_Beam = auto()
    BabaBreath = auto()
    Lifeshaver = auto()
    Fire_Wall = auto()
    Slide = auto()
    Battle = auto()
    Special = auto()
    Riot_Blade = auto()
    Mirager = auto()
    Back_Blade = auto()
    ShadowFang = auto()
    RoyalShock = auto()
    TigerBreak = auto()
    Spin_Edge = auto()
    SabreSoul = auto()
    Star_Prism = auto()
    Red_Card = auto()
    MoogleRush = auto()
    X_Meteo = auto()
    Takedown = auto()
    Wild_Fang = auto()
    Lagomorph = auto()
    # NOTE: only in scripts
    #Nothing = auto()

    def is_blitz(self):
        return super().is_blitz(self)

    def is_swdtech(self):
        return super().is_swdtech(self)

    def is_esper(self):
        return super().is_esper(self)

    def is_slots(self):
        return super().is_slots(self)

    def is_desperation(self):
        return super().is_desperation(self)

    @classmethod
    def rank(cls, value):
        pass
