import collections
import logging
log = logging.getLogger()

import hashlib
import itertools

from . import ExpandImage

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

    def describe_changes(self, bindata, queue=None):
        queue = queue or self._write_queue
        from ..game.ff6.randomizers import FF6StaticRandomizer
        _tmp = FF6StaticRandomizer()
        for i, write in enumerate(queue):
            affected_blocks = _tmp._reg.find_blks_from_addr(write._memblk.addr)
            print(f"--- Write #{i} ---\n"
                  f"affected blocks: {affected_blocks}\n"
                  f"memblk: {write._memblk}")
            print(write.diff(bindata))
            print()

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

from ..components import Registry
class Compiler(WriteQueue, Registry):
    @classmethod
    def from_registry(cls, reg):
        new = cls()
        for blk in reg._blocks:
            # TODO: add tag based on metadata?
            new.register_block(blk._memblk.addr, blk._memblk.length,
                               blk._memblk.name, blk._memblk.descr)

        return reg

    def expand_image(self, size):
        end = sorted([b.addr + b.length for b in self._blocks])
        name = f"expanded_space_{end}_{end + size}"
        blk = self.register_block(addr=end, length=size, name=name,
                                  descr="ROM size expansion")
        return ExpandImage(blk, size)

    def compile(self, bindata):
        assert self.check_contiguous()
        image = b""
        for blk in sorted(self._blocks):
            image += blk << bindata

        return image

    def patch_stage(self, bindata, editable=None):
        uneditable = set(self._blocks)
        # None means all blocks are editable
        uneditable -= editable or set(self._blocks)

        for write in self._write_queue:
            blk = write._memblk
            # FIXME: assumes writes are confined to a single block
            affected_blks = {b.name
                             for b in self.find_blks_from_addr(blk.addr)
                             if b.name not in uneditable}

            for blk in affected_blks:
                log.info(f"Writing {write} to {blk.name}")
                bindata = write >> bindata
                #self.register_block(**vars(blk))
                uneditable.add(blk.name)

            # No blocks will accept this patch at this time
            if len(affected_blks) == 0:
                log.info(f"Unable to make further writes, checkpointing and "
                         f"resetting editable regions.")
                import pathlib
                self.checkpoint(bindata, pathlib.Path("./"))
                # TODO: reconstitute base image from current writes?
                # base conflict resolution
                uneditable = set()

    def checkpoint(self, bindata, tmppth):
        hsh = hashlib.new("md5")
        hsh.update(bindata)
        hsh = hsh.hexdigest()
        log.info(f"Checkpointing current image to {tmppth}."
                 f"Current md5 hash: {hsh}")

        with open(tmppth / hsh, "wb") as fout:
            fout.write(bindata)

        return hsh

class QueueController(WriteQueue):
    def __init__(self):
        pass

    def user_input(self):
        pass