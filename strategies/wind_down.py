"""wind_down: town_melon that runs the season out from day 28 -- no land, seed
or herd buys, no feed reserve, no fertilizer held back (#343).

The farm buys and holds a feed buffer of two wheat per head to the last turn,
and buys seed and fertilizer it cannot use before the season ends. From day
28 stopping every buy, keeping no feed (the sweep sells the wheat and none is
bought) and holding no fertilizer read 16/16 (+2.0K) and 16/16 (+2.1K) on two
scratch seed sets, all 32 margins positive (2026-09-24). From day 27 it
loses: the herd goes unfed two days and escapes before its last yield.

One hook changes: `wind_down` is true from WIND_DOWN_DAY, through the seam
field_rival gained for it. Everything else is town_melon's.

Declared before measurement: WIND_DOWN_DAY, and the controls and criterion in
`harness/winddown_bench.py` (posted to #343 before any code).
"""

from __future__ import annotations

from strategies.town_melon import TownMelonStrategy

#: The first day of the wind-down: the herd's last yields land before the
#: season ends, a day earlier and it escapes unfed before them.
WIND_DOWN_DAY = 28


class WindDownStrategy(TownMelonStrategy):
    """`town_melon` that runs the season out from day 28."""

    name = "wind_down"
    benchmark = False

    def wind_down(self, day):
        """True from `WIND_DOWN_DAY` (#343)."""
        return True if (day or 0) >= WIND_DOWN_DAY else None


STRATEGY = WindDownStrategy
