import os
import json
import datetime

from twitchio.ext import commands, routines

import logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

__version__ = "0.2.0-beta"

from .observer import BCFObserver, InfoProvider
from .utils import _chunk_string, construct_default_doc_url

class AuthorizedCommand(commands.Command):
    _AUTHORIZED = set()

    async def invoke(self, ctx, *, index=0):
        user = ctx.author.name
        if self._authenticate(user):
            return await super().invoke(ctx, index=index)

        await ctx.send(f"I'm sorry, @{user}, I can't do that...")
        return

    def _authenticate(self, user):
        """
        Checks if ctx.user is in the administrator list.

        :param user: Twitch chat user name
        :return: (bool) whether or not user is authorized to use admin commands
        """
        auth = user in self._AUTHORIZED
        logging.debug(f"Checking auth status for {user}: {auth}")
        return auth

class BCF(commands.Bot):
    COMMANDS = {}

    def __init__(self, config, romfile_path=None,
                 chat_readback=False, stream_status="./stream_status.txt",
                 chkpt_dir=None, stream_cooldown=20):

        self._cfg = self.load_config(config)
        self._cfg["prefix"] = "!"
        log.info(f"Configuration:\n{self._cfg}")

        super().__init__(**self._cfg)
        self.obs = BCFObserver(romfile_path)
        self.obs.load_config(config)

        # bot config
        self._chat_readback = chat_readback
        self._stream_status = stream_status
        self._stream_cooldown = stream_cooldown
        self._chkpt_dir = chkpt_dir or "./"
        self._online_sync = False

        # FIXME: remove observer dependence on provider?
        self._provider = self.obs._provider

        self._users = {}

    def load_config(self, config):
        with open(config, "r") as fin:
            opts = json.load(fin)

        # add additional admin names here
        # These users can execute admin commands
        admins = set(opts.pop("admins", []))
        AuthorizedCommand._AUTHORIZED |= admins
        admins = ', '.join(admins)
        log.info(f"Added {admins} to the authorized users list.")
        # If true-like, will enable Crowd Control
        #_ENABLE_CC = opts.pop("crowd_control", None)
        # FIXME: Ignored, make new class
        opts.pop("crowd_control", None)
        # Base URL for data listings (such as area, characters, bosses...)
        self._doc_base = opts.pop("doc_url", construct_default_doc_url())

        self._stream_cooldown = int(opts.pop("stream_status_cooldown", 20))

        self._online_sync = opts.pop("online_sync", False)

        return opts

    def _init(self, context_file=None, user_data=None, status_file=None):
        user_data = self.obs.unserialize(pth=self._chkpt_dir)
        if user_data is None:
            log.warning("No user data found for this session. Creating new table.")
        else:
            log.info(f"Retrieved user data with {len(user_data)} users")
            self.obs._users = user_data

    #
    # Twitch integration
    #
    # TODO: set this from config
    #@routines.routine(seconds=stream_cooldown)
    @routines.routine(seconds=60)
    async def _serialize(self):
        logging.info(f"Serializing state to {self._chkpt_dir}")
        self.obs.serialize(pth=self._chkpt_dir)

    @routines.routine(seconds=10)
    async def _write_status(self):
        logging.debug("Writing game state...")
        self.write_stream_status()

    # TODO: make sure we're init'd
    @routines.routine(seconds=1)
    async def core_loop(self):
        # core interaction
        logging.debug("Checking current game state...")
        import socket

        # It's possible for the state to change in the middle of procesing
        # so we have to catch a socket timeout here and attempt to carry on
        try:
            self.obs.process_change()
            self.obs.write_stream_status()
        except socket.timeout as e:
            log.error(str(e))
            logging.warn(f"Unable to communicate with game, cannot update.")
        except Exception as e:
            logging.error("Encountered error while processing game state. "
                          "Some attributes may not be updated. Error follows. ")
            log.error(str(e))

    async def event_ready(self):
        logging.warning("HELLO HUMAN, I AM BCFANTASYBOT. FEAR AND LOVE ME.")
        self._init()
        self.core_loop.start()
        #logging.debug(f"Init'd: {self._last_state_drop}, {self._last_status}\n"
                      #f"Users: {len(self._users)}")

    async def event_message(self, msg):
        # if (ctx.author.name.lower() == "crackboombot" and
        # "Type !arena to start" in ctx.content):
        # ctx.content = '!doarena' + " " + ctx.content

        if msg.echo:
            return

        if self._chat_readback:
            # FIXME: This throws weird errors with string decoding issues
            logging.info(msg.content)

        await self.handle_commands(msg)

    async def _chunk_message(self, ctx, msg_array, joiner=' '):
        for outstr in _chunk_string(msg_array, joiner=joiner):
            await ctx.send(outstr)

    #
    # Generic commands
    #
    @commands.command(name='hi')
    async def hi(self, ctx):
        await ctx.send("/me Hi. I'm BC Fantasy Bot. "
                       "You may remember me from such seeds "
                       "as the dumpster fire from last time and "
                       "OHGODNOTHATCLOCKNOOOOOOO.")
    COMMANDS["hi"] = hi

    @commands.command(name='summon')
    async def summon(self, ctx):
        await ctx.send("/me Insufficient MP. Please insert Ether.")
    #COMMANDS["summon"] = summon

    #
    # User-based commands
    #
    async def manage_users(self, ctx, action, *args):
        user = ctx.author.name
        must_be_registered = {"unregister", "userinfo", "userscore",
                              "buy", "sell"}

        if action in {"register"} and self.obs.check_user(user):
            await ctx.send(f"@{user}, you are already registered.")
            return

        elif action in must_be_registered and not self.obs.check_user(user):
            await ctx.send(f"@{user}, you are not registered.")
            return

        if action == "register":
            # Init user
            self.obs.register_user(user)
            await ctx.send(f"@{user}, you are now registered, and have "
                           f"{self.obs._users[user]['score']} Fantasy Points to use. "
                            "Choose a character (char), area, and boss with "
                            "!buy [category]=[item]")
            return
        elif action == "unregister":
            # Remove user
            self.obs.unregister_user(user)
            await ctx.send(f"Bye bye, @{user}")
            return
        elif action == "userinfo":
            # Return user selections
            await ctx.send(self.obs.format_user(user))
            return
        elif action == "userscore":
            score = self.obs._users[user]["score"]
            await ctx.send(f"@{user}, score: {score}")
            return
        elif action == "buy":
            cat, item = args[:2]

            if cat not in self._provider._lookups:
                await ctx.send(f"@{user}: {cat} is an invalid category")
                return

            # FIXME: this is now covered in observer
            if cat == "boss" and self.obs.context.get("boss", None) == item:
                await ctx.send(f"@{user}: you cannot buy the current boss.")
                return

            _user = self.obs._users[user]
            if _user.get(cat, None) is not None:
                await ctx.send(f"@{user}: sell your current {cat} selection first.")
                return

            try:
                cost = self.obs.buy(user, cat, item)
                #await ctx.send(f"@{user}: got it. Your selection for {cat} is {item}")
                return
            except KeyError:
                logging.debug(f"Tried to buy {item}, but encountered a lookup error.")
                await ctx.send(f"@{user}: that {cat} selection is invalid.")
                return
            except IndexError as e:
                await ctx.send(str(e))
                return
            except ValueError as e:
                await ctx.send(str(e))
                return

            await ctx.send(f"Sorry @{user}, that didn't work.")
            return

        elif action == "sell":
            cat = args[0]

            if cat not in self.obs._users[user]:
                await ctx.send(f"@{user}, you have no selection for {cat}.")
                return

            self.obs.sell(user, cat)
            return

    @commands.command(name='register')
    async def register(self, ctx):
        """
        !register -> no arguments, adds user to database
        """
        await self.manage_users(ctx, "register")
    COMMANDS["register"] = register

    @commands.command(name='exploder')
    async def exploder(self, ctx):
        """
        !exploder -> no arguments, deregisters user
        """
        await self.manage_users(ctx, "unregister")
    COMMANDS["unregister"] = exploder

    @commands.command(name='userinfo')
    async def userinfo(self, ctx):
        """
        !userinfo --> no arguments, returns user selections
        """
        await self.manage_users(ctx, "userinfo")
    COMMANDS["userinfo"] = userinfo

    @commands.command(name='userscore')
    async def userscore(self, ctx):
        """
        !userscore --> no arguments, returns user score
        """
        await self.manage_users(ctx, "userscore")
    COMMANDS["userscore"] = userscore

    @commands.command(name='sell')
    async def sell(self, ctx):
        """
        !sell [area|boss|char] sell indicated category and recoup its sell value
        """
        selection = ctx.message.content.lower().split(" ")[1:]
        cat = selection[0]

        if cat == "chat":
            user = ctx.author.name
            await ctx.send(f"HEY EVERYONE. @{user} IS TRYING TO SELL YOU AGAIN...")
            return

        await self.manage_users(ctx, "sell", cat)
    COMMANDS["sell"] = sell

    @commands.command(name='buy')
    async def buy(self, ctx):
        """
        !buy [area|boss|char]=[selection] purchase a selection from a given category. Must have enough Fantasy Points to pay the cost.
        """
        try:
            selection = " ".join(ctx.message.content.lower().split(" ")[1:])
            cat, item = selection.split("=")
        except ValueError:
            log.warning(f"Could not parse buy command: {ctx.message.content}")
            await ctx.send("I didn't understand, please try with "
                           "!buy category=selection")
            return
        cat = cat.lower()

        await self.manage_users(ctx, "buy", cat, item)
    COMMANDS["buy"] = buy

    @commands.command(name='whohas', cls=AuthorizedCommand)
    async def whohas(self, ctx):
        """
        !whohas [item to search for]
        """
        cmd = ctx.message.content.strip().split(" ")
        if len(cmd) != 2:
            await ctx.send("Can only search for one item at a time.")
        item = cmd[1]

        found = self.obs.whohas(item)
        if found is None:
            await ctx.send("No matches found.")
            return

        resp = " | ".join([f"{c}: " + ", ".join(u)
                           for c, u in found.items() if len(u) > 0])
        await ctx.send(f"{item} | " + resp)

    #
    # Informational commands
    #
    @commands.command(name='bcf')
    async def explain(self, ctx):
        """
        Explain what do.
        """
        user = ctx.author.name

        msg = [f"@{user}: Use '!register' to get started. ",
               f"You'll start with 1000 Fantasy Points to spend. ",
               f"You will !buy a character, boss, and area "
               f"(see !bcfinfo for listings). ",
               f"The chosen character will accrue Fantasy Points "
               f"for killing enemies and bosses. ",
               f"Bosses get Fantasy Points for kills and gameovers. ",
               f"Areas get Fantasy Points for "
               f"MIAB, character kills, and gameovers. "]

        await self._chunk_message(ctx, msg, joiner=' ')
    COMMANDS["bcf"] = explain

    @commands.command(name='bcfinfo')
    async def docs(self, ctx):
        """
        Give link to tabular documentation.
        """
        msg = [f"Head to {self._doc_base} for tables on scoring and costs"]
        await self._chunk_message(ctx, msg, joiner=' ')
    COMMANDS["bcf"] = explain

    @commands.command(name='bcfflags')
    async def bcfflags(self, ctx):
        """
        !bcfflags -> no argument, print flags and seed
        """
        if self.obs._flags is not None:
            await ctx.send(f"Flags: {self._flags} | Seed: {self._seed}")
            return
        await ctx.send("No flag information.")
    COMMANDS["bcfflags"] = bcfflags

    @commands.command(name='music')
    async def music(self, ctx):
        """
        !music -> with no arguments, lists current music. With 'list' lists all conversions, with an argument looks up info on mapping.
        """
        cmds = ctx.message.content.split(" ")
        query = cmds[1].strip().lower() if len(cmds) >= 2 else None
        logging.debug(f"Querying music.")

        if query == "list":
            music_list = self._provider.list_music()
            if music_list is None:
                logging.debug(f"No music list to query.")
                await ctx.send("No known music currently.")
                return
            logging.debug(f"Listing known music.")
            msg = ["Known music: "] + music_list
            await self._chunk_message(ctx, msg)
            return

        if query is not None:
            # query music
            logging.debug(f"Querying music, argument {query}")
            song = self._provider.lookup_music(by_name=query)
            if song is None:
                await ctx.send(f"Unknown music {query}")
                return
        else:
            # Current music
            music_id = self.obs._context.get("music", None)
            song = self._provider.lookup_music(by_id=music_id)

        if song is None:
            await ctx.send("No known music currently.")
            return

        await ctx.send(f"{song['orig']} -> {song['new']} | {song['descr']}")
    COMMANDS["music"] = music

    @commands.command(name='sprite')
    async def sprite(self, ctx):
        """
        !sprite -> with no arguments, lists all characters, with an argument looks up info on mapping.
        """
        cmds = ctx.message.content.split(" ")
        logging.debug(f"Querying character sprite.")

        if len(cmds) == 1:
            chars = self._provider.list_sprites() 
            if chars is not None:
                await self._chunk_message(ctx, ["Known chars:"] + chars, joiner=' ')
            else:
                await ctx.send("No character sprite mapping data available.")

            return

        if cmds[1] == "enemy":
            orig = cmds[-1].strip().lower()
            logging.debug(f"Querying monster sprite, argument {orig}")
            char = self._provider.lookup_monster_sprite(orig)
            if char is None:
                await ctx.send("No enemy sprite mapping data available.")
                return
        else:
            orig = cmds[1].strip().lower()
            logging.debug(f"Querying character sprite, argument {orig}")
            char = self._provider.lookup_sprite(orig)
            if char is None:
                await ctx.send("No character sprite mapping data available.")
                return

        if len(char) != 1:
            logging.error(f"Problem finding {orig}")
            # Do nothing for now
            return

        char = char.iloc[0]
        if cmds[1] == "enemy":
            await ctx.send(f"{char['name']} ({char['orig']}) -> {char['sprite']}")
        else:
            await ctx.send(f"{char['orig']} -> {char['cname']} | {char['appearance']}")
    COMMANDS["sprite"] = sprite

    #
    # Context commands
    #

    # Areas
    # TODO: remove
    @commands.command(name='listareas', cls=AuthorizedCommand)
    async def listareas(self, ctx):
        """
        !listareas --> no arguments, link to all available areas
        """
        info = self._provider.list_cat("area",
                                       with_fields=["Area", "Cost"])
        await self._chunk_message(ctx, [f"{i[0]} ({i[1]})" for _, i in info])

    @commands.command(name='areainfo')
    async def areainfo(self, ctx):
        """
        !areainfo [area] list information about given area
        """
        area = " ".join(ctx.message.content.split(" ")[1:]).lower()
        await ctx.send(self._provider.search(area, "Area", "area"))
    COMMANDS["areainfo"] = areainfo

    @commands.command(name='mapinfo')
    async def mapinfo(self, ctx):
        """
        !mapinfo [map ID] list description of map id
        """
        try:
            _, map_id = ctx.message.content.split()
        except ValueError:
            logging.info("mapinfo | no map id, using context")
            map_id = self._game_state.map_id or 0

        map_id = int(map_id)
        map_info = self._provider.lookup_map(by_id=map_id)
        if map_info is not None:
            await ctx.send(f"{map_id}: {map_info['name']} (Area: {map_info['scoring_area']})")
            return

        # FIXME: can we drop this now?
        """
        idx = self._provider._map_info.index.searchsorted(map_id)
        if idx < len(self._provider._map_info):
            left = self._provider._map_info.iloc[idx-1]["name"]
            right = self._provider._map_info.iloc[idx]["name"]
        else:
            left, right = None, None

        with open("missing_maps.txt", "a") as fout:
            fout.write(f"{map_id} ")
        await ctx.send(f"Map ID {map_id} is not in the list; "
                       f"between: {left} | {right}")
        """
    COMMANDS["mapinfo"] = mapinfo

    # Bosses
    @commands.command(name='listbosses', cls=AuthorizedCommand)
    async def listbosses(self, ctx):
        """
        !listbosses --> no arguments, link to all available bosses
        """
        info = self._provider.list_cat("boss",
                                       with_fields=["Boss", "Cost"])
        await self._chunk_message(ctx, [f"{i[0]} ({i[1]})" for _, i in info])

    @commands.command(name='bossinfo')
    async def bossinfo(self, ctx):
        """
        !bossinfo [boss] list information about given boss
        """
        boss = " ".join(ctx.message.content.split(" ")[1:]).lower()
        await ctx.send(self._provider.search(boss, "Boss", "boss"))
    COMMANDS["bossinfo"] = bossinfo

    # Characters
    @commands.command(name='listchars', cls=AuthorizedCommand)
    async def listchars(self, ctx):
        """
        !listchars --> no arguments, link to all available characters
        """
        info = self._provider.list_cat("char",
                                       with_fields=["Character", "Cost", "Kills Enemy"])
        await self._chunk_message(ctx, [f"{i[0]} ({i[1]}, kills: {i[2]})" for _, i in info])

    @commands.command(name='charinfo')
    async def charinfo(self, ctx):
        """
        !charinfo [char] list information about given char
        """
        char = " ".join(ctx.message.content.split(" ")[1:]).lower()
        await ctx.send(self._provider.search(char, "Character", "char"))
    COMMANDS["charinfo"] = charinfo

    @commands.command(name='partynames')
    async def partynames(self, ctx):
        """
        !partynames -> no arguments, list the names of the party
        """
        s = [f"{name}: {alias}"
             for name, alias in self.obs._game_state.party_names.items()]
        await self._chunk_message(ctx, s, joiner=" | ")
    COMMANDS["partynames"] = partynames

    # General
    @commands.command(name='context')
    async def context(self, ctx):
        """
        !context --> no arguments, list the currently active area and boss
        """
        await ctx.send(str(self.obs.context).replace("'", "").replace("{", "").replace("}", ""))
    COMMANDS["context"] = context

    @commands.command(name='leaderboard')
    async def leaderboard(self, ctx):
        """
        !context --> no arguments, list the current players and their scores.
        """
        s = [f"@{user}: {attr['score']}"
             for user, attr in reversed(sorted(self.obs._users.items(),
                                               key=lambda kv: kv[1]['score']))]
        if s != "":
            await self._chunk_message(ctx, s, joiner=" | ")
    COMMANDS["leaderboard"] = leaderboard

    #
    # Admin commands
    #
    @commands.command(name='give', cls=AuthorizedCommand)
    async def give(self, ctx):
        """
        !give --> [list of people to give to] [amt]
        """
        cmd = ctx.message.content.split(" ")[1:]
        if len(cmd) == 0:
            await ctx.send("Invalid !give command")
            return

        val = int(cmd.pop())
        #targets = set(map(str.lower, cmd))
        targets = set(cmd)
        if not targets:
            # Give everyone points
            targets |= set(self.obs._users)
        targets &= set(self.obs._users)

        for user in targets:
            logging.debug(f"Adding {val} to {user} Fantasy Points")
            self.obs._users[user]["score"] += val

    #
    # State handling
    #
    @commands.command(name='set', cls=AuthorizedCommand)
    async def _set(self, ctx):
        """
        !set [boss|area]=value

        Manually set a context category to a value.
        """
        cat, val = ctx.message.content.split(" ")[-1].split("=")
        self.obs.set_context(**{cat: int(val)})

    @commands.command(name='reset', cls=AuthorizedCommand)
    async def reset(self, ctx):
        """
        !reset -> no arguments; reset all contextual and user stores
        """
        # TODO: serialize first, just in case?
        self.reset()
        log.info(f"Reloading configuration from {self._config}")
        self._cfg = self.load_config(self._config)
        await ctx.send("User and context info reset.")

    @commands.command(name='stop', cls=AuthorizedCommand)
    async def stop(self, ctx):
        """
        !stop [|annihilated|kefkadown] Tell the bot to save its contents, possibly for a reason (game over, Kefka beaten).

        Will set the game state to None to prevent further processing.
        """
        cmd = ctx.message.content.split()[1:]

        # Just stopping for the moment, checkpoint and move on.
        if len(cmd) == 0:
            self.obs.halt()
            log.info("Game state discarded. Observer is now halted.")
            await ctx.send("HAMMER TIME. (Checkpointing complete.)")
            return

        if cmd[0] == "annihilated":
            self.obs.halt(end_of_game=True, online_sync=self._online_sync)
            log.info("Game state discarded. Observer is now halted.")
            await ctx.send("Sold all users items.")
            await ctx.send("!wompwomp")
            return
        elif cmd[0] == "kefkadown":
            self.obs.halt(end_of_game=True, online_sync=self._online_sync)
            log.info("Game state discarded. Observer is now halted.")
            await ctx.send("!cb darksl5GG darksl5Kitty ")
            return

        await ctx.send(f"Urecognized stop reason {cmd[0]}")

    #
    # Help commands
    #
    @commands.command(name='help')
    async def _help(self, ctx):
        """
        This command.
        """
        user = ctx.author.name
        cnt = ctx.message.content.lower().split(" ")
        cnt.pop(0)
        if not cnt:
            await ctx.send(f"Available commands: {' '.join(self.COMMANDS.keys())}. "
                           f"Use '!help cmd' (no excl. point on cmd) to get more help.")
            return

        arg = cnt.pop(0)
        if arg not in self.COMMANDS:
            await ctx.send(f"@{user}, that's not a command I have help for. "
                           f"Available commands: {' '.join(self.COMMANDS.keys())}.")
            return

        doc = self.COMMANDS[arg]._callback.__doc__
        await ctx.send(f"help | {arg}: {doc}")
    COMMANDS["help"] = _help

    @commands.command(name='ping', cls=AuthorizedCommand)
    async def ping(self, ctx):
        """
        !ping Emit a ping request to the emulator.
        """
        try:
            result = self.obs._bridge.ping(visual=True)
            if result:
                return
        except:
            pass

        await ctx.send("Ping failed.")

    @commands.command(name='read', cls=AuthorizedCommand)
    async def read(self, ctx):
        """
        !read memaddr Attempt to read the values of a set of memory addresses
        """
        cmd = ctx.message.content.split()[1:]
        try:
            if cmd[0].startswith("0x"):
                st = int(cmd[0], base=16)
            else:
                st = int(cmd[0])
            if len(cmd) == 2:
                if cmd[1].startswith("0x"):
                    en = int(cmd[1], base=16)
                else:
                    en = int(cmd[1])
            else:
                en = st + 1
            data = self.obs.read_ram(st, en)
            if en - st > 1:
                data = data[:128]
            await ctx.send(str(bytes(data)))
        except Exception as e:
            log.error("That didn't work.")
            log.error(str(e))

    @commands.command(name='poke', cls=AuthorizedCommand)
    async def poke(self, ctx):
        """
        !poke memaddr data Attempt to write the data to the memory address
        """
        cmd = ctx.message.content.split()[1:]
        try:
            if cmd[0].startswith("0x"):
                st = int(cmd[0], base=16)
            else:
                st = int(cmd[0])

            data = cmd[1]
            data = bytes([int(b1 + b2, base=16)
                          for b1, b2 in zip(data[:-1], data[1:])])

            self.obs.write_memory(st, data)
            await ctx.send(f"Wrote {len(data)} bytes to {st}")
        except Exception as e:
            log.error("That didn't work.")
            log.error(str(e))
