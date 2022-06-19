import logging
log = logging.getLogger()

import random

from .....utils.randomization import (
    triangle,
    accum_n,
    match_n
)

from ...components import FF6Text

from ... import FF6StaticRandomizer
from .....tasks import (
    ShuffleBytes,
    WriteBytes
)

from . import substitutions
from .substitutions import SubstitutionTask
from .substitutions import StateWatcher
from ... import data
from ...data import Command

from BeyondChaos.beyondchaos import utils as bc_utils
from BeyondChaos.beyondchaos import randomizer as bc_randomizer

GAME_NAME = b'FF6 BCCE'

def detect_bc(game_name):
    if game_name.startswith(GAME_NAME):
        return FF6StaticRandomizer
    return None

class BeyondChaosRandomizer(FF6StaticRandomizer):

    def __init__(self, seed, flags):
        super().__init__()
        self._seed = seed
        self._flags = flags

        # FIXME: seems offset by 1?
        slots_pointer = 0x24E4B
        self._reg.register_block(addr=slots_pointer, length=8, name="slt_ids",
                                 descr="Slot attack ids")

    """
    def christmas_mode(self, bindata):
        pass

    def halloween_mode(self, bindata):
        pass
        
    def random_boost(self, bindata):
        pass

    def scenario_not_taken(self):
        pass
    """

    def randomize(self):
        state = StateWatcher()
        args = {
            "seed": 0,
            "TEST_ON": None,
            "source": "ff6.smc",
            "destination": "bc_test/",
        }
        args = state._process_args(args)
        bc_randomizer.randomize(state, **args)
        return state._monitor._tasks

    #
    # From randomizer.py
    #
    # NOTE: these have requirements in Options_
    def auto_recruit_gau(self, **kwargs):
        # FIXME: use this
        stays_in_wor = kwargs.get("stays_in_wor", True)
        return [
            SubstitutionTask.sub_with_args(location=0xCFE1A,
                                           sub=bc_utils.AutoRecruitGauSub),
            SubstitutionTask.sub_with_args(location=0x24856,
                                           bytestring=bytes[0x89, 0xFF],
                                           sub=bc_utils.Substitution),
        ]

    def auto_learn_rage(self):
        return [
            SubstitutionTask.sub_with_args(location=0x23B73,
                                           sub=bc_utils.AutoLearnRageSub)
        ]

    def manage_commands(self, bindata, metronome=False, **kwargs):
        # Gather command data
        from ...managers import FF6CommandManager, FF6CharacterManager
        cmd_mgr = FF6CommandManager()
        cmd_mgr.populate(bindata)
        chr_mgr = FF6CharacterManager()
        chr_mgr.populate(bindata)

        invalid = [Command.Fight, Command.Item, Command.Magic, Command.X_Magic,
                   Command.Defend, Command.Row, Command.Summon, Command.Revert]
        # FIXME: handle this better
        invalid += [Command.UNUSED1, Command.UNUSED2]
        # ?
        if match_n(n=4):
            invalid.append(Command.Magitek)

        # ?
        if kwargs.get("replace_commands", False):
            invalid.extend([Command.Leap, Command.Possess])

        tasks = chr_mgr.randomize_commands(invalid, cmd_mgr)

        # Some optional stuff to process
        subs = substitutions.manage_commands_writes.copy()
        if metronome or "metronome" in self._flags:
            subs["fanatics_fix_sub"]["bytestring"] = bytes([0xA9, 0x1D])
        else:
            subs["fanatics_fix_sub"]["bytestring"] = bytes([0xA9, 0x15])

        # TODO: magitek reflect fix?
        # Job for skill manager

        return [SubstitutionTask.sub_with_args(name=name, **task)
                for name, task in subs.items()] + tasks

    def manage_rng(self, no_rng=False):
        """
        Shuffle the RNG table bytes to obtain new pseudo-random sequences in game.

        Affected by the 'norng' code (or argument)
        """
        tbl = self["rndm_nmbr_tbl"]
        if no_rng or "norng" in self._flags:
            return [WriteBytes(tbl, b"\x00" * tbl.length)]
        return [ShuffleBytes(tbl)]

    def death_abuse(self):
        """
        ???
        """
        return [SubstitutionTask.sub_with_args(location=0xC515, bytestring=b"\x60",
                                               sub=bc_utils.Substitution)]

    def randomize_slots(self, bindata, no_dupes=True):
        """
        Randomize the Slot command's attacks for each combination value.

        By default, duplications (other than where necessary) are disallowed. Set no_dupes to True to override.
        One can change the slots_pointer value if needed (not recommended).
        """
        # Get the current slot spell ids
        slots_ids = self["slt_ids"]
        _slots_ids = [*map(data.Spell, slots_ids << bindata)]
        log.info("Current slot spell data:")
        log.info(f"{[*map(data.Spell, _slots_ids)]}")

        # Get the non-magic spells to randomize over
        spell_data = self["spll_dt"] << bindata
        spells = sorted([s.idx for s in spell_data if not data.SkillSets.is_magic(s.idx)],
                         key=lambda s: data.Spell.rank(s))

        # TODO: Spell table needs something like get_by_index
        # filter to spells which target enemy (attacks)
        attack_spells = [s for s in spells
             if bool(spell_data[s].targeting & data.SpellTargeting.ENEMY_DEFAULT)]

        l, l_8, l_20 = len(spells), len(attack_spells) // 8, len(spells) // 20
        new_ids = [None] * 8
        # keep the same (magicite?)
        new_ids[3] = _slots_ids[3]
        # FIXME: somewhat inefficient since it redoes the entire loop if it
        # detects duplicates
        while len(set(new_ids)) < 7:
            # Determine new Joker Doom
            new_ids[0] = triangle(0, l_8, l_8 * 6) + random.randint(0, l) - (8 * l_8 - 1)
            new_ids[1] = new_ids[0]
            # Replacement for bahamut / sun flare
            new_ids[2] = random.randint(len(spells) // 3, len(spells) - 1)
            # Replacement for airships / chocobos / gems
            new_ids[4:7] = [triangle(0, len(spells) // 2) for _ in range(3)]

            # replacement for lagomorph
            new_fail = accum_n(2, l_20, init=random.randint(0, l_20))
            new_ids[7] = min(new_fail, len(spells) - 1)

            # we only iterate if dupes are not allowed
            if not no_dupes:
                break

        # Map to spells -- 4th spell is still unchanged
        new_ids = [attack_spells[0]] * 2 + [spells[new_ids[2]], new_ids[3]] \
                    + [spells[sid] for sid in new_ids[4:]]
        log.info("Chose the following new spells for slots:")
        log.info(f"{[*map(data.Spell, new_ids)]}")

        return [WriteBytes(slots_ids, new_ids)]

    # Won't work because of all the workarounds needed
    def _manage_commands(self):
        commands = {c.name: c
                    for c in bc_randomizer.commands_from_table(bc_utils.COMMAND_TABLE)}
        write_logger = bc_randomizer.fout = substitutions.LoggedByteWriter()
        bc_randomizer.manage_commands(commands=commands)
        return write_logger._tasks
