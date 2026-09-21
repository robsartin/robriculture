"""second_melon: fert_sixteen with a second melon wave on days 12-13 (#334).

In 27 of fert_sixteen's 29 decomposable ladder games the opponent earned
15-22K from melon to our 8-11K (#288, 2026-09-21). We plant melon once, in
the eleven early tiles before the day-5 pivot; the second quadrant opens on
day 12 and a melon planted then matures by day 25. Two scratch seed sets
read a day 12-13 window at cap ten as 12/16 and 12/16, +1.3K and +1.9K; a
wider window lost on both.

One hook changes: `melon_windows` returns the day 12-13 window, through the
seam field_rival gained for it. The melon cap stays ten, so the wave takes at
most the tiles the first wave has freed; the fertilizer line from day 16
covers melon by fert_six's crops. Everything else is fert_sixteen's.

Declared before measurement: MELON_WINDOWS, and the controls and criterion
in `harness/melon2_bench.py` (posted to #334 before any code).
"""

from __future__ import annotations

from strategies.fert_sixteen import FertSixteenStrategy

#: The second wave: the two days after the second quadrant opens.
MELON_WINDOWS = ((12, 13),)


class SecondMelonStrategy(FertSixteenStrategy):
    """`fert_sixteen` with a second melon wave on days 12-13."""

    name = "second_melon"
    benchmark = False

    def melon_windows(self):
        """The declared window (#334)."""
        return MELON_WINDOWS


STRATEGY = SecondMelonStrategy
