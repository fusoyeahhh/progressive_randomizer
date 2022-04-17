import fire

from . import FF6StaticRandomizer
from . import WriteQueue

import logging
log = logging.getLogger()
log.setLevel(logging.INFO)

#rom = open("ff6.smc", "rb").read()

#rando = FF6StaticRandomizer()
#pprint.pprint(rando._reg._blocks)
#pprint.pprint({**rando._reg._tags})

class DoAThing:
    def __init__(self, filename="ff6.smc"):
        with open(filename, "rb") as fin:
            self._romdata = fin.read()

        self._rando = FF6StaticRandomizer()
        self._q = WriteQueue()

    def print_tags(self):
        return {**self._rando._reg._tags}

    def print_component(self, comp):
        return str(self._rando[comp])

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
        from . import TASKS

        log.info(f"Queueing task {task} for component {comp}")
        task = TASKS[task](self._rando[comp])

        self._q.queue_write(task)
        return self

    def print_tasks(self):
        from . import TASKS
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
