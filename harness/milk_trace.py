"""#228: why the MILK market collapsed on seed 601 and held on seed 600.

    python -m harness.milk_trace --seeds 600 601 --us rival_aware --them meta_bot
    python -m harness.milk_trace --seeds 600 601 602 603 604 605 606 607
    python -m harness.milk_trace --counterfactuals

A **measurement**, not an experiment: no strategy is added, no bar is declared,
nothing here can be promoted. #225 recorded realised milk at 152% of base on
seed 600 and 34% (late window 2.9% -- the $1 floor) on seed 601, against the
same rival, for the same agent. This module drives those games turn by turn and
reads, off both seats at once, what the season-long summary cannot show: who
put how many units of milk into the market and on which day, what the price did
in response, and how the two farms' combined volume compares with what the town
actually draws.

**The town's draw is not a constant.** `rival_aware`'s own docstring says milk
"has three shops and 570 season demand". Milk is in three of the eight shop
*types*, but the town unlocks eight shop *instances* by drawing from those eight
types **with replacement** (`_end_of_day` in the sim), so how many milk shops a
town ends up with is a property of the seed. 570 is what a town with three
milk shops standing all season would draw; `town_draw` below computes the real
figure from the shop list the game actually unlocked, per seed.

The positive control is the first thing the CLI prints: the per-turn
reconstruction's cumulative milk units and revenue for our seat must reconcile
to `episode_analysis.price_realisation` on the same episode. The trace is built
from the live drive (our own step loop, reading each seat's observation before
it acts) while `price_realisation` re-reads `env.steps` afterwards and pairs
each action with the *previous* index's observation -- two different walks over
the same season, so an off-by-one in either shows up as a mismatch rather than
as a plausible-looking table.
"""

from __future__ import annotations

import argparse
import os

from kaggisim import economy
from kaggisim.economy import SHOP_DEMAND, base_price

#: Turns between consumption ticks by every unlocked shop instance, and by the
#: town centre. Both are the *sim's* defaults (`townShopSellInterval` 4,
#: `townCenterSellInterval` 24), pinned against the installed environment's own
#: configuration schema by `tests/test_milk_trace.py` -- not read from
#: `economy.CONFIG_DEFAULTS`, whose `townCenterSellInterval` says 12 where the
#: sim says 24. That transcription gap is reported on #228, not patched here:
#: this module is a measurement and correcting a shared table would change what
#: every other bench computes.
SHOP_SELL_INTERVAL = 4
TOWN_CENTER_INTERVAL = 24

#: Every product the town centre buys one of per tick: the sim's
#: TOWN_CENTER_PRODUCTS is "every product except fertilizer".
NO_TOWN_CENTRE = ("FERTILIZER",)


def town_draw(shops, step, item):
    """Units of `item` the town removes from market inventory leaving `step`.

    The sim's `_town_consume`, applied to the shop list a turn actually
    observed: on a shop tick every unlocked instance pulls one of each of its
    products (two, if that shop sells only one thing), and on a town-centre
    tick the centre pulls one more of everything but fertilizer. Shops are
    drawn with replacement, so a name appearing twice consumes twice.

    Unconditional in the sim -- inventory is decremented whether or not there
    is stock to take -- so this is the exact draw, not an upper bound.
    """
    drawn = 0
    if step % SHOP_SELL_INTERVAL == 0:
        for shop in shops or []:
            products = SHOP_DEMAND.get(shop) or []
            if item in products:
                drawn += 2 if len(products) == 1 else 1
    if step % TOWN_CENTER_INTERVAL == 0 and item not in NO_TOWN_CENTRE:
        drawn += 1
    return drawn


#: The product this module is about. Named once so the base price, the shop
#: table lookup and the trace's own keys can never drift apart.
ITEM = "MILK"


def cumulative_by_day(trace, key):
    """`key` summed over every turn up to and including each day of the trace.

    A day that sold nothing still gets an entry, holding the running total: a
    gap in the curve would read as "not measured" where the honest reading is
    "sold none that day", and the whole point of the curve is to say *when* the
    units went in.
    """
    out: dict = {}
    total = 0.0
    for row in trace:
        total += row.get(key) or 0
        out[row["day"]] = total
    return out


