"""
Generic randomization tasks.
"""
import random

class RandomizationTask:
    def __init__(self, memblk):
        self._memblk = memblk

    def __call__(self, bindata):
        # FIXME: we have to ensure this binary data, because our read method returns
        # different things
        # TODO: we need to have a base "raw" read and then deserialization / dereferencing
        try:
            return bytes(self._memblk << bindata, encoding='utf8')
        except TypeError:
            pass
        return self._memblk << bindata

    def __rshift__(self, bindata):
        data = self(bindata)
        return self._memblk @ bytes(data) >> bindata

    # Determines whether two randomizations could collide
    def __and__(self, rhs):
        import portion
        lhs = portion.closedopen(*self.affected_blocks())
        rhs = portion.closedopen(*rhs.affected_blocks())
        return lhs.intersection(rhs) != portion.empty()

    def affected_blocks(self):
        return (self._memblk.addr, self._memblk.addr + self._memblk.length)

class ShuffleBytes(RandomizationTask):
    def __call__(self, bindata):
        data = super().__call__(bindata)
        return bytes(random.sample(list(data), k=len(data)))

TASKS = {
    "shuffle_bytes": ShuffleBytes,
}
