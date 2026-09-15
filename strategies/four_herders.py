"""four_herders: ten_melon with a fourth herder from day 12 (#289).

#288 mined 102 rated games: opponents with twelve head by day 8 beat us 11
of 12, and our own herd ends every game at eleven placed with four animals
standing in the shed from day 12 on. payday_herd's ramp asks thirteen; the
herd block counts shed animals as pending and stops buying; the three
herders are saturated at eleven head and the per-herder scan never reaches
the tiles at the back of the block. A fourth herder from day 12 placed a
twelfth head and won 8/8 probe games, milk 171-177 -> 204-210.

One decision changes: from FOURTH_DAY, worker FOURTH_HERDER herds too (the
`livestock_workers` seam). It gives up its crop cluster, as third_herder's
did. Everything else is ten_melon's.

Declared before measurement: FOURTH_HERDER and FOURTH_DAY, and the controls
and criterion in `harness/fourth_bench.py` (posted to #289 before any code).
"""

from __future__ import annotations

from strategies import field_rival as fr
from strategies.ten_melon import TenMelonStrategy

#: The worker that joins the livestock line, and the day it does.
FOURTH_HERDER = 7
FOURTH_DAY = 12


class FourHerdersStrategy(TenMelonStrategy):
    """`ten_melon` with a fourth herder from day twelve."""

    name = "four_herders"
    benchmark = False
    FOURTH_HERDER = FOURTH_HERDER
    FOURTH_DAY = FOURTH_DAY

    def livestock_workers(self, day):
        """The parent's answer -- None before day 8, the trio from 8 -- with
        the fourth worker appended from FOURTH_DAY."""
        base = super().livestock_workers(day)
        if day < self.FOURTH_DAY:
            return base
        return tuple(base or fr.LIVESTOCK_WORKERS) + (self.FOURTH_HERDER,)


STRATEGY = FourHerdersStrategy
