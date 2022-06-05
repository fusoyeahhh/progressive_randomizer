import random
import logging
log = logging.getLogger()

from ....components import MemoryStructure
from ....utils.randomization import random_prob, choice_without_replacement
from ....tasks import WriteBytes

from ..components import FF6Text
from ..randomizers import FF6StaticRandomizer
from ..data import Character, Command

class FF6CommandManager(FF6StaticRandomizer):
    def __init__(self):
        super().__init__()
        # FIXME: We may need a parent rando to reconfigure this one in the future
        #self._rando = rando
        self.cmd_data = {}

    def populate(self, bindata):
        # Gather command data
        cmd_names = FF6Text._decode(self["bttl_cmmnd_nms"] << bindata, 7)
        cmd_data = self["bttl_cmmnd_dt"] << bindata
        self.cmd_data = dict(zip(cmd_names, cmd_data))

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

    def plando(self, chars, cmd_data):
        for c, commands in cmd_data.items():
            chars[c].commands = commands

        return chars

class FF6CharacterManager(FF6StaticRandomizer):
    _MORPH_MEMBLK = MemoryStructure(addr=0x25E32, length=2, name="morph_data",
                                    descr="Character specific morph byte data")

    @classmethod
    def validate(cls, chr_data):
        if len(chr_data) != 16:
            log.warning("Attempting to modify more or less than all 16 characters.")

        # FIXME: does this always have to be fight?
        if not all([c.commands[0] is Command.Fight for c in chr_data.values()
                    if c.idx < Character.Gau]):
            log.error("All characters must have Fight as the first command.")
            raise RuntimeError()

        # evidently gogo has to have mimic?
        gogo = [c for c in chr_data.values() if c.idx == Character.Gogo][0]
        if gogo.commands[0] is not Command.Mimic:
            log.error("Gogo must have Mimic as the first command.")
            raise RuntimeError()

    @classmethod
    def package(cls, chr_data):
        # TODO: names
        cls.validate(chr_data)
        raw_data = b""
        for cdata in sorted(chr_data.values(), key=lambda c: c.idx):
            raw_data += bytes(cdata)

        return raw_data

    def __init__(self):
        super().__init__()
        # FIXME: We may need a parent rando to reconfigure this one in the future
        #self._rando = rando
        self.chr_data = {}

    def populate(self, bindata):
        # Gather command data
        self.chr_names = FF6Text._decode(self["chrct_nms"] << bindata, 6)
        #chr_ids = [Character(i) for i in range(len(self.chr_names))]
        # FIXME:
        chr_ids = [Character(i) for i in range(16)]
        chr_data = self["chrct_intl_prprt"] << bindata
        self.chr_data = dict(zip(chr_ids, chr_data))

    def randomize_commands(self, invalid, cmd_mgr, shuffle_cmds=False, replace_cmds=False,
                           unique_xmagic=True, force_only_cmd=None, force_skill_cmd=None,
                           **kwargs):
        # populate pool
        cmd_pool = {Command(c.idx) for n, c in cmd_mgr.cmd_data.items() if c.idx not in invalid}
        xmagic_used = False

        for char in self.chr_data.values():
            # "fix" Gau
            if shuffle_cmds or replace_cmds and char.idx is Character.Gau:
                char.commands[0] = Command.Fight

            # example: this is used in "metronome" in BC to set skill to Magitek
            if force_skill_cmd is not None:
                char.commands = [Command.Fight, Command(force_skill_cmd),
                                 Command.Magic, Command.Item]
                continue

            # Force the menu to have only one command (I think?)
            # TODO: why does BC only fill the last three slots?
            if force_only_cmd is not None:
                char.commands = [char.command[0], Command.Nothing,
                                 Command.Nothing, Command(force_only_cmd)]
                continue

            # Handle "special characters differently
            if char.idx > Character.Gau:
                char.commands = [char.commands[0], Command.Nothing,
                                 Command.Nothing, char.commands[-1]]
                continue

            # zero out X-magic probability if we have and we're unique
            xmagic_prob = kwargs.pop("xmagic_prob", 0.5) \
                            if not (xmagic_used and unique_xmagic) else 0
            char.commands[1:] = cmd_mgr._get_random_commands(cmd_pool,
                                                         xmagic_prob=xmagic_prob,
                                                         **kwargs)
            xmagic_used |= Command.X_Magic

            log.info(f"New commands for {str(Character(char.idx))}: {char.commands}")

        tasks = [WriteBytes(self["chrct_intl_prprt"], self.package(self.chr_data))]
        return tasks + self._handle_morph_changes()

    def _handle_morph_changes(self):
        for c in self.chr_data.values():
            if Command.Morph in c.commands:
                return [WriteBytes(self._MORPH_MEMBLK, bytes([0xC9, c.idx]))]
        return []