def first_day_below(trace, frac_of_base):
    """The first day the milk quote sat below `frac_of_base` x its base price.

    First break wins even if the price later recovers -- this answers "when did
    the market leave the band", not "is it still out of it now". ``None`` when
    it never left.
    """
    threshold = frac_of_base * base_price(ITEM)
    for row in trace:
        price = row.get("milk_price")
        if price is not None and price < threshold:
            return row["day"]
    return None


def revenue_at(units_by_turn, prices_by_turn):
    """What `{step: units}` fetches at `{step: quote}`, aligned by step.

    The turn's opening quote, not the per-unit walk down the curve: this is the
    like-for-like instrument the counterfactual needs, and it is used on both
    sides of that comparison so the difference between them is the price path
    and nothing else. The realised, curve-walked revenue is a separate number
    and is the one the positive control reconciles.

    A step that sold units but carries no quote is refused rather than priced at
    zero: silently dropping it would show up as exactly the collapse this
    module is trying to measure.
    """
    total = 0.0
    for step, units in units_by_turn.items():
        if not units:
            continue
        price = prices_by_turn.get(step)
        if price is None:
            raise ValueError(f"step {step} sold {units} units with no quote in the "
                             f"price path it is being aligned against")
        total += units * price
    return total


def revenue_if(units_by_turn, other_prices_by_turn):
    """The counterfactual: our units, another game's price path, step by step.

    Deliberately `revenue_at`'s own walk rather than a second implementation --
    "what they fetched" and "what they would have fetched" have to be the same
    arithmetic or their difference is not a cost.
    """
    return revenue_at(units_by_turn, other_prices_by_turn)


def draw_ratio(total_units, season_demand):
    """Both farms' season volume as a multiple of what the town draws.

    #146's reading: what puts a market on the floor is not how much we sell, it
    is how much we sell against the town's appetite for it. A season demand of
    zero is refused -- with no draw there is no ratio, and reporting 0.0 would
    read as "no pressure" where the truth is "no measurement".
    """
    if season_demand <= 0:
        raise ValueError(f"season demand {season_demand} is not a draw to compare against")
    return total_units / season_demand


def count_cows(tiles):
    """Cows standing on a farm's public tiles.

    A locked tile is the string "LOCKED" and a weed is a dict with no "animal"
    key; both count zero, the same shape `field_rival.rival_sheep` reads.
    """
    return sum(1 for row in tiles or [] for t in row
               if isinstance(t, dict) and t.get("animal") == "COW")


def reconciliation(trace, analysis, item=ITEM):
    """The positive control: does the per-turn trace sum to the season summary?

    `trace` is built by the live drive, which pairs each action with the
    observation the agent was handed before acting; `analysis` is
    `episode_analysis.price_realisation`, which re-reads `env.steps` afterwards
    and pairs each action with the *previous* index's observation. Two walks,
    one season -- an off-by-one in either lands here as a gap.

    `precondition_ok` is reported separately and gates `ok`: a season that sold
    no milk reconciles 0 against 0 without proving anything, and a vacuous
    match must not read as a passed control.
    """
    trace_units = sum(row.get("our_milk_sold") or 0 for row in trace)
    trace_revenue = sum(row.get("our_milk_revenue") or 0 for row in trace)
    summary = (analysis.get("items") or {}).get(item) or {}
    season_units = summary.get("units", 0)
    season_revenue = summary.get("revenue", 0)
    precondition_ok = season_units > 0 and trace_units > 0
    return {
        "ok": (precondition_ok and trace_units == season_units
               and trace_revenue == season_revenue),
        "precondition_ok": precondition_ok,
        "trace_units": trace_units, "season_units": season_units,
        "trace_revenue": trace_revenue, "season_revenue": season_revenue,
        "units_gap": abs(trace_units - season_units),
        "revenue_gap": abs(trace_revenue - season_revenue),
    }
