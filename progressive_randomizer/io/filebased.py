import logging
log = logging.getLogger()

from io import BytesIO

from . import BaseEmuIO

class FileBasedBridge(BaseEmuIO):
    def __init__(self, fname):
        super().__init__()

        with open(fname, "rb") as fin:
            self._io = BytesIO(fin.read())

    def read_memory(self, st, en):
        self._io.seek(st)
        return self._io.read(en - st)

    def write_memory(self, st, val):
        self._io.seek(st)
        self._io.write(val)
