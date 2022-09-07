import sys
import logging
logging.basicConfig(stream=sys.stdout, level=logging.INFO)
log = logging.getLogger()

import time
from .observer import BCFObserver

if __name__ == "__main__":
    #bot._last_state_drop = -1
    #bot.run()

    obs = BCFObserver()
    obs.register_user("TEST USER")
    obs._users["TEST USER"] = {"score": 0, "char": "Terra", "area": "WoB Overworld"}
    while True:
        obs.process_change()
        #log.info(str(time.time()))
        #log.info(obs._context)
        log.info(obs._game_state.play_state.name)
        log.info(obs._context)
        log.info(obs.context)
        time.sleep(1)
