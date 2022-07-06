import random
from dataclasses import dataclass, asdict
import logging
log = logging.getLogger()

#from .. import data

from ....components import MemoryStructure
from ....utils.randomization import random_prob, choice_without_replacement
from ....tasks import WriteBytes

from ..components import (
    FF6Text,
    FF6SRAM,
    FF6ItemTable
)
from ..randomizers import (
    FF6StaticRandomizer,
    FF6ProgressiveRandomizer,
    AttributeRandomizer,
    SpellRandomizer,
    StatusRandomizer,
    StatRandomizer
)
from ..data import (
    Character,
    Command,
    Item,
    InventoryType
)

class FF6CommandManager(FF6StaticRandomizer):
    def __init__(self):
        super().__init__()
        # FIXME: We may need a parent rando to reconfigure this one in the future
        #self._rando = rando
        self.cmd_data = {}

    def populate(self, bindata):
        # Gather command data
        cmd_names = FF6Text._decode(self["bttl_cmmnd_nms"] << bindata, 7)
        cmd_data = self["bttl_cmmnd_dt"] << bindata
        self.cmd_data = dict(zip(cmd_names, cmd_data))

    # BC style
    def _get_random_commands(self, cmd_pool, only_unique=True,
                             item_prob=0.5, magic_prob=0.5,
                             xmagic_prob=0.5, n=3):
        commands = []
        # determine if x-magic is part of the menu
        if random_prob(xmagic_prob):
            commands.append(Command.X_Magic)
        elif random_prob(magic_prob):
            commands.append(Command.Magic)
        # determine if item is part of the menu
        if random_prob(item_prob):
            commands.append(Command.Item)

        n -= len(commands)
        if n <= 0:
            return commands

        # TODO: handle giving "nothing" instead
        allow_pad = True
        if len(cmd_pool) < n and not allow_pad:
            log.warning("Attempting draw a commands from pool without enough "
                        "left.\nThis will probably fail.")
        new_cmds = choice_without_replacement(list(cmd_pool), k=n)

        if only_unique:
            cmd_pool -= set(new_cmds)
        commands += new_cmds
        if allow_pad and len(commands) < n:
            commands += [Command.Nothing] * (n - len(commands))
        return commands

    def plando(self, chars, cmd_data):
        for c, commands in cmd_data.items():
            chars[c].commands = commands

        return chars

class FF6CharacterManager(FF6StaticRandomizer):
    _MORPH_MEMBLK = MemoryStructure(addr=0x25E32, length=2, name="morph_data",
                                    descr="Character specific morph byte data")

    @classmethod
    def validate(cls, chr_data):
        if len(chr_data) != 16:
            log.warning("Attempting to modify more or less than all 16 characters.")

        # FIXME: does this always have to be fight?
        if not all([c.commands[0] is Command.Fight for c in chr_data.values()
                    if c.idx < Character.Gau]):
            log.error("All characters must have Fight as the first command.")
            raise RuntimeError()

        # evidently gogo has to have mimic?
        gogo = [c for c in chr_data.values() if c.idx == Character.Gogo][0]
        if gogo.commands[0] is not Command.Mimic:
            log.error("Gogo must have Mimic as the first command.")
            raise RuntimeError()

    @classmethod
    def package(cls, chr_data):
        # TODO: names
        cls.validate(chr_data)
        raw_data = b""
        for cdata in sorted(chr_data.values(), key=lambda c: c.idx):
            raw_data += bytes(cdata)

        return raw_data

    def __init__(self):
        super().__init__()
        # FIXME: We may need a parent rando to reconfigure this one in the future
        #self._rando = rando
        self.chr_data = {}

    def populate(self, bindata):
        # Gather command data
        self.chr_names = FF6Text._decode(self["chrct_nms"] << bindata, 6)
        #chr_ids = [Character(i) for i in range(len(self.chr_names))]
        # FIXME:
        chr_ids = [Character(i) for i in range(16)]
        chr_data = self["chrct_intl_prprt"] << bindata
        self.chr_data = dict(zip(chr_ids, chr_data))

    def randomize_commands(self, invalid, cmd_mgr, shuffle_cmds=False, replace_cmds=False,
                           unique_xmagic=True, force_only_cmd=None, force_skill_cmd=None,
                           **kwargs):
        # populate pool
        cmd_pool = {Command(c.idx) for n, c in cmd_mgr.cmd_data.items() if c.idx not in invalid}
        xmagic_used = False

        for char in self.chr_data.values():
            # "fix" Gau
            if shuffle_cmds or replace_cmds and char.idx is Character.Gau:
                char.commands[0] = Command.Fight

            # example: this is used in "metronome" in BC to set skill to Magitek
            if force_skill_cmd is not None:
                char.commands = [Command.Fight, Command(force_skill_cmd),
                                 Command.Magic, Command.Item]
                continue

            # Force the menu to have only one command (I think?)
            # TODO: why does BC only fill the last three slots?
            if force_only_cmd is not None:
                char.commands = [char.command[0], Command.Nothing,
                                 Command.Nothing, Command(force_only_cmd)]
                continue

            # Handle "special characters differently
            if char.idx > Character.Gau:
                char.commands = [char.commands[0], Command.Nothing,
                                 Command.Nothing, char.commands[-1]]
                continue

            # zero out X-magic probability if we have and we're unique
            xmagic_prob = kwargs.pop("xmagic_prob", 0.5) \
                            if not (xmagic_used and unique_xmagic) else 0
            char.commands[1:] = cmd_mgr._get_random_commands(cmd_pool,
                                                         xmagic_prob=xmagic_prob,
                                                         **kwargs)
            xmagic_used |= Command.X_Magic

            log.info(f"New commands for {str(Character(char.idx))}: {char.commands}")

        tasks = [WriteBytes(self["chrct_intl_prprt"], self.package(self.chr_data))]
        return tasks + self._handle_morph_changes()

    def _handle_morph_changes(self):
        for c in self.chr_data.values():
            if Command.Morph in c.commands:
                return [WriteBytes(self._MORPH_MEMBLK, bytes([0xC9, c.idx]))]
        return []# Thought: MI from StaticRandomizer and FF6ItemTable?
