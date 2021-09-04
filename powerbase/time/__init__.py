from .interval import *
from powerbase.core.time import TimeDelta

# Syntax
import pandas as pd
import calendar

from .construct import get_between, get_before, get_after, get_full_cycle

from powerbase.core.time import PARSERS
PARSERS.update(
    {
        re.compile(r"time of (?P<type_>month|week|day|hour|minute) between (?P<start>.+) and (?P<end>.+)"): get_between,
        re.compile(r"time of (?P<type_>month|week|day|hour|minute) after (?P<start>.+)"): get_after,
        re.compile(r"time of (?P<type_>month|week|day|hour|minute) before (?P<end>.+)"): get_before,
    }
)