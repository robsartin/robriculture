"""town_split: four_at_eight with the herd split in proportion to the town's
drain (#305).

#302's switch (`town_herd`) went to eleven sheep and one cow in every
yarn-store town: it won by 26-33K where no milk shop competed and lost by
7-11K where one did, the milk line thrown away and eleven sheep halving their
own price per head. The sign was right and the dose was wrong.

One decision changes: the kind of the next animal. `herd_preference` sets the
herd's sheep share from the town's wool drain over its wool and milk drain
together (`town_herd.shop_drain`, from the sim's own tables) and asks for a
sheep while the sheep are short of that share of the herd including the next
head. A yarn store alone means every head a sheep; a milk shop alone every
head a cow; a yarn store beside a pizza shop eight sheep to four cows at
twelve head. When the town takes neither, the inherited rule runs. The
frozen rule's day-0 herd (three sheep, one cow, before the first shop) is
untouched; everything else is four_at_eight's.

Declared before measurement: the rule, and the controls and criterion in
`harness/split_bench.py` (posted to #305 before any code), judged under
ADR-0007's amendment of 2026-09-16.
"""

from __future__ import annotations

from strategies.four_at_eight import FourAtEightStrategy
from strategies.town_herd import our_head, shop_drain


def sheep_share(shops):
    """The share of the herd that should be sheep: the town's wool drain over
    its wool and milk drain together, or ``None`` when it takes neither."""
    wool, milk = shop_drain(shops, "WOOL"), shop_drain(shops, "MILK")
    if wool + milk == 0:
        return None
    return wool / (wool + milk)


def split_kind(share, cows, sheep):
    """The next head: SHEEP while the sheep are short of `share` of the herd
    that includes it, else COW."""
    return "SHEEP" if sheep < share * (cows + sheep + 1) else "COW"


class TownSplitStrategy(FourAtEightStrategy):
    """`four_at_eight` with the herd split by the town's drain."""

    name = "town_split"
    benchmark = False

    def sheep_share(self, shops):
        """The module's `sheep_share`; arm B overrides it with an even split."""
        return sheep_share(shops)

    def owned(self, obs):
        """(cows, sheep) we have placed or pending."""
        me = obs["farms"][obs["player"]]
        shed = (obs.get("private") or {}).get("shed") or {}
        tiles = me.get("tiles")
        return our_head(tiles, shed, "COW"), our_head(tiles, shed, "SHEEP")

    def herd_preference(self, obs):
        """`split_kind` at the town's share and our head; the inherited rule
        when the town takes neither product or the observation is malformed
        (ADR-0006)."""
        try:
            shops = (obs.get("town") or {}).get("unlocked_shops") or []
            share = self.sheep_share(shops)
            kind = None if share is None else split_kind(share, *self.owned(obs))
        except (LookupError, TypeError, AttributeError):
            kind = None
        return kind if kind is not None else super().herd_preference(obs)


STRATEGY = TownSplitStrategy