class ItemManager(FF6StaticRandomizer):
    _BASE_ITEM_TMPLT = FF6ItemTable.ItemEntry

    def handle_spell_proc(self, item, spell=None, random_cast=None, inv_remove=None):
        item["cast_spell"] = spell or AttributeRandomizer.spells(skillsets={"magic"})
        item["random_cast"] = random_cast or bool(random.randint(0, 1))
        item["inv_remove"] = inv_remove or bool(random.randint(0, 1))
        return item

    def handle_spell_learning(self, item, spell=None, closeness=50):
        # TODO: handle tiering
        item["learned_spell"] = spell or AttributeRandomizer.spells(skillsets={"magic"})
        lr = max(1, item["learn_rate"])
        item["learn_rate"] = AttributeRandomizer.spells.gen_learning_rate(lr, closeness)
        return item

    def generate(self, base, tmplt=None, mixing_ratio=0.1, closeness=100, keep=set(),
                 element_gen=0.1, status_gen=0.1, field_effect_gen=0.1, equip_effect_gen=0.1,
                 learn_spell_prob=0.01, gen_proc_prob=0.05):
        assert tmplt is None or base.item_type == tmplt.item_type

        base_item = asdict(base)
        new_item = base_item.copy()
        for attr in self._BASE_ITEM_TMPLT.__dataclass_fields__:
            if attr in keep:
                log.info(f"base {base.name} | attr {attr}: {base_item[attr]} -> NO CHANGE")
                continue

            if tmplt is not None and random.uniform(0, 1) < mixing_ratio:
                new_item[attr] = tmplt[attr]

            # FIXME: for both spells, we can modify rates / flags independently
            # if they are valid
            if attr == "learned_spell" \
                and (new_item["learn_rate"] > 0 or learn_spell_prob < random.uniform(0, 1)):
                self.handle_spell_learning(new_item, closeness=closeness)
            elif attr == "cast_spell" \
                 and (new_item["random_cast"] > 0 or new_item["inv_remove"]
                   or learn_spell_prob < random.uniform(0, 1)):
                self.handle_spell_learning(new_item, closeness=closeness)
            elif attr == "equipped_by":
                new_item[attr] = AttributeRandomizer.equipchar.shuffle(new_item[attr],
                                                                       mix_ratio=0.5,
                                                                       fuzzy=True)
            elif attr == "field_effect":
                new_item[attr] = AttributeRandomizer.fieldeffect.shuffle(new_item[attr],
                                                                         fuzzy=True,
                                                                         generate=field_effect_gen)
            elif attr == "equip_flags":
                exclude = {EquipmentFlags.UNKNOWN, EquipmentFlags.UNKNOWN_2,
                           EquipmentFlags.UNKNOWN_3, EquipmentFlags.UNKNOWN_4}
                new_item[attr] = AttributeRandomizer.equipflags.shuffle(new_item[attr],
                                                                        fuzzy=True,
                                                                        exclude=exclude,
                                                                        generate=equip_effect_gen)
            elif attr == "status_1":
                new_item[attr] = AttributeRandomizer.status.shuffle(new_item[attr],
                                                                    fuzzy=True,
                                                                    generate=status_gen,
                                                                    only_bytes={0})
            elif attr in "status_2":
                new_item[attr] = AttributeRandomizer.status.shuffle(new_item[attr],
                                                                    fuzzy=True,
                                                                    generate=status_gen,
                                                                    only_bytes={1})
            elif attr in "equip_status":
                new_item[attr] = AttributeRandomizer.status.shuffle(new_item[attr],
                                                                    fuzzy=True,
                                                                    generate=status_gen,
                                                                    only_bytes={2})
            elif attr in "_equipment_status":
                new_item[attr] = AttributeRandomizer.status.shuffle(new_item[attr],
                                                                    fuzzy=True,
                                                                    generate=status_gen,
                                                                    only_bytes={1})
            elif attr == "elemental_data":
                new_item[attr] = AttributeRandomizer.element.shuffle(new_item[attr],
                                                                     fuzzy=True,
                                                                     generate=element_gen)
            elif attr == "targeting":
                new_item[attr] = AttributeRandomizer.spelltargeting(new_item[attr])
            elif attr in {"vigor", "speed", "stamina", "magic"}:
                new_item[attr] = StatRandomizer(-7, 7)(new_item[attr], closeness)
            elif attr in {"evade", "magic_evade"}:
                new_item[attr] = StatRandomizer(0, 15)(new_item[attr], closeness)
            elif attr == "power":
                # This wpn pwr / armor def / item heal
                new_item[attr] = StatRandomizer(0, 255)(new_item[attr], closeness)
            elif attr == "actor_status_1":
                # This wpn hit rate / armor mag def / item status
                if base.item_type == InventoryType.Item:
                    new_item[attr] = AttributeRandomizer.status.shuffle(new_item[attr],
                                                                        fuzzy=True,
                                                                        only_bytes={0})
                else:
                    new_item[attr] = StatRandomizer(0, 255)(new_item[attr], closeness)
            elif attr in {"actor_status_2", "actor_status_3", "actor_status_4"}:
                # This wpn and armor elem {absorb,null,weak} / item status
                if base.item_type == InventoryType.Item:
                    new_item[attr] = AttributeRandomizer.status.shuffle(new_item[attr],
                                                                        fuzzy=True,
                                                                        only_bytes={0})
                else:
                    new_item[attr] = AttributeRandomizer.element.shuffle(new_item[attr],
                                                                         fuzzy=True,
                                                                         generate=element_gen)
            elif attr == "price":
                new_item[attr] = StatRandomizer(0, 2**16 - 1)(new_item[attr], closeness)

            log.debug(f"base {base.name} | {attr}: {base_item[attr]} -> {new_item[attr]}")

        return self._BASE_ITEM_TMPLT(**new_item)

    def read(self, bindata):
        item_names = FF6Text._decode(self["itm_nms"] << bindata, 13)
        item_descr = self["itm_dscrp"].from_ptr_table(self["pntrs_t_itm_dscrp"], bindata)
        item_data = dict(zip(item_names, self["itm_dt"] << bindata))

        # FIXME: maybe the item object should know where to retrieve its own name / data?
        for name, descr, key in zip(item_names, item_descr, item_data):
            item_data[name].name = name
            item_data[name].descr = descr

        return item_data

    def write(self, items):
        # FIXME: these aren't writing the item icons and such
        item_names = [FF6Text._encode(item.name) for item in items.values()]
        item_descr = [FF6Text._encode(item.descr) for item in items.values()]
        item_data = map(bytes, items.values())

        return [
            WriteBytes(self["itm_dt"], b''.join(item_data)),
            WriteBytes(self["itm_dscrp"], b''.join(item_descr)),
            WriteBytes(self["itm_nms"], b''.join(item_names))
        ]

    def randomize_items(self, bindata, **kwargs):
        item_data = self.read(bindata)
        log.info(f"Decoded {len(item_data)} items")

        ignore_empty = kwargs.pop("ignore_empty", True)

        for name in item_data:
            # Don't randomize Empty, as it has invalid values
            if ignore_empty and name == " Empty".ljust(13, " "):
                continue
            item_data[name] = self.generate(item_data[name], **kwargs)

        print("\n".join(self.write_spoiler(item_data.values(),
                                           ignore_empty=ignore_empty)))
        return self.write(item_data)

    def write_spoiler(self, items, ignore_empty=True):
        return [item.spoiler_text(i)
                for i, item in enumerate(items)
                if (True if i != 255 else ignore_empty)]

if __name__ == "__main__":
    mngr = ItemManager()
    # Print out some stuff from args