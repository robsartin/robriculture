"""four_at_eight: four_herders from day 8 (#291).

#289 declared the fourth herder from day 12 and lost 8/16 to ten_melon; its
recorded arm, the same herder from day 8, read 15/16 -- the strongest
champion-row reading of any recorded arm this month, with its anchors and
externals unmeasured. The third arm in a row to out-read its contender, so
this time the arm is the contender.

One number changes: FOURTH_DAY is 8, the day the crew reaches ten and the
third herder starts. Everything else is four_herders', which is ten_melon's.

Declared before measurement: the day, and the controls and criterion in
`harness/four8_bench.py` (posted to #291 before any code).
"""

from __future__ import annotations

from strategies.four_herders import FourHerdersStrategy


class FourAtEightStrategy(FourHerdersStrategy):
    """`four_herders` with the fourth herder from day eight."""

    name = "four_at_eight"
    benchmark = False
    FOURTH_DAY = 8


STRATEGY = FourAtEightStrategy
