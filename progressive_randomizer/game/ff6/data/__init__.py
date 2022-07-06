from enum import Enum, IntEnum, IntFlag, unique, auto

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
    NoEffect = 0

    Raise_Fight_Dmg = auto()
    Raise_Magic_Dmg = auto()
    HP_Plus_25p = auto()
    HP_Plus_50p = auto()
    HP_Plus_12p = auto()
    MP_Plus_25p = auto()
    MP_Plus_50p = auto()
    MP_Plus_12p = auto()

    Preemptive_Strike = auto()
    Prevent_Back_Attack = auto()
    Fight_To_Jump = auto()
    Enable_XMagic = auto()
    Sketch_To_Control = auto()
    Slot_To_GPRain = auto()
    Steal_To_Capture = auto()
    Improved_Jump = auto()

    UNKNOWN = auto()
    Improved_Sketch = auto()
    Improved_Control = auto()
    Always_Hits = auto()
    Half_MP = auto()
    MP_1 = auto()
    Raise_Vigor = auto()
    Enable_XFight = auto()
    Randomly_Counter = auto()
    Randomly_Evade = auto()
    Double_Grip = auto()
    Dual_Wield = auto()
    Anyone_Equips = auto()
    Cover_Allies = auto()
    UNKNOWN_2 = auto()
    Critical_Shell = auto()
    Critical_Safe = auto()
    Critical_Reflect = auto()
    Double_Exp = auto()
    Double_Gp = auto()
    UNKNOWN_3 = auto()
    UNKNOWN_4 = auto()
    Relic_Ring = auto()


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

@unique
class FieldEffects(IntFlag):
    NoEffect = 0
    # Charm Bangle
    Reduced_Encounters = 1
    # Moogle Charm
    No_Encounters = 2
    # Sprint Shoes
    Sprint = 32
    # Tintinabar
    Field_Regen = 128

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

    @classmethod
    def bytes(cls, as_enum=False):
        vals = [{cls(1 << i) for i in range(8)},
                {cls(1 << i) for i in range(8, 16)},
                {cls(1 << i) for i in range(16, 24)},
                {cls(1 << i) for i in range(24, 32)}]
        if as_enum:
            return [cls(sum(b)) for b in vals]
        return vals

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
    UNUSED1 = auto()
    UNUSED2 = auto()
    Nothing = 0xFF

    def __str__(self):
        return self.name

@unique
class SpellTargeting(IntFlag):
    NO_TARGETIING = 0
    ST_TARG = auto()
    NO_GROUP_SWITCH = auto()
    TARGET_ALL = auto()
    TARGET_GROUP = auto()
    AUTO_ACCEPT_DEFAULT = auto()
    MT_TARG = auto()
    ENEMY_DEFAULT = auto()
    RANDOM = auto()
    SUBMENU = 0xFF

    """
    def __str__(self):
        return {
            1 << 0: "ST moveable",
            1 << 1: "cannot switch group",
            1 << 2: "target all",
            1 << 3: "target group",
            1 << 4: "accept default",
            1 << 5: "MT",
            1 << 6: "default enemy",
            1 << 7: "random",
            0xFF: "open a submenu"
        }[self.value]
    """

@unique
class ItemType(IntEnum):
    pass

@unique
class ItemSpecialFlags(IntFlag):
    # FIXME: Memento / Safety Bit have
    UNKNOWN = 1
    Damage_Undead = auto()
    UNKNOWN_2 = auto()
    Affects_HP = auto()
    Affects_MP = auto()
    Removes_Status = auto()
    # Super Ball and Magicite have this
    Combat_Item = auto()
    Complete_Refill = auto()

@unique
class WeaponSpecialFlags(IntFlag):
    UNKNOWN = 1
    SwdTech_Enable = auto()
    UNKNOWN_2 = auto()
    UNKNOWN_3 = auto()
    UNKNOWN_4 = auto()
    BackRow_Full_Damage = auto()
    Double_Grip_Enabled = auto()
    Runic_Enabled = auto()

