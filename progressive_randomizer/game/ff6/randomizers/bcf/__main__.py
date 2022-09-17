import sys
import logging
logging.basicConfig(stream=sys.stdout, level=logging.INFO)
log = logging.getLogger()

from .bot import BCF

if __name__ == "__main__":
    bot.run()
