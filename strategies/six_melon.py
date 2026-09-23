"""six_melon: town_melon that waters a ready melon before cutting it, and
carries eighteen (#341).

In every live-town ladder loss of town_melon the opponent earned 18-21K from
melon to our 9-13K (2026-09-22). Melon yield rises by one per WATER between
ages 6 and 12; our plot rule cuts before it waters, so the first wave comes
off at five units a tile on day 10 while the opponent waters first and cuts
six. Water-first alone loses: at yield six a worker fills its carry of six
on one tile instead of two, halves its harvests, and the tiles it never
reaches die after two dry days. With the carry raised to eighteen (the sim
has no per-worker cap; six is the benchmark's own constant) two scratch seed
sets read 13/16 (+2.0K) and 12/16 (+1.0K); the carry alone is a null.

Two hooks change: `carry_limit` returns CARRY and `water_first` returns
True, through the seams field_rival gained for them. Everything else is
town_melon's.

Declared before measurement: CARRY, and the controls and criterion in
`harness/sixmelon_bench.py` (posted to #341 before any code).
"""

from __future__ import annotations

from strategies.town_melon import TownMelonStrategy

#: Units a crop worker carries before it banks: three full melons.
CARRY = 18


class SixMelonStrategy(TownMelonStrategy):
    """`town_melon` that waters a ready melon before cutting it and carries eighteen."""

    name = "six_melon"
    benchmark = False

    def carry_limit(self):
        """The declared carry (#341)."""
        return CARRY

    def water_first(self):
        """Water a ready melon before cutting it (#341)."""
        return True


STRATEGY = SixMelonStrategy
