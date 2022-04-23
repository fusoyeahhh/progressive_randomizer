import socket

import logging
log = logging.getLogger()

from . import BaseEmuIO

class RetroArchBridge(BaseEmuIO):
    def __init__(self):
        super().__init__()

        self.conn = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.conn.settimeout(1)

    def read_memory(self, st, en):
        cmd = b"READ_CORE_MEMORY "
        cmd += f"{st:x}".encode() + b" "
        cmd += f"{en - st:d}".encode() + b"\n"

        self.conn.sendto(cmd, ("127.0.0.1", 55355))

        resp, _ = self.conn.recvfrom(4 * (en - st) + 10)
        assert resp.startswith(b"READ_CORE_MEMORY")

        # FIXME: I think this needs to be decoded
        return resp.replace(b"READ_CORE_RAM f ", b"")

    def write_memory(self, st, en, val):
        cmd = b"WRITE_CORE_MEMORY "
        cmd += f"{st:x}".encode + b" "
        cmd += b" ".join(["{b:02x}".encode() for b in val])

        self.conn.sendto(cmd, ("127.0.0.1", 55355))

    def display_msg(self, msg):
        cmd = b"SHOW_MSG " + msg.encode()
        self.conn.sendto(cmd, ("127.0.0.1", 55355))

        #resp, _ = self.conn.recvfrom(4096)
        #assert resp.startswith(b"READ_CORE_RAM")

        ## FIXME: I think this needs to be decoded
        #return resp

    def ping(self):
        try:
            self.read_memory(0x0, 0x1)
        except Exception as e:
            log.error(e)
            print(e)
            return False
        return True