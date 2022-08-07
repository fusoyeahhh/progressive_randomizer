import math
import random
from dataclasses import dataclass
import logging
log = logging.getLogger()

from ....utils import set_bit

from ....components import (
    MemoryStructure,
    AssemblyObject,
)
from ....utils.randomization import random_prob, choice_without_replacement
from ....tasks import WriteBytes


from ..components import (
    FF6PointerTable,
    FF6Text,
)
from ..randomizers import  FF6StaticRandomizer

from ..data import (
    Command,
    SpellTargeting,
    Spell
)

class CommandFactory:
    pass

class FF6CommandManager(FF6StaticRandomizer):
    # TODO: merge this back down into CommandItem in super
    @dataclass
    class NewCommand:
        idx: Command
        name: str
        mimic_allowed: bool = False
        imp_allowed: bool = False
        targeting: SpellTargeting = SpellTargeting.ST_TARG
        retarget_allowed: bool = False
        berserk_allowed: bool = False
        confused_allowed: bool = False
        code: bytes = b""

        @classmethod
        def from_id(cls, id, mgr, bindata, **kwargs):
            cmd_data = mgr["bttl_cmmnd_dt"].read(bindata)[id]
            cmd_name = FF6Text._decode(mgr["bttl_cmmnd_nms"] << bindata, 7)[id]
            return cls(
                id, cmd_name,
                cmd_data.can_mimic, cmd_data.can_imp,
                cmd_data.targeting,
                **kwargs
            )

        def __bytes__(self):
            return bytes([
                (int(self.mimic_allowed) << 1) + (int(self.imp_allowed) << 2),
                self.targeting
            ])

        def annotate(self):
            return AssemblyObject.annotate(self.code)

        def code_block(self, dst):
            return AssemblyObject(dst, len(self.code),
                                  name=f"command_code_{self.name}",
                                  descr=f"Assembly code for command {self.name}")

        # see SpellSub in BC, similar to the Health command at 0x2171E - 0x21725
        _SKILL_TMPLT = [
            0xA9, None,
            0x85, 0xB6,
            0xA9, 0x02,
            0x85, 0xB5,
            0x4C, 0x5F, 0x17
        ]

        @classmethod
        def build_skill(self, skill):
            code = self._SKILL_TMPLT[:]
            code[1] = skill
            return bytes(code)

        def use_skill(self, ptr, skill):
            self.code += self.build_skill(skill)

        _MULTI_SKILL_TMPLT = [
            0x5A,
            0x20, None, None,
            0x7A
        ]
        _MULTI_SKILL_TMPLT_2 = [
            0xA9, 0x01,
            0x04, 0xB2,
        ]

        def build_multi(self, ptr, skills):
            skill_code = self.build_skill(skills.pop(0))
            header_code = self._MULTI_SKILL_TMPLT[:]

            skill_code_len = len(skill_code)
            for skill in skills:
                skill_code += self.build_skill(skill)
                header_code += self._MULTI_SKILL_TMPLT_2[:]
                header_code += self._MULTI_SKILL_TMPLT[:]

            off = len(header_code)
            # Replace skill code pointers
            idx = 0
            for i in range(len(skills) + 1):
                idx = header_code.index(None, idx + 1)
                header_code[idx:2+idx] = (ptr + off).to_bytes(2, byteorder="little")
                off += skill_code_len

            return bytes(header_code) + bytes(skill_code)

        def use_dual_skill(self, ptr, skill1, skill2):
            self.code = self.build_multi(ptr, [skill1, skill2])
            # TODO: set name and attributes

        _RANDOM_SKILL_TMPLT = [
            0x20, 0x5A, 0x4B,                      # get random number
            0x29, 0x00,                            # AND the result
            0xAA,                                  # TAX
            0xBF, 0x00, 0x00, 0x00,                # load byte from $addr + X
            0x85, 0xB6, 0xA9, 0x02, 0x85, 0xB5,
            0x64, 0xB8, 0x64, 0xB9,                # clear targets
            0x20, 0xC1, 0x19,                      # JSR $19C1
            0x20, 0x51, 0x29,                      # JSR $2951
            0x4C, 0x5F, 0x17,
        ]

        @classmethod
        def build_rskill(cls, ptr, skills):
            code = cls._RANDOM_SKILL_TMPLT[:]
            code[4] = len(skills) - 1
            code[7:10] = (0xC00000 + ptr + len(code)).to_bytes(length=3, byteorder="little")
            return bytes(code) + bytes(sorted(skills))

        def use_rskill(self, ptr, rskill):
            self.code = self.build_rskill(ptr, rskill)

        def use_wskill(self, ptr, wskill):
            self.code = self.build_multi(ptr, [wskill, wskill])

        # see ChainSpellSub in BC
        _CHAIN_SKILL_TMPLT = [
            0xA9, 0x01,
            0x04, 0xB2,
            0x5A,              # PHY
            0x20, None, None,  # call spell sub
            0x7A,              # PLY
            0x20, 0x5A, 0x4B,  # get random number
            0x29, 0x01,        # AND the result
            0xC9, 0x00,        # CMP #0
            0xD0, None,        # BNE start of bytestring
            0x60
        ]

        @classmethod
        def build_chain_skill(cls, ptr, skill):
            code = cls._CHAIN_SKILL_TMPLT[:]
            code[-2] = 0x100 - len(code) - 1
            skill_call_ptr = ptr + len(code)
            code[6:8] = skill_call_ptr.to_bytes(2, byteorder="little")
            return bytes(code) + cls.build_skill(skill)

        def use_chain_skill(self, ptr, skill):
            self.code = self.build_chain_skill(ptr, skill)

    _LEN_VALID_COMMANDS = 30
    _BE_FIELD_LEN = math.ceil(_LEN_VALID_COMMANDS / 8)
    # https://datacrystal.romhacking.net/wiki/Final_Fantasy_VI:ROM_map/Assembly_C24#C2.2F4E46_data:_commands_that_need_to_retarget
    _BATTLE_ENGINE_TARGETING = MemoryStructure(addr=0x24E46, length=_BE_FIELD_LEN,
                                               name="battle_engine_retargeting",
                                               descr="Retargeting allowance bits "
                                                     "in the battle engine")

    _BATTLE_ENGINE_CONFUSED = MemoryStructure(addr=0x204D0, length=_BE_FIELD_LEN,
                                              name="battle_engine_confused",
                                              descr="Allowance bits for "
                                                    "confused characters "
                                                    "in the battle engine")

    _BATTLE_ENGINE_BERSERK = MemoryStructure(addr=0x204D4, length=_BE_FIELD_LEN,
                                             name="battle_engine_berserk",
                                             descr="Allowance bits for "
                                                   "berserked characters "
                                                   "in the battle engine")

    _BATTLE_ENGINE_SUMMON = MemoryStructure(addr=0x25049, length=1,
                                            name="battle_engine_summon",
                                            descr="Targeting for Summon command "
                                                  "in the battle engine")

    _BATTLE_ENGINE_CMD_PTRS = FF6PointerTable(addr=0x219C7, length=60,
                                              name="battle_engine_cmd_ptrs",
                                              descr="Pointers to command implementations "
                                                    "in the battle engine")

    # https://datacrystal.romhacking.net/wiki/Final_Fantasy_VI:ROM_map/Assembly_C34#C3.2F4D78_data:_commands_related_to_skills_menu
    _BATTLE_ENGINE_CMD_MENU_PTRS = MemoryStructure(addr=0x34D78, length=7,
                                                   name="battle_engine_cmd_menu_ptrs",
                                                   descr="Pointers to command menus "
                                                         "in the battle engine")

    # https://datacrystal.romhacking.net/wiki/Final_Fantasy_VI:ROM_map/Assembly_C17#C1.2F7CE9_commands_.28table.29^
    _BATTLE_ENGINE_CMD_GRP_TBL = FF6PointerTable(addr=0x17CE9, length=60,
                                                 name="battle_engine_cmd_menu_ptrs",
                                                 descr="Pointers to command menus "
                                                       "in the battle engine")

    _BATTLE_ENGINE_GOGO_USE = AssemblyObject(addr=0x35e57, length=3,
                                             name="battle_engine_gogo_usable",
                                             descr="assembly for command being "
                                                   "usable by Gogo")

    def __init__(self):
        super().__init__()
        # FIXME: We may need a parent rando to reconfigure this one in the future
        #self._rando = rando
        self.cmd_data = {}

        self._be_targeting = None
        self._be_confused = None
        self._be_berserk = None

    def _fix_summon_command(self):
        # http://www.rpglegion.com/ff6/hack/summon.htm
        # but see also https://www.ff6hacking.com/forums/thread-821.html
        return self._BATTLE_ENGINE_SUMMON @ b"\x02"

    def edit_battle_engine_flags(self, cid, targeting=None, confused=None,
                                 berserk=None):
        offset = cid // 8
        bit = cid % 8
        if targeting is not None:
            set_bit(self._be_targeting, targeting, offset, bit)
        if confused is not None:
            set_bit(self._be_confused, confused, offset, bit)
        if berserk is not None:
            set_bit(self._be_berserk, berserk, offset, bit)

    def populate(self, bindata):
        # Gather command data
        cmd_names = FF6Text._decode(self["bttl_cmmnd_nms"] << bindata, 7)
        cmd_data = self["bttl_cmmnd_dt"].read(bindata)

        self._be_targeting = bytearray(self._BATTLE_ENGINE_TARGETING << bindata)
        self._be_confused = bytearray(self._BATTLE_ENGINE_CONFUSED << bindata)
        self._be_berserk = bytearray(self._BATTLE_ENGINE_BERSERK << bindata)

        _be_flags = {
            "retarget_allowed": self._be_targeting,
            "confused_allowed": self._be_confused,
            "berserk_allowed": self._be_berserk
        }
        cmd_ptrs = dict(zip(map(hex, self._BATTLE_ENGINE_CMD_PTRS.read(bindata)), Command))
        import pprint
        pprint.pprint(cmd_ptrs)
        import pdb; pdb.set_trace()

        cmds = {}
        for i, (name, cdata) in enumerate(zip(cmd_names, cmd_data)):
            #print(i, name, cdata)
            mask = 1 << (i % 8)
            _flags = {k: bool(v[i // 8] & mask) for k, v in _be_flags.items()}
            cmds[i] = self.NewCommand.from_id(i, self, bindata, **_flags)

        return cmds

    def edit_command(self, cmd):
        pass

    def plando(self, chars, cmd_data):
        for c, commands in cmd_data.items():
            chars[c].commands = commands

        return chars

    # From BC, based in part on manage_commands_new
    def randomize_commands(self, bindata, no_combos=True, replace_everything=False,
                           desperations=False, plays_itself=False):

        cmds, cmd_installs = self.populate(bindata), []

        to_rando = list(cmds.keys())
        for cmd_idx in to_rando:
            old_cmd = cmds.pop(cmd_idx)
            # randomize
            import copy
            new_cmd = copy.deepcopy(old_cmd)

            skill_choices = [*Spell]
            choice = random.choice([
                (new_cmd.use_skill, [0, random.choice(skill_choices)]),
                (new_cmd.use_dual_skill, [0] + choice_without_replacement(skill_choices, k=2)),
                (new_cmd.use_chain_skill, [0, random.choice(skill_choices)]),
                # FIXME: generate rskill categories
                #(new_cmd.use_rskill, None),
                (new_cmd.use_wskill, [0, random.choice(skill_choices)]),
                None
            ])

            if choice is not None:
                # FIXME: is there a better way to do this? Do we have to call this twice?
                print(choice)
                rand_skill, args = choice
                rand_skill(*args)

                new_code_blk = self.request_space(len(new_cmd.code),
                                                  start=0x0, end=0xFFFF,
                                                  name=f"new_command_write_{new_cmd.name.lower().strip()}")

                args[0] = new_code_blk.addr
                rand_skill(*args)

                # install command code
                cmd_installs.append(WriteBytes(new_cmd.code_block(new_code_blk.addr),
                                               new_cmd.code))

                # https://datacrystal.romhacking.net/wiki/Final_Fantasy_VI:ROM_map/Assembly_C21#C2.2F19C7_pointers:_commands
                # encoded command pointer for battle engine
                dst = self._BATTLE_ENGINE_CMD_PTRS.addr + 2 * new_cmd.idx
                write_ptr, ptr = new_code_blk.get_pointer_write(dst, ptr_len=2)
                # rewrite pointer in battle engine
                cmd_installs.append(WriteBytes(write_ptr, ptr))

                dst = self._BATTLE_ENGINE_CMD_GRP_TBL.addr + 2 * new_cmd.idx
                write_ptr, ptr = new_code_blk.get_pointer_write(dst, ptr_len=2)
                # rewrite pointer in menu engine
                cmd_installs.append(WriteBytes(write_ptr, ptr))

                dst = self._BATTLE_ENGINE_CMD_GRP_TBL.addr + 2 * new_cmd.idx
                write_ptr, ptr = new_code_blk.get_pointer_write(dst, ptr_len=2)
                # rewrite pointer in graphics engine
                cmd_installs.append(WriteBytes(write_ptr, ptr))

                # another menu write -- usable by Gogo --- this may only be done once

                # BC also seems to change some enemy scripts for some reason?

            # update battle engine flags
            self.edit_battle_engine_flags(new_cmd.idx, new_cmd.retarget_allowed,
                                          new_cmd.confused_allowed, new_cmd.berserk_allowed)

            cmds[cmd_idx] = new_cmd
            log.info(f"Original: {old_cmd}\n-> {new_cmd}")

        return self.write(cmds, cmd_installs)

    def write(self, cmds, installs):
        # Sort by the command index for the correct write order
        cmds = {idx: cmd
                for idx, cmd in sorted(cmds.items(), key=lambda t: t[-1].idx)}

        be_to_write = zip(
            (self._BATTLE_ENGINE_TARGETING, self._BATTLE_ENGINE_CONFUSED, self._BATTLE_ENGINE_BERSERK),
            (self._be_targeting, self._be_confused, self._be_berserk)
        )
        battle_engine_edits = [WriteBytes(blk, data) for blk, data in be_to_write]

        cmds_names = [FF6Text._encode(cmd.name) for cmd in cmds.values()]
        cmds_data = map(bytes, cmds.values())

        return [
            WriteBytes(self["bttl_cmmnd_dt"], b''.join(cmds_data)),
            # FIXME: name length is probably wrong
            WriteBytes(self["bttl_cmmnd_nms"], b''.join(cmds_names)),
            *installs,
            *battle_engine_edits
        ]

    # BC style
    def _get_random_commands(self, cmd_pool, only_unique=True,
                             item_prob=0.5, magic_prob=0.5,
                             xmagic_prob=0.5, n=3):
        commands = []
        # determine if x-magic is part of the menu
        if random_prob(xmagic_prob):
            commands.append(Command.X_Magic)
        elif random_prob(magic_prob):
            commands.append(Command.Magic)
        # determine if item is part of the menu
        if random_prob(item_prob):
            commands.append(Command.Item)

        n -= len(commands)
        if n <= 0:
            return commands

        # TODO: handle giving "nothing" instead
        allow_pad = True
        if len(cmd_pool) < n and not allow_pad:
            log.warning("Attempting draw a commands from pool without enough "
                        "left.\nThis will probably fail.")
        new_cmds = choice_without_replacement(list(cmd_pool), k=n)

        if only_unique:
            cmd_pool -= set(new_cmds)
        commands += new_cmds
        if allow_pad and len(commands) < n:
            commands += [Command.Nothing] * (n - len(commands))
        return commands

if __name__ == "__main__":
    mngr = FF6CommandManager()
    # Print out some stuff from args