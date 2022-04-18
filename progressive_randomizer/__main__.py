import pprint
import fire

from . import StaticRandomizer, WriteQueue, SNESHeader
from .tasks import TASKS

import logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger()

def _read_header(filename):
    with open(filename, "rb") as fin:
        romdata = fin.read(0x10000)

    return SNESHeader() << romdata

def autodetect_and_load_game(filename):
    from .game import KNOWN_GAMES
    header_data = _read_header(filename)
    game_name = header_data["Game Title Registration"]

    if game_name not in KNOWN_GAMES:
        log.warning("Game does not have a registered randomizer, "
                    "using default --- some functions may not be available.")
    rando = KNOWN_GAMES.get(game_name, StaticRandomizer)()
    log.info(f"Read header, game name: {game_name} -> {rando}")

    with open(filename, "rb") as fin:
        romdata = fin.read()

    return romdata, rando

class DoAThing:
    def __init__(self, filename="ff6.smc"):
        self._filename = filename
        self._romdata, self._rando = autodetect_and_load_game(filename)
        self._q = WriteQueue()

    def print_header(self):
        return pprint.pformat(_read_header(self._filename))

    def print_tags(self):
        return {**self._rando._reg._tags}

    def print_component(self, comp):
        return str(self._rando[comp])

    def print_ram_layout(self):
        from .game.ff6 import FF6SRAM
        return pprint.pformat(FF6SRAM()._blocks)

    def decode_raw(self, comp):
        return self._rando[comp] << self._romdata

    def decode_tabular(self, comp, bytes_per_row=16, prefix_addr=True):
        rawdata = self._rando[comp] << self._romdata
        tabdata = ""
        offset = self._rando[comp].addr
        while rawdata:
            row, rawdata = rawdata[:bytes_per_row], rawdata[bytes_per_row:]
            if prefix_addr:
                tabdata += f"0x{offset:08x}: "
            tabdata += " ".join([f"0x{val:02x}" for val in row])
            tabdata += "\n"
            offset += bytes_per_row
        return tabdata

    def decode_text(self, comp):
        return self._rando[comp].read(self._romdata)

    def annotate_assembly(self, comp):
        return self._rando[comp].annotate(self._romdata)

    # FIXME: why do we need a terminator?
    def write(self, filename="test.smc"):
        #print(self._rando[comp] << self._romdata)
        result = self._q.flush(self._romdata)
        #print(self._rando[comp] << result)

        # write file
        log.info(f"Writing result to {filename}")
        assert len(self._romdata) == len(result)
        #with open(filename, "wb") as fout:
            #fout.write(result)

        return

    def apply_randomizer_task(self, comp, task):
        log.info(f"Queueing task {task} for component {comp}")
        task = TASKS[task](self._rando[comp])

        self._q.queue_write(task)
        return self

    def print_tasks(self):
        import pprint
        return pprint.pformat(TASKS)


fire.Fire(DoAThing())

"""
spell_ptr_table = FF6PointerTable.from_super(rando["pntrs_t_spll_dscrp"])
print(spell_ptr_table, spell_ptr_table.ptr_offset)
print(spell_ptr_table << rom)
spell_table = FF6DataTable.from_super(rando["spll_dscrp"])
print(spell_table)
print([FF6Text._decode(text)
       for text in spell_table.dereference(rom, spell_ptr_table)])

#print(rando["itm_dt"].dereference(rom))
print(rando["bttl_cmmnd_nms"] << rom)

#print(rando["bttl_prgrm"] << rom)
#print(AssemblyObject._disassemble(rando["bttl_prgrm"] << rom))
print(rando["bttl_prgrm"].annotate(rom))

"""