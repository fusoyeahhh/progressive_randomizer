import logging
log = logging.getLogger()

from ... import FF6StaticRandomizer
from .....tasks import (
    RandomizationTask,
    WriteBytes
)

from . import substitutions
from .substitutions import SubstitutionTask

from BeyondChaos import utils as bc_utils

GAME_NAME = b'FF6 BCCE'

def detect_bc(game_name):
    if game_name.startswith(GAME_NAME):
        return FF6StaticRandomizer
    return None

class BeyondChaosRandomizer(FF6StaticRandomizer):

    def __init__(self, seed, flags):
        super().__init__()
        self._seed = seed
        self._flags = flags

    """
    def christmas_mode(self, bindata):
        pass

    def halloween_mode(self, bindata):
        pass
        
    def random_boost(self, bindata):
        pass

    def scenario_not_taken(self):
        pass
    """

    #
    # From randomizer.py
    #
    # NOTE: these have requirements in Options_
    def auto_recruit_gau(self, **kwargs):
        # FIXME: use this
        stays_in_wor = kwargs.get("stays_in_wor", True)
        return [
            SubstitutionTask.sub_with_args(location=0xCFE1A,
                                           sub=bc_utils.AutoRecruitGauSub),
            SubstitutionTask.sub_with_args(location=0x24856,
                                           bytestring=bytes[0x89, 0xFF],
                                           sub=bc_utils.Substitution),
        ]

    def auto_learn_rage(self):
        return [SubstitutionTask.sub_with_args(location=0x23B73,
                                               sub=bc_utils.AutoLearnRageSub)
        ]

    def manage_commands(self):
        return [
            SubstitutionTask.sub_with_args(**task)
            for name, task in substitutions.manage_commands_writes.items()
        ]