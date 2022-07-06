
import logging
log = logging.getLogger()

from . import Registry
from ..tasks import queues

class StaticRandomizer:
    def __init__(self):
        self._reg = Registry()

    def __getitem__(self, item):
        if not isinstance(item, tuple):
            item = (item,)

        if item[0] in self._reg._blocks:
            return self._reg._blocks[item[0]]
        elif len(item) != 3:
            raise KeyError(f"Block key {item[0]} not found in registry.")

        beg, end = item[1:]
        name = f"0x{beg:x}_0x{end:x}"
        descr = f"Autogenerated alias for block {name}"

        return self._reg.register_block(addr=beg, length=end - beg,
                                        name=name, descr=descr)

    def _register_non_documented_areas(self):
        undoc_reg = Registry()
        i, ptr = 0, 0x0
        blks = sorted(self._reg._tree.keys(), key=lambda t: t[0])
        for b1, b2 in blks:
            if b1 < ptr:
                continue
            ptr2 = b1

            undoc_reg.register_block(ptr, ptr2 - ptr,
                                     f"undoc_{i}",
                                     f"Undocumented Area {i}")
            ptr = b2

        return undoc_reg

    def decompile(self, bindata, fill_gaps=True):
        known = {name: blk << bindata for name, blk in self._reg._blocks.items()}
        # get all undocumented sections
        unknown = {name: blk << bindata
                   for name, blk in self._register_non_documented_areas()._blocks.items()}
        return {**known, **unknown}

    def compile(self, mmap, fill=b'\x00', binsize=None):
        # TOD: This should use a WriteQueue
        # TODO: check full coverage of all blocks
        # TODO: fill gaps
        # TODO: remap pointers
        bindata = b""
        for name, blk in sorted(mmap, key=lambda blk: len(blk[-1])):
            log.debug(f"Writing {len(blk)} bytes for section {name}")
            bindata += bytes(blk)

        pad = (binsize or len(bindata)) - len(bindata)
        assert pad >= 0
        return bindata + fill * pad

#
# Progressive stuff
#

class ProgressiveRandomizer(StaticRandomizer):
    def __init__(self):
        # TODO: should we do this with MI?
        from ..io.retroarch import RetroArchBridge
        super().__init__()
        self._q = queues.QueueController()
        self._bridge = RetroArchBridge()

        self._ram = None
        #self._rom = None

    def scan_memory(self, st=None, en=None, relative=False):
        # UDP limitations for retroarch, scan 2kib at a time
        _SNES_WRAM_BEGIN = max(0x7E0000, st or 0)
        _SNES_WRAM_END = min(0x800000, en or 2**64)
        st = max(_SNES_WRAM_BEGIN, st or 0)
        # FIXME: gotta either round up or do remainder
        en = min(_SNES_WRAM_END, en or 2**64)

        self._ram = []
        for st in range(st, en, 0x2000):
            size = min(0x2000, en - st)
            log.debug(f"Reading {size} bytes from {hex(st)}, ram size: {hex(len(self._ram))}")
            self._ram.extend(self._bridge.read_memory(st, st + size))

    def write_memory(self, addr, values, relative=False):
        # TODO: write to our RAM copy
        log.info(f"Writing {len(values)} bytes to {hex(addr)}")
        self._bridge.write_memory(addr, values)

    def run(self):
        #import threading
        #t = threading.Thread(target=self._run_loop)
        #t.start()
        self._run_loop()

    def dump(self, fname="ram_dump"):
        self.scan_memory()
        with open(fname, "wb") as fout:
            fout.write(bytes(self._ram))

    def _run_loop(self):
        while True:
            if not self._bridge.ping():
                raise RuntimeError("Lost connection to I/O bridge.")
            else:
                log.debug("Connection still alive.")