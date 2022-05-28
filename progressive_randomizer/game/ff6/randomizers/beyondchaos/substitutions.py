from io import BytesIO

from .....tasks import (
    RandomizationTask,
    WriteBytes
)

from .....components import (
    AssemblyObject,
    MemoryStructure
)

from BeyondChaos import utils

# FIXME: Do we want to inherit from WriteBytes?
class SubstitutionTask(WriteBytes):
    """
    Wrapper for the Substitution class writer from BC.
    """
    @classmethod
    def sub_with_args(cls, location=None, bytestring=None,
                      sub=utils.Substitution, subkwargs={}, **kwargs):
        sub = sub(**subkwargs)
        sub.set_location(location)
        sub.bytestring = bytestring
        # TODO: callback?
        return cls(sub, **kwargs)

    @classmethod
    def from_dict(cls, subs):
        return [cls.sub_with_args(name=name, **args) for name, args in subs.items()]

    def __init__(self, substitution, **kwargs):
        self._sub = substitution
        name = kwargs.get("name", "bc:" + str(self._sub))
        descr = kwargs.get("descr", "dummy memblk")
        subs = MemoryStructure(addr=self._sub.location,
                               length=len(self._sub.bytestring),
                               name=name, descr=descr)
        super().__init__(subs, self._sub.bytestring)

    def apply(self, bindata):
        buffer_writer = BytesIO(bindata)
        self._sub.write(buffer_writer)
        return buffer_writer.getvalue()

    def as_assembly(self):
        return AssemblyObject(addr=self._sub.location,
                              length=len(self._sub.bytestring),
                              name=str(self._sub),
                              descr="substitution assembly block")

manage_commands_writes = {
    "learn_lore_sub": {
        "location": 0x236E4,
        "bytestring": bytes([0xEA, 0xEA, 0xF4, 0x00, 0x00, 0xF4, 0x00, 0x00])
    },

    "learn_dance_sub": {
        "location": 0x25EEB,
        "bytestring": bytes([0xEA, 0xEA])
    },

    "learn_swdtech_sub": {
        "location": 0x261C7,
        "bytestring": bytes([0xEB, 0x48, 0xEB, 0xEA])
    },
    "learn_swdtech_sub_2": {
        "location": 0x261D3,
        "bytestring": bytes([0x68, 0xEB] + [0xEA] * 4)
    },

    "learn_blitz_sub": {
        "location": 0x261CE,
        "bytestring": bytes([0xF0, 0x09]),
    },
    "learn_blitz_sub_2": {
        "location": 0x261D3,
        "bytestring": bytes([0xD0, 0x04])
    },
    "learn_blitz_sub_3": {
        "location": 0x261D9,
        "bytestring":  bytes([0x68, 0xEB, 0xEA, 0xEA, 0xEA, 0xEA, 0xEA])
    },
    "learn_blitz_sub_4": {
        "location": 0x261E3,
        "bytestring": bytes([0xEA] * 4),
    },
    "learn_blitz_sub_5": {
        "location": 0xA200,
        "bytestring": bytes([0xEA]),
    },

    "learn_multiple_sub": {
        "location": 0xA1B4,
        "bytestring": bytes([0xF0, 0xFE - (0xA1B4 - 0xA186)])
    },
    "learn_multiple_sub_2": {
        "location": 0xA1D6,
        "bytestring": bytes([0xF0, 0xFE - (0xA1D6 - 0xA18A)])
    },
    "learn_multiple_sub_3": {
        "location": 0x261DD,
        "bytestring": bytes([0xEA] * 3)
    },

    "range_blank_sub": {
        "location": 0x47AA0,
        "bytestring": bytes([0x01] + ([0x00] * 31))
    },
}

