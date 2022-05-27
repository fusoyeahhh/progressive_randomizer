from ....components import MemoryStructure

# Upper case
_CHARS = {128 + i: chr(j) for i, j in enumerate(range(65, 65 + 26))}
# Lower case
_CHARS.update({154 + i: chr(j) for i, j in enumerate(range(97, 97 + 26))})
# Numbers
_CHARS.update({180 + i: chr(j) for i, j in enumerate(range(48, 48 + 10))})
# FIXME: Will probably need symbols at some point
_CHARS[190] = "!"
_CHARS[191] = "?"
_CHARS[193] = ":"
_CHARS[195] = "'"
_CHARS[196] = "-"
_CHARS[197] = "."
_CHARS[198] = ","
_CHARS[0xd3] = "["
_CHARS[0xc2] = "]"
_CHARS[199] = "..."  # ellipsis character
_CHARS[255] = " "

# Handle 1-byte converted control sequences
_CHARS[0x04] = "\x04"
_CHARS[0x05] = "\x05"
_CHARS[0x0A] = "\n"
_CHARS[0x11] = "..."

_CHARS[0x00] = "\x00"
_CHARS[0x12] = "\x12"
_CHARS[0x13] = "\x13"
_CHARS[0x14] = "\x14"
_CHARS[0x15] = "\x15"
_CHARS[0x16] = "\x16"
_CHARS.update({v: k for k, v in _CHARS.items()})

# Mapping special sequences in text to ASCII characters so that they
# be more easily encoded and edited
CONTROL_SEQUENCES = {

    # Unknown, shows up in Gau's return event
    b"\x05\xff": b"\x13",
    # Gau's name, but the second byte is an index, so we may have to watch out for more
    b"\x02\x0b": b"\x14",
    # Sabin's name, but the second byte is an index, so we may have to watch out for more
    b"\x02\x05": b"\x15",
    # Cyan's name, but the second byte is an index, so we may have to watch out for more
    b"\x02\x02": b"\x16",

    # one pause is controlled, one is not? (map to Enquiry in ASCII)
    #b"\x05": b"\x05",
    # Unknown, in unused event text, and in Cranes
    #b"\x00": b"\x12",

    # this is a terminator (map End of Transmission in ASCII)
    b"\x05\x00": b"\x04",
    # newline
    b"\x05\x01": b"\n",
    # this is a codebook compression thing, so nothing is semantically related
    # use an uncommon code
    b"\xc7": b"\x11"
}
_CTL_TO_SEQ = {v: k for k, v in CONTROL_SEQUENCES.items()}

class FF6Text(MemoryStructure):

    @classmethod
    def from_super(cls, mem_struct):
        return cls(mem_struct.addr, mem_struct.length,
                   mem_struct.name, mem_struct.descr)

    @classmethod
    def _decode(cls, word, replace_ctl_seq=True, strict=False):
        _word = bytes(word[:])
        if replace_ctl_seq:
            for key, replace in CONTROL_SEQUENCES.items():
                word = word.replace(key, replace)
        try:
            return "".join([_CHARS[i] for i in word])
        except KeyError as e:
            if strict:
                print(_word)
                print(cls._decode(_word, replace_ctl_seq, strict=False))
                raise e
        return "".join([_CHARS.get(i, "_") for i in word])

    @classmethod
    def _encode(cls, word, compress=True, replace_ctl_seq=False):
        # Right now, there's only one multi-char compression to account for
        if compress:
            word = word.replace("...", "\x11")

        word = bytes([_CHARS.get(char, ord(char)) for char in word])
        if replace_ctl_seq:
            for key, replace in _CTL_TO_SEQ.items():
                word = word.replace(key, replace)

        return word

    @classmethod
    def serialize(cls, json_repr):
        _data = json_repr.pop("_data", None)
        return cls._encode(_data)

    def patch(self, text, bindata=None):
        return super().patch(self._encode(text), bindata)

