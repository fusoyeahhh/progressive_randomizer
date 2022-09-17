import sys
import logging
logging.basicConfig(stream=sys.stdout, level=logging.INFO)
log = logging.getLogger()

from argparse import ArgumentParser

from .bot import BCF

argp = ArgumentParser()
argp.add_argument("-c", "--config-file", help="Path to configuration file.")

if __name__ == "__main__":
    args = argp.parse_args()

    bot = BCF(args.config_file or "config.json")
    bot.run()
