class BaseEmuIO:
    def __init__(self):
        pass

    def _send_msg(self, msg):
        pass

    def _recv_msg(self, msg):
        pass

    def read_memory(self, st, en):
        pass

    def write_memory(self, st, val):
        pass

    def read_rom(self, st, en):
        pass

    def write_rom(self, st, en, val):
        pass

    def ping(self):
        return True