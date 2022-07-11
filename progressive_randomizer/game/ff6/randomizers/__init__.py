import csv
import re
import time
import random

import logging
log = logging.getLogger()

from ....components import (
    AssemblyObject,
    Registry
)

from ....components.randomizers import (
    StaticRandomizer,
    ProgressiveRandomizer
)

from .. import data

from ..components import (
    FF6PointerTable,
    FF6DataTable,
    FF6Text,
    FF6SRAM,
    FF6EventFlags,
    FF6MemoryManager
)

from ..components import REGISTER_DATA
from .. import ROM_MAP_DATA, ROM_DESCR_TAGS

from ....utils import randomization

class StatRandomizer:
    def __init__(self, lower, upper=255):
        self._lower = lower
        self._upper = upper
        self._range = upper - lower

    def __call__(self, targ, inv_width=1):
        from ....utils import randomization
        return self._lower + randomization.discrete_beta(self._range,
                                                         targ - self._lower,
                                                         inv_width)

class AttributeRandomizer:

    def __init__(self, attr_enum, null=None):
        self._enum = attr_enum
        self._null = None or null

    def __call__(self, attrs=None, n=1, exclude=None, reset=False):
        from ....utils import randomization
        if n < 0:
            n = randomization.poisson(abs(n))

        pool = {a for a in self._enum} - {self._null}
        attrs = self._null if reset or attrs is None else attrs
        if reset:
            attrs = self._null
        else:
            pool -= {e for e in self._enum if e & attrs} or set()
            pool -= exclude or set()

        if len(pool) <= 0:
            log.warning("Insufficient remaining attributes left to add")
            return

        for e in randomization.choice_without_replacement(list(pool), n):
            attrs |= e
            pool -= {e}

        return attrs

    def shuffle(self, to_shuffle, mix_ratio=1, fuzzy=False, generate=0, exclude=None):
        keep = {e for e in self._enum
                if e & to_shuffle and random.uniform(0, 1) < mix_ratio}
        n = len([e for e in self._enum if e & to_shuffle])
        draw = max(generate, n - len(keep))
        draw *= -1 if fuzzy else 1
        return self._enum(self(sum(keep), n=draw, exclude=exclude))

class StatusRandomizer(AttributeRandomizer):
    _BY_BYTE = [{e for e in data.Status.bytes()[b]} for b in range(4)]

    def __init__(self):
        super().__init__(data.Status, null=data.Status.NoStatus)

    def shuffle(self, to_shuffle, mix_ratio=1, fuzzy=False, generate=0,
                exclude=None, only_bytes={0, 1, 2, 3}):
        exclude = exclude or set()
        for i, stats in enumerate(data.Status.bytes()):
            if i not in only_bytes:
                exclude |= stats
        return super().shuffle(to_shuffle, mix_ratio=mix_ratio, fuzzy=fuzzy,
                               generate=0, exclude=exclude)

class SpellRandomizer(AttributeRandomizer):
    def __init__(self):
        super().__init__(data.Spell, null=0)

    _LR_GENERATOR = StatRandomizer(1, 50)
    def gen_learning_rate(self, lr=1, closeness=50):
        return self._LR_GENERATOR(lr, closeness)

    def _retrieve_skills_by_type(self, magic=False, blitzes=False, swdtech=False,
                                 espers=False, slots=False, dance=False,
                                 lore=False, magitek=False, desperation=False,
                                 others=False):
        pool = set()
        pool |= data.SkillSets._MAGIC if magic else set()
        pool |= data.SkillSets._BLITZES if blitzes else set()
        pool |= data.SkillSets._SWDTECH if swdtech else set()
        pool |= data.SkillSets._ESPER if espers else set()
        pool |= data.SkillSets._SLOTS if slots else set()
        pool |= data.SkillSets._DANCE if dance else set()
        pool |= data.SkillSets._LORE if lore else set()
        pool |= data.SkillSets._MAGITEK if magitek else set()
        pool |= data.SkillSets._DESPERATION if desperation else set()
        if others:
            pool |= set(*data.Spell) - (data.SkillSets._MAGIC |
                                        data.SkillSets._BLITZES |
                                        data.SkillSets._SWDTECH |
                                        data.SkillSets._ESPER |
                                        data.SkillSets._SLOTS |
                                        data.SkillSets._DANCE |
                                        data.SkillSets._LORE |
                                        data.SkillSets._MAGITEK |
                                        data.SkillSets._DESPERATION)

        return set(map(data.Spell, pool))

    def __call__(self, pool=None, skillsets={"all"}):
        if "all" in skillsets:
            # do not recommend
            pool = {*data.Spell}
        else:
            sets = {arg: True for arg in skillsets}
            pool = pool or self._retrieve_skills_by_type(**sets)
        return random.choice(list(pool))

