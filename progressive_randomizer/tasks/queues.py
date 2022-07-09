import collections
import logging
log = logging.getLogger()

import pprint
import itertools


def is_soft_conflict(p1, p2):
    min_off = min(p1.affected_blocks()[0], p2.affected_blocks()[0])
    max_off = max(p1.affected_blocks()[1], p2.affected_blocks()[1])

    test_data = b"\xff" * max_off
    left_test_data = p2 >> (p1 >> test_data)
    test_data = b"\x00" * max_off
    right_test_data = p1 >> (p2 >> test_data)
    return left_test_data[min_off:max_off] == right_test_data[min_off:max_off]

class WriteQueue:
    def __init__(self, seed=0):
        self._write_queue = []
        self._history = {}

        # TODO: make this consistent
        self._seed = seed

    def __len__(self):
        return len(self._write_queue)

    def group_writes(self):
        write_grp = itertools.groupby(sorted(self._write_queue,
                                             key=lambda w: w._memblk.name),
                                      key=lambda w: w._memblk.name)
        return {lbl: list(grp) for lbl, grp in write_grp}

    def check_overlaps(self, queue=None):
        queue = queue or self._write_queue
        conflicts, n = {}, len(queue)

        # have to sort the queue first or else it goes to O(n^2)
        _q = sorted(queue, key=lambda t: t.affected_blocks()[0])

        conf_lookup = collections.defaultdict(list)
        # still could be ~ O(n * (n - 1))   :/
        for i in range(n - 1):
            for j in range(i + 1, n):
                a, b = _q[i], _q[j]
                if a & b and not is_soft_conflict(a, b):
                    conf_lookup[id(a)].append(id(b))
                    conflicts[a.affected_blocks(), b.affected_blocks()] = (a._memblk.name, b._memblk.name)
                else:
                    # if they don't intersect, then no others in the list will
                    # either
                    break

        log.info(f"Checked {n} writes: {len(conflicts)} conflicts found")
        return conf_lookup

    def merge_writes(self, queue=None):
        queue = queue or self._write_queue
        cur_p = queue.pop(0)
        for _ in range(len(queue)):
            p = queue.pop(0)
            try:
                cur_p += p
                continue
            except ValueError:
                queue.append(cur_p)
                cur_p = p

        queue.append(cur_p)
        return queue

    def flush(self, bindata, conf_resolver=None):
        """
        write_grps = self.consolidate_writes()
        for lbl, grp in write_grps.items():
            conflicts = self.check_overlaps(grp)
            #log.warning(f"{lbl}: {len(conflicts)} conflicts found")
        """
        self._write_queue = self.merge_writes()
        log.info(f"{len(self._write_queue)} writes total after merging")

        # detect collisions
        conflicts = self.check_overlaps()
        #log.warning(f"all: {len(conflicts)} conflicts found")
        #if len(conflicts) > 0:
            #log.info("Summary of conflicts:")
            #log.info("\n" + pprint.pformat(conflicts))

        pos_conf = []
        while len(self._write_queue) > 0:
            patcher = self._write_queue.pop(0)
            log.info(str(patcher))
            log.info(f"Applying {patcher}, current conflicts in queue {len(pos_conf)}")

            # does this patch conflict with anything else?
            # if so, take resolution step
            # FIXME: What to do if there are?
            # FIXME: use decompile / compile, e.g., JSON schematic
            if id(patcher) in pos_conf:
                log.info(f"{patcher} has been identified has conflicting with "
                         "an earlier write. Calling conflict resolver.")
                #conf_resolver()
                #self.checkpoint(bindata)

            # Apply patch
            # TODO: merge long patchsets in a chain splice (use PatchFromIPS?)
            bindata = patcher >> bindata
            # TODO: annotate history

            # Add our own conflicts
            if id(patcher) in conflicts:
                pos_conf.extend(conflicts[patcher])

        return bindata

    def queue_write(self, patcher):
        self._write_queue.append(patcher)

class QueueController(WriteQueue):
    def __init__(self):
        pass

    def user_input(self):
        pass