@unique
class SpecialEffects(IntEnum):
    NoEffect = 0
    Random_Summon = 1
    Super_Ball = 2
    Battle_Escape = 3
    # randomly evade?
    # elixir and megaelixir have this too?
    _Guardian = 4
    # Enhancer / Falchion / Excalibur / Murasame / Sky_Render / Warp Stone
    _UNKNOWN = 5
    _UNKNOWN_11 = 7
    # a bunch of shields have this ... and dried meat?
    _UNKNOWN_2 = 6
    # force shield
    _UNKNOWN_3 = 10
    # bunch of high tier shields have this
    _UNKNOWN_4 = 14
    _UNKNOWN_5 = 20
    # AtmaWeapon
    Total_HP_Based_Damage = 32
    _UNKNOWN_6 = 48
    _UNKNOWN_7 = 52
    Double_Human_Damage = 68
    # But... isn't this covered elsewhere?
    Drain_Hp = 85
    _UNKNOWN_8 = 101
    _UNKNOWN_9 = 112
    # But also 112? (Punisher)
    MP_Criticals = 117
    # Hawk Eye / Sniper
    Flyer_Critical = 128
    _UNKNOWN_10 = 144
    # ValiantKnife
    HP_Fraction_Damage = 164
    Replace_With_Spell = 176
    Heals_HP = 192
    Instant_Kill = 208
    Randomly_Breaks = 224
    Item_Flag = 255

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
    _SWDTECH = set(range(0x56, 0x5D))
    _ESPER = set(range(0x36, 0x51))
    _SLOTS = set(range(0x7F, 0x83)) | {0xFF}
    _DESPERATION = set(range(0xF0, 0xFD))
    _DANCE = set(range(0x66, 0x7E))
    _MAGITEK = set(range(0x84, 0x8C))
    _LORE = set(range(0x8C, 0xA4))
    # ...

    @classmethod
    def is_magic(cls, value):
        return value in cls._MAGIC

    @classmethod
    def is_blitz(cls, value):
        return value in cls._BLITZES

    @classmethod
    def is_swdtech(cls, value):
        return value in cls._SWDTECH

    @classmethod
    def is_esper(cls, value):
        return value in cls._ESPER

    @classmethod
    def is_slots(cls, value):
        return value in cls._SLOTS

    @classmethod
    def is_desperation(cls, value):
        return value in cls._DESPERATION

    @classmethod
    def rank(cls, value):
        return 1

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

    # Blitzes
    Pummel = auto()
    AuraBolt = auto()
    Suplex = auto()
    Fire_Dance = auto()
    Mantra = auto()
    Air_Blade = auto()
    Spiraler = auto()
    Bum_Rush = auto()

    # Dance skills
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

    # Dance / animals
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

    # slots
    Flash = auto()
    Chocobop = auto()
    H_Bomb = auto()
    _7_Flush = auto()

    # shock
    Megahit = auto()

    # magitek
    Fire_Beam = auto()
    Bolt_Beam = auto()
    Ice_Beam = auto()
    Bio_Blast = auto()
    Heal_Force = auto()
    Confuser = auto()
    X_fer = auto()
    TekMissile = auto()

    # lore
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

    # unused
    Clear = auto()

    # enemy skills
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

    # enemy specific
    Battle = auto()
    Special = auto()

    # Desperations
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

    # interceptor
    Takedown = auto()
    Wild_Fang = auto()

    # technically slots, but...
    Lagomorph = auto()
    # NOTE: only in scripts
    #Nothing = auto()

    def is_magic(self):
        return super().is_magic(self)

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

class InventoryType(IntEnum):
    Tool = 0
    Weapon = 1
    Armor = 2
    Shield = 3
    Helmet = 4
    Relic = 5
    Item = 6

