from .... import MemoryLayoutParser
from ....components import Registry

class FF6SRAM(Registry):
    def __init__(self):
        super().__init__()

        for blk in MemoryLayoutParser.parse("etc/ff6_sram_descr.txt")._blocks.values():
            self.register_block(blk.addr, blk.length, blk.name, blk.descr)

class FF6BattleRAM(Registry):
    def __init__(self, reg):
        super().__init__()
        self._reg = reg

    def _setup(self):
        blks = [
            dict(addr=0x0, length=0x100, name="bttl_dp",
                 descr="$0000-$00FF: Battle Direct Page"),
            dict(addr=0x0100, length=0x100, name="bttl_ram",
                 descr="$0100-$01FF: Battle RAM | Used by battle menus."),
            # ...
            dict(addr=0x1600, length=0x2000 - 0x1600, name="sram",
                 descr="$1600-$1FFF: Save RAM | SRAM"),
            # ...
        ]

        for blk in blks:
            self.register_block(**blk)
