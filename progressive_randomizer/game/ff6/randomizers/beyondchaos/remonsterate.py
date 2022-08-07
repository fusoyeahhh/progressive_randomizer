import sys
import os
from shutil import copyfile

import logging
log = logging.getLogger()

from ... import FF6StaticRandomizer

from . import _BeyondChaos

from BeyondChaos.beyondchaos import monsterrandomizer
from BeyondChaos.beyondchaos import customthreadpool
from BeyondChaos.remonsterate import remonsterate
import BeyondChaos

class Remonsterate(FF6StaticRandomizer, _BeyondChaos):
    def __init__(self, seed, flags):
        super().__init__()
        self.install_bc()

        self._seed = seed
        self._flags = flags

    def _via_console(self, **kwargs):
        thread = customthreadpool.ThreadWithReturnValue(target=remonsterate,
                                                        kwargs=kwargs)
        thread.start()
        remonsterate_results = thread.join()
        if not remonsterate_results:
            # If there were no results, We can assume remonsterate generated an OverflowError.
            raise OverflowError
        return remonsterate_results

    def _via_other(self, **kwargs):
        pool = customthreadpool.NonDaemonPool(1)
        x = pool.apply_async(func=remonsterate, kwds=kwargs)
        remonsterate_results = x.get()
        pool.close()
        pool.join()
        return remonsterate_results

    def apply(self):
        import pathlib
        basedir = pathlib.Path(remonsterate.__file__).resolve().parent
        remonsterate.remonsterate(
            outfile=self.logger.outfile,
            seed=self._seed,
            monsters_tags_filename=basedir / "monsters_and_tags.txt",
            images_tags_filename=basedir / "images_and_tags.txt",
            rom_type="1.0",
            list_of_monsters=monsterrandomizer.get_monsters(self.logger.outfile),
            asset_path=basedir / "sprites"
        )
        return {}

    def apply_with_retry(self, using_console=False, max_attempts=10):
        outfile = self.logger.outfile
        # FIXME: use temporary file
        #backup_path = outfile[:outfile.rindex('.')] + '.backup' + outfile[outfile.rindex('.'):]
        backup_path = outfile + '.backup'
        copyfile(src=outfile, dst=backup_path)
        attempt_number = 0

        while attempt_number < max_attempts:
            kwargs = {
                "outfile": outfile,
                "seed": (self._seed + attempt_number),
                "rom_type": "1.0",
                "list_of_monsters": monsterrandomizer.get_monsters(outfile)
            }
            try:
                if not using_console:
                    self._via_console(**kwargs)
                elif using_console:
                    self._via_other(**kwargs)
            except OverflowError as e:
                log.warning(str(e))
                log.warning("Remonsterate: An error occurred attempting to remonsterate. Trying again...")
                # Replace backup file
                copyfile(src=backup_path, dst=outfile)
                attempt_number = attempt_number + 1
                continue
            break

        # Remonsterate finished
        # FIXME: this isn't going to do quite the same thing now
        #self.logging.fout = open(outfile, "r+b")
        os.remove(backup_path)
        #if remonsterate_results:
            #for result in remonsterate_results:
                #log(str(result) + '\n', section='remonsterate')

        return {}