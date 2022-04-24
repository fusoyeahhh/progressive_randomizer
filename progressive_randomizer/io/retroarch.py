import socket

import logging
log = logging.getLogger()

from . import BaseEmuIO

class RetroArchBridge(BaseEmuIO):
    def __init__(self):
        super().__init__()

        self.conn = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.conn.settimeout(10)

    @classmethod
    def _decode_resp(cls, resp):
        raw = [int(i, base=16) for i in resp.decode().strip().split()]
        # first entry is the memory location for read and writes
        # FIXME: could use this if needed
        addr = raw.pop(0)
        return raw

    def read_memory(self, st, en):
        assert en >= st
        cmd = b"READ_CORE_MEMORY "
        cmd += f"{st:x}".encode() + b" "
        cmd += f"{en - st:d}".encode() + b"\n"

        self.conn.sendto(cmd, ("127.0.0.1", 55355))

        log.info("SEND: " + cmd.decode("ascii"))
        # FIXME: single UDP packet is no larger than 65k
        resp, _ = self.conn.recvfrom(4 * (en - st) + 100)
        log.info("RECV: " + str(resp))
        assert resp.startswith(b"READ_CORE_MEMORY")

        return self._decode_resp(resp.replace(b"READ_CORE_MEMORY ", b""))

    def write_memory(self, st, val, get_resp=False):
        cmd = b"WRITE_CORE_MEMORY "
        cmd += f"{st:x}".encode() + b" "
        cmd += b" ".join([f"{b:02x}".encode() for b in val])

        log.info("SEND: " + cmd[:32].decode("ascii"))
        self.conn.sendto(cmd, ("127.0.0.1", 55355))

        if get_resp:
            resp, _ = self.conn.recvfrom(3 * len(val) + 100)
            log.info("RECV: " + str(resp))

    def display_msg(self, msg):
        cmd = b"SHOW_MSG " + msg.encode()
        self.conn.sendto(cmd, ("127.0.0.1", 55355))

    def ping(self, visual=False):
        try:
            if visual:
                self.display_msg("Ping!")
            self.read_memory(0x0, 0x1)
        except Exception as e:
            log.error(e)
            return False
        return True