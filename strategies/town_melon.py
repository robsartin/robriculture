"""town_melon: second_melon with melon instead of strawberry from day 9 while
the town has no shop that takes strawberry (#337).

Five of fert_sixteen's fourteen ladder losses, and none of its wins, were
towns with no strawberry shop by day 12: we held a full strawberry field the
town never bought while the opponent sold melon (#288, 2026-09-21). Shops
unlock on days 3, 6, 9, ... from eight kinds, four of which take strawberry;
12% of ladder towns have none at day 9. Scratch probes on seeds screened for
such towns read 16/16 (+11.9K) and 15/16 (+11.3K); a day-12 decision is a
null (the field is already full), a day-6 one loses on false positives.

One hook changes: `crop_plan` returns the dead-town caps and window from
`DEAD_DAY` while no unlocked shop lists STRAWBERRY, and ``None`` otherwise --
it reverts the turn a strawberry shop unlocks. The caps stop new strawberry
and let melon take the tiles the field frees, through day `LAST_MELON_DAY`,
the last day a melon can still finish. Everything else is second_melon's.

Declared before measurement: the constants below, and the screen, controls
and criterion in `harness/deadtown_bench.py` (posted to #337 before any code).
"""

from __future__ import annotations

from kaggisim import economy
from strategies.free_straw import CAPS_S
from strategies.second_melon import SecondMelonStrategy

#: The first day the rule can fire: three shops are known.
DEAD_DAY = 9

#: The last day a melon can still finish (`hired_hands.plantable`: first
#: yield on day 10 after planting, one day to sell, season of 30).
LAST_MELON_DAY = 18

DEAD_WINDOWS = ((DEAD_DAY, LAST_MELON_DAY),)

#: The dead-town caps: melon takes what the field frees, no new strawberry.
DEAD_CAPS = {**CAPS_S, "MELON": 24, "STRAWBERRY": 0}

#: The shop kinds that take strawberry, from the sim's own table.
STRAW_SHOPS = frozenset(name for name, products in economy.SHOP_DEMAND.items() if "STRAWBERRY" in products)


def straw_dead(shops) -> bool:
    """True when no unlocked shop takes strawberry."""
    return not any(shop in STRAW_SHOPS for shop in shops or ())


class TownMelonStrategy(SecondMelonStrategy):
    """`second_melon` with melon instead of strawberry from day 9 in a town
    with no strawberry shop."""

    name = "town_melon"
    benchmark = False

    def crop_plan(self, obs):
        """The dead-town caps and window from `DEAD_DAY` while the town has no
        strawberry shop; the frozen plan otherwise (#337)."""
        shops = (obs.get("town") or {}).get("unlocked_shops") or []
        if obs.get("day", 0) >= DEAD_DAY and straw_dead(shops):
            return DEAD_CAPS, DEAD_WINDOWS
        return None


STRATEGY = TownMelonStrategy
