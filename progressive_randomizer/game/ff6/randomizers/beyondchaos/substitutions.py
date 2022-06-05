from io import BytesIO

from .....tasks import WriteBytes

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



enable_esper_magic_writes = {
    "enable_esper_magic_1": {
        "location": 0x34D3D,
        "bytestring": bytes([0x20, 0xDD, 0x4E,
                             0xA6, 0x00, 0xB9, 0x00, 0x00, 0xC9, 0x0E, 0xB0, 0x04,
                             0xA9, 0x20, 0x80, 0x02, 0xA9, 0x24,
                             0x95, 0x79,
                             0xE8,
                             0xA9, 0x24, 0x60])
    },
    "enable_esper_magic_2": {
        "location": 0x3F09F,
        # NOTE: this truncates the location address
        # Could also be b"\x20\x9F\xF0\0xEA"
        # but it's encoding a JSR -- we may want to make a utility for this
        "bytestring":  bytes([0x20]) + 0x3F09F.to_bytes(3, byteorder="little")[:2]
                       + bytes([0xEA])
    }
}

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
        "location": 0xA18A,
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
    # NOTE: soft conflict here against multiple_sub_3 with the 0xEA writes
    "learn_blitz_sub_3": {
        "location": 0x261D9,
        "bytestring":  bytes([0x68, 0xEB, 0xEA, 0xEA, 0xEA, 0xEA])
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

    "rage_blank_sub": {
        "location": 0x47AA0,
        "bytestring": bytes([0x01] + ([0x00] * 31))
    },

    **enable_esper_magic_writes,

    "enable_xmagic_menu_sub_1": {
        "location": 0x3F091,
        "bytestring": bytes([0xDF, 0x78, 0x4D, 0xC3,
                             0xF0, 0x07,
                             0xE0, 0x01, 0x00,
                             0xD0, 0x02,
                             0xC9, 0x17,
                             0x6B])
    },
    "enable_xmagic_menu_sub_2": {
        "location": 0x34D56,
        "bytestring": bytes([0x22, 0x91, 0xF0, 0xC3])
    },
    "protect_battle_commands_sub": {
        "location": 0x252E9,
        "bytestring": [0x03, 0xFF, 0xFF, 0x0C, 0x17, 0x02, 0xFF, 0x00]
    },
    "enable_morph_sub": {
        "location": 0x25410,
        "bytestring": bytes([0xEA] * 2)
    },
    "enable_mpoint_sub": {
        "location": 0x25E38,
        "bytestring": bytes([0xEA] * 2)
    },
    "ungray_statscreen_sub": {
        "location": 0x35EE1,
        "bytestring": [0x20, 0x6F, 0x61, 0x30, 0x26, 0xEA, 0xEA, 0xEA]
    },
    # fanatics_fix_sub
    "fanatics_fix_sub": {
        "location": 0x2537E,
        # value depends on "metronome"
        "bytestring": []
    },

}