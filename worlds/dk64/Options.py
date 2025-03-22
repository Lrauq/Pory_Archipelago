from dataclasses import dataclass
import typing

from Options import Choice, PerGameCommonOptions, Range, Option, Toggle, DeathLink, DefaultOnToggle, OptionList

from DK64R.randomizer.Enums.Settings import SettingsStringEnum
from DK64R.randomizer.Enums.Settings import SettingsStringTypeMap
from DK64R.randomizer.Enums.Settings import SettingsStringDataType
from DK64R.randomizer.Enums.Settings import SettingsMap as DK64RSettingsMap


# DK64_TODO: Get Options from DK64R

class Goal(Choice):
    """
    Determines the goal of the seed
    """
    display_name = "Goal"
    option_krool = 0
    default = 0
    
class ClimbingShuffle(Toggle):
    """
    Whether or not you shuffle the Climbing ability into the world(s)
    """
    display_name = "Climbing Shuffle"


@dataclass
class DK64Options(PerGameCommonOptions):
    goal: Goal
    climbing_shuffle: ClimbingShuffle
