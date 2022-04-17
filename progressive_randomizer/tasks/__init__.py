"""
Generic randomization tasks.
"""

class RandomizationTask:
    def __call__(self, bindata):
        return self._memblk << bindata

    def __rshift__(self, bindata):
        data = self(bindata)
        return self._memblk @ bytes(data) >> bindata

class ShuffleBytes(RandomizationTask):
    def __init__(self, memblk):
        self._memblk = memblk

    def __call__(self, bindata):
        import random
        data = super().__call__(bindata)
        return random.sample(list(data), k=len(data))

TASKS = {
    "shuffle_bytes": ShuffleBytes,
}
