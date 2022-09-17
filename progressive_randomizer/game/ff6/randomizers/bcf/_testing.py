import sys
import pprint

from twitchio import Message, PartialChatter, Channel
from twitchio.ext import commands

from .observer import BCFObserver, BattleState, GameState
from .bot import BCF, AuthorizedCommand

from .....io.filebased import FileBasedBridge

from .....io import BaseEmuIO

import logging
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

"""
import logging
loggers = [logging.getLogger(name) for name in logging.root.manager.loggerDict]
for logger in loggers:
    logger.setLevel(logging.DEBUG)
"""

#
# Observer testing
#
class TestBattleState(BattleState):
    def __init__(self, ram_file):
        super().__init__()
        self._bridge = FileBasedBridge(ram_file)

    def read_ram(self, st, en=None, width=None):
        return super().read_ram(st, en, width=width, offset=0)

class TestGameState(GameState):
    def __init__(self, ram_file):
        super().__init__()
        self._bridge = FileBasedBridge(ram_file)

    def read_ram(self, st, en=None, width=None):
        return super().read_ram(st, en, width=width, offset=0)

class TestObserver(BCFObserver):
    def __init__(self, ram_file, rom_file):
        super().__init__(rom_file)
        self._bridge = FileBasedBridge(ram_file)

        self._game_state = TestGameState(ram_file)

    def read_ram(self, st,config,  en=None, width=None):
        return super().read_ram(st, en, width=width, offset=0)

def test_observer():
    import tempfile
    import os
    import pprint

    tmpf = tempfile.NamedTemporaryFile(delete=False)
    tmpd = tempfile.mkdtemp()
    TestObserver.generate_default_config(tmpf.name, **{
        "flags": "dummy_flags",
        "seed": "0",
        "season": "testing",
        "checkpoint_directory": tmpd
    })

    test_bcf = TestObserver("ram_dump.bin", "ff6.smc")
    test_bcf.load_config(tmpf.name)
    #print(test_state.write_status())

    print("--- User interaction ---")
    # User interaction
    test_bcf.register_user("test")
    print(test_bcf.format_user("test"))
    test_bcf.unregister_user("test")
    try:
        print(test_bcf.format_user("test"))
    except KeyError:
        print("No such user. This is expected.")
    test_bcf.register_user("test")

    try:
        test_bcf.sell("test", "boss")
    except KeyError as e:
        print(f"Expecting keyerror: {str(e)}")

    test_bcf.buy("test", "char", "Terra")
    print(test_bcf.format_user("test"))
    test_bcf.buy("test", "area", "Wob overwo")
    print(test_bcf.format_user("test"))
    test_bcf.buy("test", "boss", "Var")
    print(test_bcf.format_user("test"))

    print("--- Game state ---")
    # Game state related tests
    test_game_state = TestGameState("ram_dump.bin")
    for func in (test_game_state._menu_check,
                 test_game_state._battle_check,
                 test_game_state._field_check):
        print(f"Game state ({func}): {func()}")
    print(f"Game state: {test_game_state.game_state.name}")
    print(f"party: {test_game_state.party}")
    print(f"party name mapping: {test_game_state.party_names}")
    print(f"On Veldt: {test_game_state.on_veldt}")
    print(f"Is game over: {test_game_state.is_gameover}")
    print(f"Is miab: {test_game_state.is_miab}")
    print(f"Map ID: {test_game_state.map_id}, has changed: {test_game_state.map_changed}")
    print(f"Music ID: {test_game_state.music_id}, has changed: {test_game_state.music_changed}")

    # Battle Items
    print("--- Battle state ---")
    test_battle_state = TestBattleState("ram_dump.bin")
    print(f"formation id: {test_battle_state.eform_id}")
    curr_party = test_battle_state.battle_party
    print(f"current party: {curr_party}")
    print(f"actor map: {test_battle_state.actors}")
    print(f"party status: {test_battle_state.party_status}")
    print(f"enemy status: {test_battle_state.enemy_status}")
    print(f"last targetted: {test_battle_state.last_targetted}")

    test_battle_state.process_battle_change()

    # General state
    print("--- General state ---")
    # Do this once so the test object doesn't think it's changed
    test_bcf._game_state.game_state_changed
    test_bcf._battle_state = test_battle_state

    test_bcf.process_change()
    print(test_bcf.context)

    print(f"Change area WOB: {test_bcf._can_change_area(0)}")
    print(f"Change area gameover map: {test_bcf._can_change_area(5)}")
    print(f"Change area SF basement: {test_bcf._can_change_area(89)}")
    print(f"Change boss Whelk: {test_bcf._can_change_boss(432)}")
    print(f"Change boss form 0: {test_bcf._can_change_boss(0)}")

    print("--- Event handling ---")

    test_bcf._sell_all()
    test_bcf.buy("test", "area", test_bcf.context["area"])
    test_bcf.buy("test", "char", "Terra")
    test_bcf.buy("test", "boss", "Vargas")
    test_bcf.score_gameover()
    test_bcf.score_miab()
    pprint.pprint(test_bcf._msg_buf)
    test_bcf.score_pkill(0, eform_id=0)
    test_bcf.score_pkill(0, n=4, eform_id=0)
    test_bcf.score_pkill(0, eform_id=432)
    test_bcf.score_pdeath(0)
    pprint.pprint(test_bcf._msg_buf)
    test_bcf.write_stream_status(scoring_file=None)
    test_bcf.write_stream_status("Test override", scoring_file=None)

    print("--- User cleanup ---")
    for cat in ["char", "area", "boss"]:
        test_bcf.sell("test", cat)
    print(test_bcf.format_user("test"))

    test_bcf.buy("test", "boss", "Var")
    test_bcf._sell_all()
    print(test_bcf.format_user("test"))

    # This calls halt
    #test_bcf.handle_gameover()
    #test_bcf.halt()

    #test_bcf.serialize(season_update=True)
    #test_bcf.process_change()

    tmpf.close()
    os.unlink(tmpf.name)

