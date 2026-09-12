"""fed_herd: lean_feed with two feedings in the shed (#270).

Re-reading #266's 47 ladder replays for head placed by day: lean_feed's
animals escape in 24 of 47 games, first on day 9 in most, and we are 0/11
when three or more head go. On seeds 992/993 third_herder loses no head,
herd_first one, lean_feed three and seven. #262 cut the shed's feed stock to
one feeding; on days 7-11 dawn cash is about thirty, so a single top-up that
cannot be bought leaves the herd unfed, and a second day takes it
(`consecutive_unfed >= 2`).

One decision changes: the shed keeps two feedings. The sell sweep holds back
two days of harvested wheat instead of one and the feed block tops up to it;
the lean carry and everything else are lean_feed's. It costs cash only when
the shed is short.

Declared before measurement: `FEEDINGS`, and the controls and criterion in
`harness/fed_bench.py` (posted to #270 before any code).
"""

from __future__ import annotations

from strategies.lean_feed import LeanFeedStrategy

#: Feedings the shed keeps for the herd standing today.
FEEDINGS = 2


def stock_for_fed(animals: int) -> int:
    """Wheat the shed keeps: `FEEDINGS` days for the herd, never zero."""
    return max(1, FEEDINGS * animals)


class FedHerdStrategy(LeanFeedStrategy):
    """`lean_feed` with two feedings in the shed."""

    name = "fed_herd"
    benchmark = False

    def feed_stock(self, animals=None):
        return stock_for_fed(animals or 0)


STRATEGY = FedHerdStrategy
