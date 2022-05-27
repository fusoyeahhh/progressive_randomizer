from ....components import MemoryStructure

class FF6Text(MemoryStructure):
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

    @classmethod
    def from_super(cls, mem_struct):
        return cls(mem_struct.addr, mem_struct.length,
                   mem_struct.name, mem_struct.descr)

    @classmethod
    def _decode(cls, word):
        return "".join([cls._CHARS.get(i, "?") for i in word])

    #@classmethod
    #def _decode_stream(cls, words, sep=None):
    #return [cls._deocde(word) for word in words.split(sep)]

    @classmethod
    def _encode(cls, word):
        # FIXME
        try:
            return word.encode()
        except AttributeError:
            return word

    @classmethod
    def serialize(cls, json_repr):
        _data = json_repr.pop("_data", None)
        return cls._encode(_data)

    def patch(self, text, bindata=None):
        return super().patch(self._encode(text), bindata)