class TargetingRandomizer(AttributeRandomizer):
    # FIXME: These are all combinations in the game
    # others may be possible
    ALLOWABLE_TARGETING = {
        data.SpellTargeting.ST_TARG,
        data.SpellTargeting.NO_GROUP_SWITCH,
        data.SpellTargeting.NO_GROUP_SWITCH | data.SpellTargeting.ST_TARG,
        data.SpellTargeting.MT_TARG | data.SpellTargeting.TARGET_GROUP | data.SpellTargeting.TARGET_ALL | data.SpellTargeting.NO_GROUP_SWITCH,
        data.SpellTargeting.ENEMY_DEFAULT | data.SpellTargeting.ST_TARG,
        data.SpellTargeting.ENEMY_DEFAULT | data.SpellTargeting.NO_GROUP_SWITCH | data.SpellTargeting.ST_TARG,
        data.SpellTargeting.ENEMY_DEFAULT | data.SpellTargeting.MT_TARG | data.SpellTargeting.TARGET_GROUP | data.SpellTargeting.ST_TARG,
        data.SpellTargeting.ENEMY_DEFAULT | data.SpellTargeting.MT_TARG | data.SpellTargeting.TARGET_GROUP | data.SpellTargeting.NO_GROUP_SWITCH,
        data.SpellTargeting.ENEMY_DEFAULT | data.SpellTargeting.MT_TARG | data.SpellTargeting.TARGET_GROUP | data.SpellTargeting.TARGET_ALL | data.SpellTargeting.NO_GROUP_SWITCH
    }

    def __init__(self):
        super().__init__(data.SpellTargeting, null=data.SpellTargeting.NO_TARGETIING)

    def __call__(self, attrs):
        # The item isn't targetable, and we don't change that
        if attrs == data.SpellTargeting.NO_TARGETIING:
            return attrs

        # ensure *some* overlap
        choices = [t for t in self.ALLOWABLE_TARGETING if t & attrs]

        return random.choice(choices)

AttributeRandomizer.status = StatusRandomizer()
AttributeRandomizer.spelltargeting = TargetingRandomizer()
AttributeRandomizer.spells = SpellRandomizer()
AttributeRandomizer.element = AttributeRandomizer(data.Element, null=data.Element.NoElement)
AttributeRandomizer.equipchar = AttributeRandomizer(data.EquipCharacter, null=0)
AttributeRandomizer.fieldeffect = AttributeRandomizer(data.FieldEffects, null=data.FieldEffects.NoEffect)
AttributeRandomizer.equipflags = AttributeRandomizer(data.EquipmentFlags, null=data.EquipmentFlags.NoEffect)

