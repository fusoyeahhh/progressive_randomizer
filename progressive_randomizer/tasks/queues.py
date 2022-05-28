import logging
log = logging.getLogger()

class WriteQueue:
    def __init__(self, seed=0):
        self._write_queue = []
        self._history = {}

        # TODO: make this consistent
        self._seed = seed

    def __len__(self):
        return len(self._write_queue)

    def check_overlaps(self):
        conflicts, n = {}, len(self._write_queue)

        # have to sort the queue first or else it goes to O(n^2)
        _q = sorted(self._write_queue, key=lambda t: t.affected_blocks()[0])

        # still could be ~ O(n * (n - 1))   :/
        for i in range(n - 1):
            for j in range(i + 1, n):
                a, b = _q[i], _q[j]
                if a & b:
                    conflicts[a.affected_blocks()] = b.affected_blocks()
                else:
                    # if they don't intersect, then no others in the list will
                    # either
                    break

        log.info(f"Checked {n} writes: {len(conflicts)} conflicts found")
        return conflicts

    def flush(self, bindata):
        # detect collisions
        conflicts = self.check_overlaps()
        log.warning(f"Summary of conflicts:\n{conflicts}")

        # FIXME: What to do if there are?
        # FIXME: use decompile / compile, e.g., JSON schematic

        while len(self._write_queue) > 0:
            patcher = self._write_queue.pop(0)
            log.info(str(patcher))
            # TODO: need a way to chain splice
            # NOTE: if there are no conflicts, you can do the following:
            # 1. sort the list, get the split points,
            # 2. iterate on each split point (end of interval)
            # 2a. read and write to subsection of data (to split point)
            # 2b. concatenate next up to split point
            # 2c. repeat until done
            # However, concats will get bigger and bigger
            # So... need something like an IPS patcher
            bindata = patcher >> bindata
            # TODO: annotate history
        return bindata

    def queue_write(self, patcher):
        self._write_queue.append(patcher)

class QueueController(WriteQueue):
    def __init__(self):
        pass

    def user_input(self):
        pass