"""ten_melon: payday_herd with the melon cap at ten (#279).

On days 0-5 the farm owns eleven crop tiles and two crop workers have land;
the eleventh melon is the one nobody waters -- 36-40 units from eleven tiles,
3.3 a tile -- and its seed is the last 80 of day 0's cash. Probes against
payday_herd: cap 10 wins 2/2 with 45 melon from ten tiles, 29 tiles planted
by day 8 and the 80 left in the cash-starved days; smaller clusters lose (they
shrink the day-16 line); fewer early hands 1/2.

One number changes: `CAPS["MELON"]` is 10, not 12. A class attribute that
`act` reads; no method is overridden and everything else is payday_herd's.

Declared before measurement: `CAPS_T`, and the controls and criterion in
`harness/melon_bench.py` (posted to #279 before any code).
"""

from __future__ import annotations

from strategies.payday_herd import PaydayHerdStrategy

#: field_pace's caps with melon at ten.
CAPS_T = {"MELON": 10, "STRAWBERRY": 38, "WHEAT": 24}


class TenMelonStrategy(PaydayHerdStrategy):
    """`payday_herd` with ten melon tiles."""

    name = "ten_melon"
    benchmark = False
    CAPS = CAPS_T


STRATEGY = TenMelonStrategy
