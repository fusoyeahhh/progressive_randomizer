# BCFantasy

Beyond Chaos Fantasy

**Supported emulators**
  - RetroArch

## Python Requirements

Tested on python 3.8+.

```bash
$ pip install twitchio pandas
```

...optionally, for gsheet interaction and updates...

```bash
$ pip install twitchio pandas gsheet gsheet-dataframe
```

## Usage

Unzip the code to a location. Open this location and in a new file named `config.json`, copy the following:

```json
{
    "token": "<AUTH_TOKEN>",
    "initial_channels": ["#<CHANNEL>"]
    "admins": ["your_twitch_name", "a_bot_name"],
}
```

And replace the `<...>` values with their approrpriate values. To get an IRC token, see here: https://twitchapps.com/tmi/ . The initial channel is the name of the stream you're attaching to.

Some optional values are also possible:

```json
    "spoiler": "path/to/spoiler.txt",
```

### Starting the Bot

It is recommended that you start RetroArch and start the game before starting the bot. Once this is complete, from the directory of the unzipped code, issue the following command:

```bash
python -m progressive_randomizer.game.ff6.randomizers.bcf -c <path to config file>
```

If no config file is provided (e.g. omitting the `-c ...`) then it will look in the run directory for one named `config.json`. This will start the bot, and it will automatically begin searching for a connection with RetroArch.

You can check for bot prescence by issuing the `!hi` command in twitch chat, and check that the bot is connected to the emulator with the `!ping` command.
