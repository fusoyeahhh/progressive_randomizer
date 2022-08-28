import random
from dataclasses import dataclass, asdict
import logging
log = logging.getLogger()

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
    StatRandomizer
)
from ..data import (
    Item,
    InventoryType,
    EquipmentFlags,
)

from . import BoundedQuantity

@dataclass
class ItemData:

    item_idx: Item
    item_qty: BoundedQuantity

    def __bytes__(self):
        return bytes([int(self.item_idx), int(self.item_qty)])

    @classmethod
    def decode(cls, data):
        return {
            "item_idx": Item(data[0]),
            "item_qty": BoundedQuantity(data[1], max_value=0xFF)
        }

    @classmethod
    def from_bytes(cls, data):
        return cls(**cls.decode(data))

    @classmethod
    def from_ram(cls, bindata):
        #raw_data = FF6SRAM() << bytes(bindata)

        items = bindata[0x1869:0x1969]
        qty = bindata[0x1969:0x1A69]

        return [cls.from_bytes(bytes([i, q])) for i, q in zip(items, qty)]

class InventoryManager(FF6ProgressiveRandomizer):
    def __init__(self):
        super().__init__()
        self.sram_inventory = {}
        self.inventory = []

    def read_inventory(self):
        self.scan_memory()
        self.inventory = ItemData.from_ram(self._ram)

    def write_inventory(self):
        inv = b"".join([bytes(item) for item in self.inventory])
        self.write_memory(0x1869, bytes(inv[::2]))
        self.write_memory(0x1969, bytes(inv[1::2]))

    def get_or_create(self, get_item, diff=None):
        slot = None
        for item in self.inventory:
            if item.item_idx == get_item:
                slot = item

        if get_item is Item.Blank and slot is None:
            raise IndexError("No empty inventory slots.")

        slot = slot or self.get_or_create(Item.Blank)
        slot.item_idx = get_item
        if diff is not None:
            slot.item_qty += diff
        return slot

    def __getitem__(self, idx):
        return self.inventory[idx]

    def __setitem__(self, idx, value):
        self.inventory[idx] = value

    def __hash__(self):
        return hash(b"".join(sorted([bytes(item)
                                     for item in self.inventory])))

    def format_inventory(self, supress_empty=True):
        inv = "\n".join([f"{str(Item(item.item_idx))}: {item.item_qty.value}"
                         for item in self.inventory
                         if not (supress_empty and item.item_idx == Item.Blank)])
                         #for idx, idx2 in self.sram_inventory.items()])
        return inv

# Thought: MI from StaticRandomizer and FF6ItemTable?
class FF6ItemManager(FF6StaticRandomizer):
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

    def handle_weapon_flags(self, item):
        pass

    def handle_item_flags(self, item):
        pass

    def edit(self, item):
        pass

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
    mngr = FF6ItemManager()
    # Print out some stuff from args
