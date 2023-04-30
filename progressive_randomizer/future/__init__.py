from ..game.ff6 import data

class FF6DataItemBuilder:
    class GenericItem:
        _spec = {}

        def __bytes__(self):
            return bytes([encoder(getattr(self, name))
                          for name, (_, _, _, encoder) in self._spec])

        @classmethod
        def parse_from_bytes(cls, bytestr):
            fields = {}
            for name, (itype, offset, bytelen, decoder, _) in cls._spec:
                if bytelen > 1 and decoder is None:
                    val = int.from_bytes(bytestr[:bytelen], byteorder="little")
                else:
                    val = (decoder or itype)(bytestr[:bytelen])
                bytestr = bytestr[:bytelen]

                fields[name] = val

            return cls(**fields)

    @classmethod
    def generate_item(cls, table, spec):
        import dataclasses
        name = table.__class__.__name__ + "Item"
        item_class = dataclasses.make_dataclass(
            name,
            [(fname, itype) for fname, (itype, _, _, _) in spec.items()],
            bases=(cls.GenericItem,)
        )
        item_class._spec = spec
        return item_class

# Example:
FF6DataItemBuilder.generate_item({
    # FIXME: inefficient
    #("item_type", 0, lambda b: FF6ItemTable.decode_item_meta(b)[0], 1, None),
    ("equipped_by", 1, data.EquipCharacter, 2, None),
    ("learn_rate", 3, int, 1, None),
    ("learned_spell", 4, data.Spell, 1, None),
    ("field_effect", 5, int, 1, None),
    ("status_1", 6, data.Status, 1, None),
    ("status_2", 7, lambda b: data.Status(b << 8), 1, None),
    ("equip_status", 8, lambda b: data.Status(b << 16), 1, None),
    ("equip_flags", 9, lambda b: data.EquipmentFlags.from_bytes, 5, None),

})

STRUCT_TMPLT = """
class {clsname}(MemoryStructure):
    \"\"\"
    {cls_doc_from_descr}
    \"\"\"

    {inner_enum}

    def __init__(self):
        super({addr}, {length}, {name}, {descr})

{reader_fcn}
"""

from .components import MemoryStructure
class CompilableMemoryStructure(MemoryStructure):
    def __init__(self, blk, bit_enum=None):
        super(blk.addr, blk.length, blk.name, blk.descr)
        self._bit_enum = bit_enum

    def construct(self):
        bitenum = self._bit_enum
        reader = {}
        if isinstance(bitenum, dict):
            def _read_with_mask(self, bindata):
                data = int.from_bytes(super().read(bindata), byteorder="little")
                return {name: data & mask
                        for name, mask in bitenum.items()}
            reader = {"read": _read_with_mask}
        elif isinstance(bitenum, (IntFlag, IntEnum)):
            def _read_with_flag(self, bindata):
                data = int.from_bytes(super().read(bindata), byteorder="little")
                return bitenum(data)
            reader = {"read": _read_with_mask}

        return type(self.name, (MemoryStructure,), reader)
        

hex_digits = re.compile(r"\$[0-9A-F]+")
nonalphanum = re.compile(r"[)(#/\\+]")
def normalize_name(name):
    name = hex_digits.sub("", name).strip()
    name = nonalphanum.sub("", name).strip()
    return name.replace(" ", "_").lower().strip()

class MemoryBlockParser:
    def parse_layout_file(self, fname):
        with open(fname, "r") as fin:
            lines = fin.readlines()

        reg = Registry()
        while len(lines) > 0:
            line = lines.pop(0)
            if line.strip() == "":
                continue
            try:
                self.try_parse_header(line)
                print(f"Parsing and discarding presumed header: {line}")
                continue
            except:
                pass

            blk = None
            try:
                blk = self.try_parse_memory(line, reg)
                if blk is not None and len(lines) > 0:
                    lookahead = self.try_parse_bit_enum(blk, lines)
            except ValueError as e:
                #print(e)
                pass
        return reg

    def try_parse_header(self, line):
        locs, descr = line.strip().split(":")
        b, e = locs.split("-")
        b = int(b.replace("$", ""), base=16), int(e.replace("$", ""), base=16)

    def try_parse_memory(self, line, reg):
        _line = line.strip().split(" ")
        loc = _line.pop(0).strip()

        nbytes = 1
        if loc.startswith("+"):
            nbytes += loc.count("+")
            loc = loc.replace("+", "")

        try:
            if "-" in loc:
                beg, end = loc.replace("$", "").split("-")
                beg, end = int(beg, base=16), int(end, base=16)
                nbytes = end - beg
            else:
                beg = int(loc.replace("$", ""), base=16)
                end = beg + nbytes
        except Exception as e:
            raise ValueError("Not a memory descriptor.")

        if reg is None:
            return None

        descr = line.strip()
        name = normalize_name(descr) or f"section_{hex(beg)}_{hex(end)}"
        blk = reg.register_block(beg, nbytes, name, descr)

        return blk

    def try_parse_bit_enum(self, block, lines):
        try:
            self.try_parse_memory(lines[0], None)
            return
        except ValueError:
            pass

        descr = block.descr.strip().split(" ")[1]
        if len(descr) == 8 * block.length:
            benum = self.parse_enum(descr, lines, block.name)
            # TODO: attach benum to block somehow
            #print(list(benum))
            return

        descr = lines.pop(0).strip().replace(" ", "")
        if len(descr) == 8 * block.length:
            benum = self.parse_enum(descr, lines, block.name)
            #print(list(benum))
            return

    def parse_enum(self, descr, lines, name):
        is_masked_var = list(descr.replace("-", ""))
        is_masked_var = len(set(is_masked_var)) != len(is_masked_var)

        enum_type = "flag"
        if is_masked_var:
            _enum = self.handle_var_mask(descr)
            enum_type = "mask"
        else:
            _enum = {c: i for i, c in enumerate(descr[::-1]) if c != '-'}

        for i, line in enumerate(lines[:len(_enum)]):
            line = line.strip()

            if ":" in line:
                c, d = line.split(":")
                v = _enum.pop(c, i)
                _enum[d.strip().replace(" ", "_")] = v
            elif "=" in line:
                enum_type = "intenum"
                c, d = line.split("=")
                # TODO: parse actual i
                v = _enum.pop(c, i)
                _enum[d.strip().replace(" ", "_")] = v

        if enum_type == "flag":
            return IntFlag(name, _enum)
        elif enum_type == "intenum":
            return IntEnum(name, _enum)
        else:
            return _enum

    def handle_var_mask(self, descr):
        descr = list(descr)[::-1]
        masks, last = {}, None
        for i, c in enumerate(descr):
            mask = masks.get(c, 0)
            masks[c] = mask | (1 << i)

        masks.pop('-', None)
        return masks

