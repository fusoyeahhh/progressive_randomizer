import pathlib
import glob

# FIXME: should probably be in init
def construct_default_doc_url(gh_user="fusoyeahhh",
                              repo="progressive_randomizer",
                              fname="README_data.md"):
    parts = list(pathlib.Path(__file__).parts)[::-1]
    idx = parts.index("progressive_randomizer")
    dst = "/".join(parts[1:idx+1][::-1])
    # FIXME: switch to main branch once merged
    return f"https://github.com/{gh_user}/{repo}/blob/bcf/{dst}/{fname}"
def infer_spoiler_file_name(game_dir="./", src_ext = ".smc", spoil_ext=".txt"):
    romfile = glob.glob(str(pathlib.Path(game_dir) / "*.smc"))
    if len(romfile) > 0:
        return romfile[0].replace(src_ext, spoil_ext)
    return None

def _chunk_string(inlist, joiner=", "):
    """
    Given a list of strings to (ultimately) concatenate and send to twitch chat.

    The list of strings is concatenated (via 'joiner') into strings of lengths that are allowed by twitch chat.

    :param inlist: (list) list of strings to emit
    :param joiner: (str) character to use a joiner
    :return: None
    """

    # Nothing to do here
    if len(inlist) == 0:
        return

    # There's a string in the list which is larger than the allowed count
    # FIXME: we can break up this string too, if needed, possibly by calling this recursively
    assert max([*map(len, inlist)]) < 500, \
                                "Can't fit all messages to buffer length"

    outstr = str(inlist.pop(0))
    # While we have strings to send
    while len(inlist) >= 0:
        # We've reached the end of the input list, drain the remaining buffer and end
        if len(inlist) == 0:
            yield outstr
            return
        # If the next concat would put us over the limit, then we emit, reset, and continue
        elif len(outstr) + len(joiner) + len(inlist[0]) >= 500:
            yield outstr
            outstr = inlist.pop(0)
            continue

        # continue concatenating
        outstr += joiner + str(inlist.pop(0))

try:
    import gspread
    from gspread_dataframe import set_with_dataframe

    def export_to_gsheet(season, ndoc=0):
        """
        Export a `pandas.DataFrame` to a google sheet. Used to synch the season leaderboard.

        :param season: `pandas.DataFrame` to synch
        :param ndoc: Identifier of the sheet to synch
        :return: None
        """

        gc = gspread.service_account()
        sh = gc.open('Season Leaderboard')
        worksheet = sh.get_worksheet(ndoc)
        worksheet.format('1', {'textFormat': {'bold': True}})
        set_with_dataframe(worksheet, season)
except ImportError:
    pass
