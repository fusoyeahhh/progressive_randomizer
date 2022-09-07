import sys

from .observer import BCFObserver, BattleState, GameState

from .....io.fake_ram import FileBasedBridge

from .....io import BaseEmuIO

import logging
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

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

    def read_ram(self, st, en=None, width=None):
        return super().read_ram(st, en, width=width, offset=0)


if __name__ == "__main__":
    #from .bot import BCF
    import tempfile
    import os

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

    import pprint
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