class Item(IntEnum):
    Dirk = 0
    MithrilKnife = auto()
    Guardian = auto()
    Air_Lancet = auto()
    ThiefKnife = auto()
    Assassin = auto()
    Man_Eater = auto()
    SwordBreaker = auto()
    Graedus = auto()
    ValiantKnife = auto()
    MithrilBlade = auto()
    RegalCutlass = auto()
    Rune_Edge = auto()
    Flame_Sabre = auto()
    Blizzard = auto()
    ThunderBlade = auto()
    Epee = auto()
    Break_Blade = auto()
    Drainer = auto()
    Enhancer = auto()
    Crystal = auto()
    Falchion = auto()
    Soul_Sabre = auto()
    Ogre_Nix = auto()
    Excalibur = auto()
    Scimitar = auto()
    Illumina = auto()
    Ragnarok = auto()
    Atma_Weapon = auto()
    Mithril_Pike = auto()
    Trident = auto()
    Stout_Spear = auto()
    Partisan = auto()
    Pearl_Lance = auto()
    Gold_Lance = auto()
    Aura_Lance = auto()
    Imp_Halberd = auto()
    Imperial = auto()
    Kodachi = auto()
    Blossom = auto()
    Hardened = auto()
    Striker = auto()
    Stunner = auto()
    Ashura = auto()
    Kotetsu = auto()
    Forged = auto()
    Tempest = auto()
    Murasame = auto()
    Aura = auto()
    Strato = auto()
    Sky_Render = auto()
    Heal_Rod = auto()
    Mithril_Rod = auto()
    Fire_Rod = auto()
    Ice_Rod = auto()
    Thunder_Rod = auto()
    Poison_Rod = auto()
    Pearl_Rod = auto()
    Gravity_Rod = auto()
    Punisher = auto()
    Magus_Rod = auto()
    Chocobo_Brsh = auto()
    DaVinci_Brsh = auto()
    Magical_Brsh = auto()
    Rainbow_Brsh = auto()
    Shuriken = auto()
    Ninja_Star = auto()
    Tack_Star = auto()
    Flail = auto()
    Full_Moon = auto()
    Morning_Star = auto()
    Boomerang = auto()
    Rising_Sun = auto()
    Hawk_Eye = auto()
    Bone_Club = auto()
    Sniper = auto()
    Wing_Edge = auto()
    Cards = auto()
    Darts = auto()
    Doom_Darts = auto()
    Trump = auto()
    Dice = auto()
    Fixed_Dice = auto()
    MetalKnuckle = auto()
    Mithril_Claw = auto()
    Kaiser = auto()
    Poison_Claw = auto()
    Fire_Knuckle = auto()
    Dragon_Claw = auto()
    Tiger_Fangs = auto()
    Buckler = auto()
    Heavy_Shld = auto()
    Mithril_Shld = auto()
    Gold_Shld = auto()
    Aegis_Shld = auto()
    Diamond_Shld = auto()
    Flame_Shld = auto()
    Ice_Shld = auto()
    Thunder_Shld = auto()
    Crystal_Shld = auto()
    Genji_Shld = auto()
    TortoiseShld = auto()
    Cursed_Shld = auto()
    Paladin_Shld = auto()
    Force_Shield = auto()
    Leather_Hat = auto()
    Hair_Band = auto()
    Plumed_Hat = auto()
    Beret = auto()
    Magus_Hat = auto()
    Bandana = auto()
    Iron_Helmet = auto()
    Coronet = auto()
    Bards_Hat = auto()
    Green_Beret = auto()
    Head_Band = auto()
    Mithril_Helm = auto()
    Tiara = auto()
    Gold_Helmet = auto()
    Tiger_Mask = auto()
    Red_Cap = auto()
    Mystery_Veil = auto()
    Circlet = auto()
    Regal_Crown = auto()
    Diamond_Helm = auto()
    Dark_Hood = auto()
    Crystal_Helm = auto()
    Oath_Veil = auto()
    Cat_Hood = auto()
    Genji_Helmet = auto()
    Thornlet = auto()
    Titanium = auto()
    LeatherArmor = auto()
    Cotton_Robe = auto()
    Kung_Fu_Suit = auto()
    Iron_Armor = auto()
    Silk_Robe = auto()
    Mithril_Vest = auto()
    Ninja_Gear = auto()
    White_Dress = auto()
    Mithril_Mail = auto()
    Gaia_Gear = auto()
    Mirage_Vest = auto()
    Gold_Armor = auto()
    Power_Sash = auto()
    Light_Robe = auto()
    Diamond_Vest = auto()
    Red_Jacket = auto()
    Force_Armor = auto()
    DiamondArmor = auto()
    Dark_Gear = auto()
    Tao_Robe = auto()
    Crystal_Mail = auto()
    Czarina_Gown = auto()
    Genji_Armor = auto()
    Imps_Armor = auto()
    Minerva = auto()
    Tabby_Suit = auto()
    Chocobo_Suit = auto()
    Moogle_Suit = auto()
    Nutkin_Suit = auto()
    BehemothSuit = auto()
    Snow_Muffler = auto()
    NoiseBlaster = auto()
    Bio_Blaster = auto()
    Flash = auto()
    Chain_Saw = auto()
    Debilitator = auto()
    Drill = auto()
    Air_Anchor = auto()
    AutoCrossbow = auto()
    Fire_Skean = auto()
    Water_Edge = auto()
    Bolt_Edge = auto()
    Inviz_Edge = auto()
    Shadow_Edge = auto()
    Goggles = auto()
    Star_Pendant = auto()
    Peace_Ring = auto()
    Amulet = auto()
    White_Cape = auto()
    Jewel_Ring = auto()
    Fairy_Ring = auto()
    Barrier_Ring = auto()
    MithrilGlove = auto()
    Guard_Ring = auto()
    RunningShoes = auto()
    Wall_Ring = auto()
    Cherub_Down = auto()
    Cure_Ring = auto()
    True_Knight = auto()
    DragoonBoots = auto()
    Zephyr_Cape = auto()
    Czarina_Ring = auto()
    Cursed_Ring = auto()
    Earrings = auto()
    Atlas_Armlet = auto()
    Blizzard_Orb = auto()
    Rage_Ring = auto()
    Sneak_Ring = auto()
    Pod_Bracelet = auto()
    Hero_Ring = auto()
    Ribbon = auto()
    Muscle_Belt = auto()
    Crystal_Orb = auto()
    Gold_Hairpin = auto()
    Economizer = auto()
    Thief_Glove = auto()
    Gauntlet = auto()
    Genji_Glove = auto()
    Hyper_Wrist = auto()
    Offering = auto()
    Beads = auto()
    Black_Belt = auto()
    Coin_Toss = auto()
    FakeMustache = auto()
    Gem_Box = auto()
    Dragon_Horn = auto()
    Merit_Award = auto()
    Memento_Ring = auto()
    Safety_Bit = auto()
    Relic_Ring = auto()
    Moogle_Charm = auto()
    Charm_Bangle = auto()
    Marvel_Shoes = auto()
    Back_Guard = auto()
    Gale_Hairpin = auto()
    Sniper_Sight = auto()
    Exp_Egg = auto()
    Tintinabar = auto()
    Sprint_Shoes = auto()
    Rename_Card = auto()
    Tonic = auto()
    Potion = auto()
    X_Potion = auto()
    Tincture = auto()
    Ether = auto()
    X_Ether = auto()
    Elixer = auto()
    Megalixer = auto()
    Fenix_Down = auto()
    Revivify = auto()
    Antidote = auto()
    Eyedrop = auto()
    Soft = auto()
    Remedy = auto()
    Sleeping_Bag = auto()
    Tent = auto()
    Green_Cherry = auto()
    Magicite = auto()
    Super_Ball = auto()
    Echo_Screen = auto()
    Smoke_Bomb = auto()
    Warp_Stone = auto()
    Dried_Meat = auto()
    Blank = auto()