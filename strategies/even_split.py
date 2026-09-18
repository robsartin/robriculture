"""even_split: town_split with an even herd whenever the town takes both
wool and milk (#310).

#305's recorded arm B -- exactly this rule -- went 16/16 decided against
four_at_eight where the proportional split went 13/16. The proportional
split's three losses were the towns where a yarn store sat among two or
three milk shops and its weight still tipped the herd to nine sheep; the
yarn store's double drain does not translate into double revenue once nine
sheep sit on it.

One method changes: the share. A half whenever the town drains both
products, all sheep when only wool, all cows when only milk, the inherited
rule when neither. `split_kind`, `owned` and `herd_preference` are
town_split's; the frozen day-0 herd is untouched.

Declared before measurement: the rule, and the controls and criterion in
`harness/even_bench.py` (posted to #310 before any code), judged under
ADR-0007's amendment of 2026-09-16 as corrected 2026-09-17.
"""

from __future__ import annotations

from strategies.town_herd import shop_drain
from strategies.town_split import TownSplitStrategy


def even_share(shops):
    """A half whenever the town takes both wool and milk; one when only wool,
    zero when only milk, ``None`` when neither."""
    wool, milk = shop_drain(shops, "WOOL"), shop_drain(shops, "MILK")
    if wool + milk == 0:
        return None
    if milk == 0:
        return 1.0
    if wool == 0:
        return 0.0
    return 0.5


class EvenSplitStrategy(TownSplitStrategy):
    """`town_split` at a half share whenever the town takes both."""

    name = "even_split"
    benchmark = False

    def sheep_share(self, shops):
        """The module's `even_share`; arm B overrides it with `half_share`."""
        return even_share(shops)


STRATEGY = EvenSplitStrategy
