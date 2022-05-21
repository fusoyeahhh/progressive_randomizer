class IPSReader:
    def __init__(self, fname):
        self.fname = fname
        self.trunc_length = 0
        self.contents = {}

        self._decode()

    def _decode(self):
        with open(self.fname, "rb") as patch_file:
            _contents = patch_file.read()

        # As an extension, the end-of-file marker may be followed
        # by a three-byte length to which the resulting file should be truncated.
        # Not every patching program will implement this extension, however.
        try:
            idx = _contents.rindex(b"EOF") + 3
            assert len(_contents) - idx <= 3

            self.trunc_length = int.from_bytes(_contents[idx:], 'big')
            _contents = _contents[:idx]
        except ValueError:
            raise ValueError("end bytes invalid")

        # An IPS file starts with the magic number "PATCH" (50 41 54 43 48),
        # followed by a series of hunks and an end-of-file marker "EOF" (45 4f 46).
        # All numerical values are unsigned and stored big-endian.
        try:
            header = _contents[:5]
            eof = _contents[-3:]
            assert header.decode() == "PATCH"
            assert eof.decode() == "EOF"
        except UnicodeDecodeError:
            raise ValueError("header / end bytes invalid")

        _contents = _contents[5:-3]

        # Regular hunks consist of a three-byte offset
        # followed by a two-byte length of the payload and the payload itself.
        # Applying the hunk is done by writing the payload at the specified offset.
        while len(_contents) > 0:
            offset, length = int.from_bytes(_contents[:3], "big"), \
                             int.from_bytes(_contents[3:5], "big")
            _contents = _contents[5:]

            # RLE hunks have their length field set to zero;
            # in place of a payload there is a two-byte length of the run
            # followed by a single byte indicating the value to be written.
            # Applying the RLE hunk is done by writing this byte
            # the specified number of times at the specified offset.
            if length == 0:
                #print("RLE")
                payload, _contents = _contents[:3], _contents[3:]
                length = int.from_bytes(payload[:2], "big")
                payload = payload[2:3] * length
            else:
                #print("standard")
                payload, _contents = _contents[:length], _contents[length:]
            #print(hex(offset), hex(offset + length), length)

            # length is implied in the bytestring object, not needed to preserve
            self.contents[offset] = payload

    def __iter__(self):
        for offset, payload in self.contents.items():
            yield offset, payload

    def apply(self, inbytes):
        for offset, payload in self.contents.items():
            inbytes = inbytes[:offset] + bytes(payload) + inbytes[offset+len(payload):]

        if self.trunc_length > 0:
            inbytes = inbytes[self.trunc_length:]

        return inbytes

    def pretty_print(self, width=24, fmt_str=None):
        for offset, payload in self.contents.items():
            payload = payload[:]

            if fmt_str is None:
                print(f"{hex(offset)}:")

            pstr = ""
            while len(payload) > 0:
                if fmt_str is None:
                    print(", ".join(map(hex, payload[:width])))
                #pstr += ", ".join(map(hex, payload[:width]))
                payload = payload[width:]
            if fmt_str:
                fmt_str.format(addr=hex(offset), contents=pstr)
                print(fmt_str)

if __name__ == "__main__":
    import sys
    for fname in sys.argv[1:]:
        print(fname)
        patch = IPSReader(fname)
        patch.pretty_print()