"""town_herd: four_at_eight with the animal kind chosen from the town's shops (#302).

#288 decomposed four_at_eight's 30 rated ladder games: the losses are not
escapes and the herd ramp is the same every game; revenue from the same board
runs 24K-110K because the market price is set by inventory and only the
town's shops drain it. The milk-shop count predicts our MILK revenue at
r = 0.78, the yarn-store count our WOOL at 0.77. The herd was bought blind.

One decision changes: the kind of the next animal. `herd_preference` reads
`obs["town"]["unlocked_shops"]`, works out from the sim's own tables how many
head of each kind the town clears each day, subtracts the head we own, and
asks for the kind with the most room. When the town supports neither (no
milk or yarn shop yet) the inherited rule runs. Everything else is
four_at_eight's.

Declared before measurement: the rule, and the controls and criterion in
`harness/town_bench.py` (posted to #302 before any code).
"""

from __future__ import annotations

from kaggisim import economy
from strategies.four_at_eight import FourAtEightStrategy

#: Consumption ticks a shop instance gets per day (the sim's `_town_consume`:
#: one unit of each listed product every `townShopSellInterval` turns).
SHOP_TICKS_PER_DAY = economy.CONFIG_DEFAULTS["turnsPerDay"] // economy.CONFIG_DEFAULTS["townShopSellInterval"]

#: The kinds the seam chooses between.
KINDS = ("COW", "SHEEP")


def shop_drain(shops, product) -> int:
    """Units of `product` the unlocked shops take per day: one per tick per
    instance listing it, doubled for a single-product shop (the sim's
    multiplier). An unknown shop name counts nothing."""
    total = 0
    for name in shops or ():
        products = economy.SHOP_DEMAND.get(name) or ()
        if product in products:
            total += SHOP_TICKS_PER_DAY * (2 if len(products) == 1 else 1)
    return total


def head_supported(shops, kind) -> int:
    """Head of `kind` whose output the town clears each day: its product's
    drain over one head's daily yield (one unit every `interval` days)."""
    animal = economy.ANIMALS[kind]
    return shop_drain(shops, animal["product"]) * animal["interval"]


def our_head(tiles, shed, kind) -> int:
    """Placed head of `kind` on our tiles plus the shed's pending ones. Counting
    the pending ones is what stops the ramp's per-turn loop from ordering the
    same kind again every turn (the sheep_first lesson, #268)."""
    placed = sum(1 for row in (tiles or []) for t in row
                 if isinstance(t, dict) and t.get("animal") == kind)
    return placed + int((shed or {}).get(kind, 0) or 0)


def town_kind(shops, cows, sheep):
    """The kind with the most unfilled room -- head the town supports less
    head owned -- or ``None`` when the town supports neither. COW on a tie:
    it is the cheaper animal."""
    supported = {k: head_supported(shops, k) for k in KINDS}
    if not any(supported.values()):
        return None
    room = {"COW": supported["COW"] - cows, "SHEEP": supported["SHEEP"] - sheep}
    return "SHEEP" if room["SHEEP"] > room["COW"] else "COW"


class TownHerdStrategy(FourAtEightStrategy):
    """`four_at_eight` with the next animal's kind read from the town."""

    name = "town_herd"
    benchmark = False

    def owned(self, obs):
        """(cows, sheep) we have placed or pending. Arm B overrides this to (0, 0)."""
        me = obs["farms"][obs["player"]]
        shed = (obs.get("private") or {}).get("shed") or {}
        tiles = me.get("tiles")
        return our_head(tiles, shed, "COW"), our_head(tiles, shed, "SHEEP")

    def herd_preference(self, obs):
        """`town_kind` on the town's shops and our head; the inherited rule when
        the town supports neither kind or the observation is malformed (ADR-0006)."""
        try:
            shops = (obs.get("town") or {}).get("unlocked_shops") or []
            cows, sheep = self.owned(obs)
            kind = town_kind(shops, cows, sheep)
        except (LookupError, TypeError, AttributeError):
            kind = None
        return kind if kind is not None else super().herd_preference(obs)


STRATEGY = TownHerdStrategy
