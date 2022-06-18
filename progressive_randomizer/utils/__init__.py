import logging
log = logging.getLogger()

    from .autodetect import autodetect_and_load_game

    if game_name not in KNOWN_GAMES:
        log.warning("Game does not have a registered randomizer, "
                    "using default --- some functions may not be available.")
    rando = KNOWN_GAMES.get(game_name, StaticRandomizer)()
    log.info(f"Read header, game name: {game_name} -> {rando}")

    with open(filename, "rb") as fin:
        romdata = fin.read()

    return romdata, rando

class Utils:
    @classmethod
    def compare(cls, file1, file2, file3=None, suppress_same=False):
        # FIXME: have to refactor this to avoid the circular dependency
        from .autodetect import autodetect_and_load_game

        g1, lhs = autodetect_and_load_game(file1)
        g2, rhs = autodetect_and_load_game(file2)
        if file3 is not None:
            g3, _ = autodetect_and_load_game(file3)

        total_diff = 0

        # TODO: compare differences in block structure
        unknown_blks_1 = lhs._register_non_documented_areas()
        unknown_blks_2 = rhs._register_non_documented_areas()

        all_blks = {
            **lhs._reg._blocks,
            **unknown_blks_1._blocks,
            **unknown_blks_2._blocks
        }

        for name, blk in all_blks.items():
            data1 = blk << g1
            data2 = blk << g2
            if file3 is not None:
                data3 = blk << g3
            diff = sum([b1 != b2 for b1, b2 in zip(data1, data2)])
            total_diff += diff
            if not suppress_same and data1 == data2:
                print(f"[{blk.addr:8x}+{blk.length:6x}] {name}: {blk.descr}"
                      f"\n\tmatches")
                continue
            elif data1 != data2:
                print(f"[{blk.addr:8x}+{blk.length:6x}] {name}: {blk.descr}"
                      f"\n\tdoes not match {diff} / {len(data1)} bytes differ")

            k = 0
            addr = blk.addr
            # while len(data1) > 0:
            while k <= 3:
                _d1, data1 = data1[:16], data1[16:]
                _d2, data2 = data2[:16], data2[16:]
                if file3 is not None:
                    _d3, data3 = data3[:16], data3[16:]
                if len(_d1) == 0:
                    break
                if _d1 == _d2:
                    addr += 16
                    continue
                k += 1

                diff = [i for i, (b1, b2) in enumerate(zip(_d1, _d2))
                        if b1 != b2]
                diff = " " * 25 + " ".join(["^^" if i in diff else "  " for i in range(len(_d1))])
                _d1 = file1.ljust(15)[:15] + f" {addr:08x} " \
                      + " ".join([f"{b:02x}" for b in _d1])
                _d2 = file2.ljust(15)[:15] + f" {addr:08x} " \
                      + " ".join([f"{b:02x}" for b in _d2])
                if file3 is not None:
                    _d3 = file3.ljust(15)[:15] + f" {addr:08x} " \
                          + " ".join([f"{b:02x}" for b in _d3])
                    print(_d3)
                print(_d1)
                print(_d2)
                print(diff)
                print()

                addr += 16

        p = total_diff / len(g1) * 100
        print(f"Total difference: {total_diff} / {len(g1)} bytes ({p:.3f}%) differ")

    @classmethod
    def merge(cls, file1, file2):
        # TODO: probably should check if they're from the same base game
        # for now... 'eh.
        g1, src = autodetect_and_load_game(file1)
        g2, dst = autodetect_and_load_game(file2)

        dst_blks = dst.decompile(g2)

        merged, ptr_map = {}, {}
        # So, this is basically going to be splicing WC -> BC
        # essentially, the assets from BC will be used with the
        # gameplay from WC
        # TODO: reconcile overlapping sections
        for name, data in src.decompile(g1).items():
            # formally, we should check that there are no "conflicting"
            # sections which exist in one ROM but not the other ---
            # we'll assume there isn't. BC has expanded the ROM
            # but WC neither knows nor cares about this
            assert name in dst._blocks
            # No difference, use this data block without modification
            if data == dst_blks[name]:
                log.info(f"No change for {name}, merging automatically")
                continue

            # Make an IPS-style patch and integrate them into a WriteQueue

            # The things we'll have to watch out for:
            # JMP / RTS and related pointers that changed
            # - this means marked assembly code should be inspected for changes
            # if is assembly: try to find pointers in dst
            # - specifically, there are probably jumps into the expanded ROM
            #   that will be need to be spliced in the incoming WC assembly
            # pointers into data tables should be modified appropriately
            # Incompatible data table changes
            # - items / NPC / event trigger data all needs to be checked for
            #   compatibility

        # WC makes much more use of free space than BC, consequently
        # some conflicts will need to be resolved in free space usage

