import os
import json
import datetime

from twitchio.ext import commands, routines

import logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

__version__ = "0.2.0-beta"

from .observer import BCFObserver, InfoProvider
from .utils import _chunk_string

class authorize:
    _AUTHORIZED = set()

    def __init__(self, func):
        self._func = func

    async def __call__(self, ctx):
        user = ctx.author.name
        if self._authenticate(user):
            return self._func(ctx)

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
    def __init__(self, config, romfile_path=None,
                 chat_readback=False, stream_status="./stream_status.txt",
                 chkpt_dir=None, stream_cooldown=20):

        self._config = config
        self._cfg = self.load_config(config)
        self._cfg["prefix"] = "!"
        log.info(self._cfg)

        super().__init__(**self._cfg)
        self.obs = BCFObserver(romfile_path)
        self.obs.load_config(config)

        # bot config
        self._chat_readback = chat_readback
        self._stream_status = stream_status
        self._stream_cooldown = stream_cooldown
        self._chkpt_dir = chkpt_dir
        self._doc_base = None
        # FIXME: can this go away?
        self._skip_auth = False

        self._provider = InfoProvider()

        self._users = {}

    def load_config(self, config):
        with open(config, "r") as fin:
            opts = json.load(fin)

        # add additional admin names here
        # These users can execute admin commands
        authorize._AUTHORIZED_USERS = set(opts.pop("admins", []))
        # If true-like, will enable Crowd Control
        #_ENABLE_CC = opts.pop("crowd_control", None)
        # FIXME: Ignored, make new class
        opts.pop("crowd_control", None)
        # Base URL for data listings (such as area, characters, bosses...)
        self._doc_base = opts.pop("doc_url", "https://github.com/fusoyeahhh/BCFantasy/blob/main/")

        self._stream_cooldown = int(opts.pop("stream_status_cooldown", 20))

        return opts

    def _init(self, context_file=None, user_data=None, status_file=None):
        if os.path.exists(context_file):
            with open(context_file, "r") as fin:
                self._context = json.load(fin)
            logging.debug(self._context)
        else:
            logging.debug("No context file found")

        # find latest
        try:
            with open(user_data, "r") as fin:
                self._users = json.load(fin)
            logging.debug(self._users)
        except IndexError:
            pass

        self._last_status = {}
        if os.path.exists(status_file):
            with open(status_file, "r") as fin:
                self._last_status = json.load(fin)

    #
    # Twitch integration
    #
    # TODO: set this from config
    #@routines.routine(seconds=stream_cooldown)
    @routines.routine(seconds=60)
    async def _serialize(self):
        logging.debug("Serializing state...")
        self.serialize(pth=self._chkpt_dir)

    @routines.routine(seconds=10)
    async def _write_status(self):
        logging.debug("Writing game state...")
        self.write_stream_status()

    # TODO: make sure we're init'd
    @routines.routine(seconds=1)
    async def core_loop(self):
        # core interaction
        self.process_change()

    async def event_ready(self):
        logging.warning("HELLO HUMAN, I AM BCFANTASYBOT. FEAR AND LOVE ME.")

        udata_file = os.path.join(self._chkpt_dir, "user_data*.json")
        import glob
        latest = sorted(glob.glob(udata_file),
                        key=lambda f: os.path.getmtime(f))[-1]

        self._init()

        self._skip_auth = False
        self._status = None
        self._last_state_drop = -1

        logging.debug(f"Init'd: {self._last_state_drop}, {self._last_status}\n"
                      f"Users: {len(self._users)}")

        # Event poller
        #asyncio.create_task(_poll())
        # Crowd control queue
        #if _ENABLE_CC:
            #asyncio.create_task(_check_queue())

    async def event_message(self, ctx):
        # if (ctx.author.name.lower() == "crackboombot" and
        # "Type !arena to start" in ctx.content):
        # ctx.content = '!doarena' + " " + ctx.content

        if self._chat_readback:
            # FIXME: This throws weird errors with string decoding issues
            logging.info(ctx.content)

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

    @commands.command(name='summon')
    async def summon(self, ctx):
        await ctx.send("/me Insufficient MP. Please insert Ether.")

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
            score = self._users[user]["score"]
            await ctx.send(f"@{user}, score: {score}")
            return
        elif action == "buy":
            cat, item = args[:2]

            if cat not in self.obs._provider._lookups:
                await ctx.send(f"@{user}: {cat} is an invalid category")
                return

            # FIXME
            if cat == "boss" and cat in self.obs.context.get("boss", None) == item:
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

    @commands.command(name='exploder')
    async def exploder(self, ctx):
        """
        !exploder -> no arguments, deregisters user
        """
        await self.manage_users(ctx, "unregister")

    @commands.command(name='userinfo')
    async def userinfo(self, ctx):
        """
        !userinfo --> no arguments, returns user selections
        """
        await self.manage_users(ctx, "userinfo")

    @commands.command(name='userscore')
    async def userscore(self, ctx):
        """
        !userscore --> no arguments, returns user score
        """
        await self.manage_users(ctx, "userscore")

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


    @commands.command(name='whohas')
    #@authorize
    async def whohas(self, ctx):
        """
        !whohas [item to search for]
        """
        raise NotImplementedError
        self.whohas(" ".join(ctx.message.content.split(" ")[1:]).strip())

        # Initial scan
        # FIXME: implement a fuzzy match as well
        import pandas
        _users = pandas.DataFrame(self.obs._users)
        found = _users.loc[(_users == item).any(axis=1)]
        if found is None:
            await ctx.send("No matches found.")
            return

        await ctx.send(f"{item} | {', '.join(found.index)}")


    #
    # Informational commands
    #
    @commands.command(name='bcf')
    async def explain(self, ctx):
        """
        Explain what do.
        """
        user = ctx.author.name
        self._chunk_message([f"@{user}: Use '!register' to get started.",
                             f"You'll start with 1000 Fantasy Points to spend.",
                             f"You will !buy a character, boss, and area (see !bcfinfo for listings).",
                             f"The chosen character will accrue Fantasy Points for killing enemies and bosses.",
                             f"Bosses get Fantasy Points for kills and gameovers.",
                             f"Areas get Fantasy Points for MIAB, character kills, and gameovers."],
                             joiner=' ')

    @commands.command(name='bcfflags')
    async def bcfflags(self, ctx):
        """
        !bcfflags -> no argument, print flags and seed
        """
        if self.obs._flags is not None:
            await ctx.send(f"Flags: {self._flags} | Seed: {self._seed}")
            return
        await ctx.send("No flag information.")

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
            self._chunk_message(ctx, msg)
            return

        if query is not None:
            # query music
            logging.debug(f"Querying music, argument {query}")
            song = self._provider.lookup_music(by_name=query)
        else:
            # Current music
            music_id = self.obs._context.get("music", None)
            song = self._provider.lookup_music(by_id=music_id)

        if song is None:
            await ctx.send("No known music currently.")
            return

        await ctx.send(f"{song['orig']} -> {song['new']} | {song['descr']}")

    @commands.command(name='sprite')
    async def sprite(self, ctx):
        """
        !sprite -> with no arguments, lists all characters, with an argument looks up info on mapping.
        """
        cmds = ctx.message.content.split(" ")
        logging.debug(f"Querying character sprite.")

        if len(cmds) == 1:
            chars = self.obs._provider.list_sprites() 
            if chars is not None:
                self._chunk_message(ctx, ["Known chars: "] + chars, joiner=' ')
            else:
                await ctx.send("No character sprite mapping data available.")

            return

        if cmds[1] == "enemy":
            orig = cmds[-1].strip().lower()
            logging.debug(f"Querying monster sprite, argument {orig}")
            char = self._provider.lookup_monster_sprite(orig)
            if char is None:
                await ctx.send("No character sprite mapping data available.")
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
            await ctx.send(f"{char['enemy_id']} -> {char['sprite']}")
        else:
            await ctx.send(f"{char['orig']} -> {char['cname']} | {char['appearance']}")

    #
    # Context commands
    #

    # Areas
    # TODO: remove
    @commands.command(name='listareas')
    #@authorize
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

    # Bosses
    @commands.command(name='listbosses')
    #@authorize
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

    # Characters
    @commands.command(name='listchars')
    #@authorize
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

    @commands.command(name='partynames')
    async def partynames(self, ctx):
        """
        !partynames -> no arguments, list the names of the party
        """
        # FIXME
        await ctx.send("No party information at this time.")
        """
        s = [f"{name}: {alias}"
             for name, alias in bot._last_status["party"].items()]
        self._chunk_message(s, joiner=" | "))
        """

    # General
    @commands.command(name='context')
    async def context(self, ctx):
        """
        !context --> no arguments, list the currently active area and boss
        """
        await ctx.send(str(self.obs.context).replace("'", "").replace("{", "").replace("}", ""))

    @commands.command(name='leaderboard')
    async def leaderboard(self, ctx):
        """
        !context --> no arguments, list the current players and their scores.
        """
        s = [f"@{user}: {attr['score']}"
             for user, attr in reversed(sorted(self.obs._users.items(),
                                               key=lambda kv: kv[1]['score']))]
        await self._chunk_message(ctx, s, joiner=" | ")

    #
    # Admin commands
    #
    @commands.command(name='give')
    #@authorize
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
    @commands.command(name='set')
    #@authorize
    async def _set(self, ctx):
        """
        !set [boss|area]=value

        Manually set a context category to a value.
        """
        cat, val = ctx.message.content.split(" ")[-1].split("=")
        self.context(**{cat: int(val)})

    @commands.command(name='reset')
    #@authorize
    async def reset(self, ctx):
        """
        !reset -> no arguments; reset all contextual and user stores
        """
        # TODO: serialize first, just in case?
        self.reset()
        log.info(f"Reloading configuration from {self._config}")
        self._cfg = self.load_config(self._config)
        await ctx.send("User and context info reset.")

    @commands.command(name='stop')
    #@authorize
    async def stop(self, ctx):
        """
        !stop [|annihilated|kefkadown] Tell the bot to save its contents, possibly for a reason (game over, Kefka beaten).

        Will set the game state to None to prevent further processing.
        """
        cmd = ctx.message.content.split()[1:]

        # Just stopping for the moment, checkpoint and move on.
        if len(cmd) == 0:
            self.halt()
            await ctx.send("HAMMER TIME. (Checkpointing complete.)")
            return

        if cmd[0] == "annihilated":
            self.halt(end_of_game=True)
            await ctx.send("Sold all users items.")
            await ctx.send("!wompwomp")
            return
        elif cmd[0] == "kefkadown":
            self.halt(end_of_game=True)
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
        #FIXME:
        await ctx.send(f"Help unavailable at this time.")

        """
        user = ctx.author.name
        cnt = ctx.content.lower().split(" ")
        cnt.pop(0)
        if not cnt:
            await ctx.send(f"Available commands: {' '.join(COMMANDS.keys())}. Use '!help cmd' (no excl. point on cmd) to get more help.")
            return

        arg = cnt.pop(0)
        if arg not in COMMANDS:
            await ctx.send(f"@{user}, that's not a command I have help for. Available commands: {' '.join(COMMANDS.keys())}.")
            return

        doc = COMMANDS[arg]._callback.__doc__
        #print(COMMANDS[arg])
        await ctx.send(f"help | {arg}: {doc}")
        """
