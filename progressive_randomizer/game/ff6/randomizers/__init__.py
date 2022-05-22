from .... import AssemblyObject

from ....components.randomizers import (
    StaticRandomizer,
    ProgressiveRandomizer
)

from ..components import (
    FF6PointerTable,
    FF6DataTable,
    FF6Text,
    FF6BattleMessages,
    FF6SRAM,
    FF6EventFlags
)

from .. import REGISTER_DATA
from .. import ROM_MAP_DATA, ROM_DESCR_TAGS

from ....utils import randomization

class FF6StaticRandomizer(StaticRandomizer):
    def __init__(self):
        super().__init__()
        self._reg = StaticRandomizer.from_rom_map(ROM_MAP_DATA,
                                                  ROM_DESCR_TAGS,
                                                  apply_offset=0xC00000)

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

        msgs = self["bttl_mssgs"]
        ptrs = self["pntrs_t_bttl_mssgs"]

        # TODO: maybe also decode from JSON
        if fname is not None:
            with open(fname, "r") as fin:
                new_msgs = fin.readlines()
        else:
            new_msgs = msgs << bindata

        # TODO: Check formatting
        #assert len(new_msgs) <= 256

        # Pad to 256
        new_msgs += [""] * (256 - len(new_msgs))
        # Randomize if requested
        if randomize:
            new_msgs = [new_msgs[i] for i in randomization.shuffle_idx(256)]

        msg_data = [FF6Text._encode(p) + FF6BattleMessages._TERM_CHAR
                    for p in new_msgs]

        # FIXME
        #_OFFSET = FF6PointerTable.maybe_parse_offset(ptrs.descr) or 0xF000
        _OFFSET = 0xF000
        ptr_data = [_OFFSET]
        for msg in new_msgs[1:]:
            ptr_data.append(ptr_data[-1] + len(msg))

        ptr_data = b"".join([p.to_bytes(2, byteorder="little") for p in ptr_data])
        msg_data = b"".join(msg_data)
        WriteBytes(ptrs, ptr_data)

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
        import time
        for _ in range(100):
            time.sleep(1)
            self.scan_memory()
            print(self._ram[0x1EA5:0x1EA7])

    def watch_event_flags(self):
        import time
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
