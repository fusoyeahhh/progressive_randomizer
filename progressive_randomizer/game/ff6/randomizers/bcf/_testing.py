import sys

from twitchio import Message, PartialChatter, Channel
from twitchio.ext import commands
from twitchio.ext.commands.stringparser import StringParser

from .observer import BCFObserver, BattleState, GameState

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

def test_command(bot, cmd, cnt, debug=False):
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
                name="test_twitch_user"
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
    asyncio.run(test())

def test_bot():
    import pprint
    from .bot import BCF

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

    #print("--- Testing Command: whohas ---")
    #test_command(bot, bot.whohas, "!whohas Terra")

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

if __name__ == "__main__":
    test_observer()
    test_bot()