#
# Bot testing
#

def test_command(bot, cmd, cnt, user="test_twitch_user",
                 debug=False, skip_auth=False):
    import asyncio

    class DummyChannel(Channel):
        def __init__(name):
            super().__init__("test_channel", None)

    async def test():
        msg = Message(
            _raw_data=None,
            content=cnt,
            author=PartialChatter(
                None,
                id=0,
                name=user,
            ),
            channel=None,
            tags={"id": None}
        )
        return await bot.get_context(msg)
    ctx = asyncio.run(test())

    class DummyIO:
        async def send(self, msg):
            print(msg)
    ctx._ws = DummyIO()

    async def test():
        try:
            if debug:
                await cmd._callback(bot, ctx)
        except Exception as e:
            print(f"Command {cnt} failed. Exception follows.")
            print(e)
            raise e
        await cmd(ctx)

    if skip_auth and user not in AuthorizedCommand._AUTHORIZED:
        AuthorizedCommand._AUTHORIZED.add(user)
        asyncio.run(test())
        AuthorizedCommand._AUTHORIZED.remove(user)
    else:
        asyncio.run(test())

def test_bot():
    bot = BCF("config.json")

    print("--- Testing Command: hi ---")
    print("Command: !hi")
    test_command(bot, bot.hi, "!hi")
    print("--- Testing Command: summon ---")
    print("Command: !summon")
    test_command(bot, bot.summon, "!summon")
    #print("--- Testing Command: bcf ---")
    #print("Command: !bcf")
    #test_command(bot, bot.explain, "!bcf")

    print("--- Testing Command: exploder ---")
    print("Command: !exploder")
    test_command(bot, bot.exploder, "!exploder")
    print("Command: !register")
    test_command(bot, bot.register, "!register")
    print("Command: !exploder")
    test_command(bot, bot.exploder, "!exploder")

    print("--- Testing Command: register ---")
    print("Command: !register")
    test_command(bot, bot.register, "!register")
    pprint.pprint(bot.obs._users)
    print("Command: !register")
    test_command(bot, bot.register, "!register")
    pprint.pprint(bot.obs._users)

    print("--- Testing Command: buy ---")
    test_command(bot, bot.buy, "!buy chr Terra")
    print("!buy chr Terra")
    test_command(bot, bot.buy, "!buy char Terra")
    print("!buy char Terra")
    test_command(bot, bot.buy, "!buy chat=Terra")

    print("!buy char=Terra")
    test_command(bot, bot.buy, "!buy char=Terra")
    print("!buy area=Kolt")
    test_command(bot, bot.buy, "!buy area=Kolt")
    pprint.pprint(bot.obs._users)

    print("!buy area=WoB Ov")
    test_command(bot, bot.buy, "!buy area=WoB Ov")

    print("--- Testing Command: whohas ---")
    test_command(bot, bot.whohas, "!whohas Terra", skip_auth=True)

    print("--- Testing Command: sell ---")
    print("!sell chr")
    test_command(bot, bot.sell, "!sell chr")
    print("!sell char Terra")
    test_command(bot, bot.sell, "!sell char Terra")
    print("!sell char Terra")
    test_command(bot, bot.sell, "!sell char Terra")
    print("!sell chat=Terra")
    test_command(bot, bot.sell, "!sell chat=Terra")
    print("!sell chat")
    test_command(bot, bot.sell, "!sell chat")

    print("!sell char")
    test_command(bot, bot.sell, "!sell char")
    print("!sell area")
    test_command(bot, bot.sell, "!sell area")
    print("!sell area")
    test_command(bot, bot.sell, "!sell area")
    pprint.pprint(bot.obs._users)

    print("--- Testing Command: leaderboard ---")
    print("Command: !leaderboard")
    test_command(bot, bot.leaderboard, "!leaderboard")

    print("--- Testing Command: give ---")
    print("Command: !give 100")
    test_command(bot, bot.give, "!give 100", skip_auth=True)
    print("Command: !give test 100")
    test_command(bot, bot.give, "!give test 100", skip_auth=True)
    print("Command: !give test_twitch_user 100")
    test_command(bot, bot.give, "!give test_twitch_user 1", skip_auth=True)
    pprint.pprint(bot.obs._users)

    print("--- Testing Command: bcfflags ---")
    print("Command: !bcfflags")
    test_command(bot, bot.bcfflags, "!bcfflags", user="test_bcfflags")

    # Start switching users to not trigger cooldown checks
    print("--- Testing Command: music ---")
    print("Command: !music")
    test_command(bot, bot.music, "!music", user="test_music")
    print("Command: !set music=1")
    test_command(bot, bot._set, "!set music=1", user="test_user")
    print("Command: !music")
    test_command(bot, bot.music, "!music", user="test_music")
    print("Command: !music list")
    test_command(bot, bot.music, "!music list", user="test_music")
    print("Command: !music songname")
    test_command(bot, bot.music, "!music songname", user="test_music")
    print("Command: !music prelude")
    test_command(bot, bot.music, "!music prelude", user="test_music")
    #print("Command: !music sd2_dwarf")
    #test_command(bot, bot.music, "!music prelude", user="test_music")

    print("--- Testing Command: sprite ---")
    print("Command: !sprite")
    test_command(bot, bot.sprite, "!sprite", user="test_user_sprite")
    print("Command: !sprite enemy Acani")
    test_command(bot, bot.sprite, "!sprite enemy Acani", user="test_user_sprite")
    print("Command: !sprite terra")
    test_command(bot, bot.sprite, "!sprite terra", user="test_user_sprite")

    print("--- Testing Command: listareas ---")
    print("Command: !listareas")
    test_command(bot, bot.listareas, "!listareas", user="test_user", skip_auth=True)

    print("--- Testing Command: areainfo ---")
    print("Command: !areainfo")
    test_command(bot, bot.areainfo, "!areainfo Ebot", user="test_user")
    test_command(bot, bot.areainfo, "!areainfo WoB", user="test_user")
    test_command(bot, bot.areainfo, "!areainfo notanarea", user="test_user")

    print("--- Testing Command: listbosses ---")
    print("Command: !listbosses")
    test_command(bot, bot.listbosses, "!listbosses", user="test_user_boss", skip_auth=True)

    print("--- Testing Command: bossinfo ---")
    print("Command: !bossinfo")
    test_command(bot, bot.bossinfo, "!bossinfo Varg", user="test_user_boss")
    test_command(bot, bot.bossinfo, "!bossinfo Kefka", user="test_user_boss")
    test_command(bot, bot.bossinfo, "!bossinfo notaboss", user="test_user_boss")

    print("--- Testing Command: listchars ---")
    print("Command: !listcharss")
    test_command(bot, bot.listchars, "!listchars", user="test_user", skip_auth=True)

    print("--- Testing Command: charsinfo ---")
    print("Command: !charinfo")
    test_command(bot, bot.charinfo, "!charinfo Sabin", user="test_user")
    test_command(bot, bot.charinfo, "!charinfo C", user="test_user")
    test_command(bot, bot.charinfo, "!charinfo Leo", user="test_user")

    print("--- Testing Command: context ---")
    print("Command: !context")
    test_command(bot, bot.context, "!context", user="test_user")

    print("--- Testing Command: set ---")
    print("Command: !set boss=432")
    test_command(bot, bot._set, "!set boss=432", user="test_user", skip_auth=True)
    test_command(bot, bot.context, "!context", user="test_user")

    print("Command: !set area=0")
    test_command(bot, bot._set, "!set area=0", user="test_user", skip_auth=True)
    test_command(bot, bot.context, "!context", user="test_user")

    print("Command: !set music=1")
    test_command(bot, bot._set, "!set music=1", user="test_user", skip_auth=True)
    test_command(bot, bot.context, "!context", user="test_user")

    print("--- Testing Command: stop ---")
    print("Command: !stop")
    pprint.pprint(bot.obs._users)
    test_command(bot, bot.stop, "!stop", user="test_user_stop", skip_auth=True, debug=True)
    pprint.pprint(bot.obs._users)
    test_command(bot, bot.leaderboard, "!leaderboard", user="test_user_stop", skip_auth=True)

    print("Command: !stop annihilated")
    pprint.pprint(bot.obs._users)
    test_command(bot, bot.stop, "!stop annihilated", user="test_user_stop", skip_auth=True)
    pprint.pprint(bot.obs._users)
    test_command(bot, bot.leaderboard, "!leaderboard", user="test_user_stop", skip_auth=True)

    print("Command: !stop kefkadown")
    pprint.pprint(bot.obs._users)
    test_command(bot, bot.stop, "!stop kefkadown", user="test_user_stop", skip_auth=True)
    pprint.pprint(bot.obs._users)
    test_command(bot, bot.leaderboard, "!leaderboard", user="test_user_stop", skip_auth=True)

    # We do this separately, because it requires
    # actual interaction with the memory
    bot.obs = TestObserver("ram_dump.bin", "ff6.smc")
    print("--- Testing Command: ping ---")
    print("Command: !ping")
    test_command(bot, bot.ping, "!ping", user="test_user_ping", skip_auth=True)

    print("--- Testing Command: partynames ---")
    print("Command: !partynames")
    test_command(bot, bot.partynames, "!partynames", user="test_user_party")

if __name__ == "__main__":
    test_observer()
    test_bot()