class FF6StaticRandomizer(StaticRandomizer):
    def __init__(self):
        super().__init__()
        self._reg = self.from_rom_map(ROM_MAP_DATA,
                                      ROM_DESCR_TAGS,
                                      apply_offset=0xC00000)
        self._reg = FF6MemoryManager.copy(self._reg)
        self._reg.mark_tag_as_free("unused")

    @classmethod
    def from_rom_map(cls, rommap, tags=set(), apply_offset=0):
        reg = Registry()
        with open(rommap, "r", encoding="utf-8") as fin:
            for beg, end, descr in csv.reader(fin.readlines()):
                beg = int(beg, base=16) - apply_offset
                end = int(end, base=16) - apply_offset + 1

                # make a shorter memorable name
                name = re.sub(r'\([^()]*\)', "", descr)
                name = "_".join([word[0] + re.sub(r"[aeiou]", "", word[1:], flags=re.I)[:4]
                                 for word in name.lower().strip().split(" ")])
                name = re.sub(r"[/'-,&]", "_", name, flags=re.I)
                _tags = set(descr.lower().split()) & tags

                if name in reg._blocks:
                    i = 0
                    while name + str(i) in reg._blocks:
                        i += 1
                    name = name + str(i)

                reg.register_block(beg, end - beg, name, descr, _tags)

        return reg

    # FIXME: have each type register with the randomizer explicitly
    def __getitem__(self, item):
        # semantic behavior --- applying tags will produce different object
        # reads
        if item in REGISTER_DATA:
            return REGISTER_DATA[item]()

        bare = super().__getitem__(item)
        if item in self._reg._tags.get("pointers", set()):
            return FF6PointerTable.from_super(bare)
        elif item in self._reg._tags.get("pointers", set()):
            return FF6PointerTable.from_super(bare)
        elif item in self._reg._tags.get("data", set()):
            return FF6DataTable.from_super(bare)
        elif item in self._reg._tags.get("program", set()):
            return AssemblyObject(bare.addr, bare.length, bare.name, bare.descr)
        elif item in self._reg._tags.get("names", set()) | \
                self._reg._tags.get("descriptions", set()) | \
                self._reg._tags.get("messages", set()):
            return FF6Text.from_super(bare)

        return bare

    def write(self, *args):
        # section, data, section, data, etc...
        pass

    def request_space(self, req_length, start=None, end=None, name=None, descr=None):
        res = self._reg.allocate(req_length, start, end)
        res.name = name or res.name
        res.descr = descr or res.descr
        return res

    # utils
    CHAR_NAME_LEN = 6
    def get_char_names(self, bindata, nbytes=CHAR_NAME_LEN):
        cnames_raw = self["chrct_nms"] << bindata
        return [cnames_raw[i * nbytes: (i + 1) * nbytes]
                for i in range(len(cnames_raw) // nbytes)]

    def get_unused_space_blks(self):
        return [self[k] for k in self._reg._tags.get("unused", [])]

    # Randomization functions
    def replace_event_battle_msgs(self, bindata, fname=None, randomize=False):
        from ....tasks import WriteBytes

        msgs = self["shrt_bttl_dlg"]
        ptrs = self["pntrs_t_shrt_bttl_dlg"]

        _OFFSET = 0xF0000

        # TODO: maybe also decode from JSON
        if fname is not None:
            with open(fname, "r") as fin:
                new_msgs = fin.readlines()
            # assume that the new messages do not have proper terminators
            # FIXME: figure out what's going on with the non-terminated
            # battle messages
            new_msgs = [msg + "\x04" for msg in new_msgs]
        else:
            new_msgs = FF6DataTable.from_super(msgs).dereference(bindata, ptrs, _OFFSET)
            new_msgs = [FF6Text._decode(t, strict=True) for t in new_msgs]

        # TODO: Check formatting
        assert len(new_msgs) <= 256

        # Pad to 256
        new_msgs += [""] * (256 - len(new_msgs))
        # Randomize if requested
        if randomize:
            new_msgs = [new_msgs[i] for i in randomization.shuffle_idx(256)]

        msg_data = [FF6Text._encode(p, replace_ctl_seq=True) for p in new_msgs]

        # FIXME: this should probably be handled by a component
        #_OFFSET = FF6PointerTable.maybe_parse_offset(ptrs.descr) or 0xF000
        ptr_data = [msgs.addr - _OFFSET]
        for msg in new_msgs[1:]:
            ptr_data.append(ptr_data[-1] + len(msg))

        ptr_data = b"".join([p.to_bytes(2, byteorder="little") for p in ptr_data])
        msg_data = b"".join(msg_data).ljust(msgs.length, b"\xff")

        # FIXME: Do we assert this?
        #msg_data = msg_data[:msgs.length]

        return [WriteBytes(msgs, msg_data), WriteBytes(ptrs, ptr_data)]

class FF6ProgressiveRandomizer(ProgressiveRandomizer):
    def __init__(self):
        super().__init__()
        # replace our registry with one specific to RAM
        self._reg = FF6SRAM()

    _EVENT_BITS = {

    }
    def check_events(self):
        pass

    def watch_location(self):
        for _ in range(100):
            time.sleep(1)
            self.scan_memory()
            print(self._ram[0x1EA5:0x1EA7])

    def watch_event_flags(self):
        event_flags = FF6EventFlags()
        self.scan_memory()
        events = event_flags << self._ram
        for _ in range(1000):
            time.sleep(1)
            self.scan_memory()
            _events = event_flags << self._ram
            diff = {k for k in events if _events[k] ^ events[k]}
            if len(diff) > 0:
                print(diff)
            else:
                print(f"No change: {sum(events.values())} {sum(_events.values())}")
            events = _events
