"""Run both businesses: the champion's crop line plus the herd it turned off.

Experiment for issue #187, ADR-0007.

#157 decomposed 63 real ladder matches, both sides, and found the winning field
draws **62% of its revenue from livestock and fertilizer** while we draw none:

    revenue, medians          crops    livestock + fert    total
    us (neuropilot)          55,958                   0   59,667
    opponents who beat us    28,361              60,154   96,002

Our crop line is the strongest in that data -- nearly double the field's. We
lose because we run one business where the field runs two.

The champion is not missing the machinery. `neuropilot` already implements the
entire livestock line: pastures, cows, sheep, feeding, harvesting and the free
`COLLECT_FERTILIZER` byproduct, all driven by its `herd_target_scale` knob. Its
evolved genome sets that knob to a median **0.0098**, and `_herd_targets` rounds
`0.0098 * 13` to **zero animals** for the whole game. Evolution switched the
second business off, and nineteen experiments then searched everywhere except
the switch.

So the single variable is that knob, floored to the herd the field actually
keeps. Everything else is the champion's, untouched and byte-identical: the same
genome, the same network, every other knob, the whole crop line and controller.
"""

from __future__ import annotations

from strategies import neuropilot as npx

#: Animals the measured field holds from day 16 on (#157 median). The full comp
#: `neuropilot` can express is 13 -- N_COW 9 plus N_SHEEP 4 -- so this asks for
#: nine cows and two sheep, cows first, exactly as `_herd_targets` fills them.
TARGET_HERD = 11

#: The smallest `herd_target_scale` that rounds to TARGET_HERD animals. Derived
#: from the champion's own constants rather than written as a decimal, so it
#: cannot drift if the comp size changes.
HERD_FLOOR = TARGET_HERD / (npx.N_COW + npx.N_SHEEP)

#: The second half of the switch, and the reason the first half alone does
#: nothing. `herd_target_scale` buys the herd; `livestock_labor_share` decides
#: whether any worker is ever assigned to tend it. An animal job is worth
#: `ANIMAL_JOB_SCALE * livestock_labor_share` against a crop job's
#: `CROP_JOB_VALUE`, so at the champion's 0.1063 an animal job scores 0.213
#: against 1.0 and, at `TRAVEL_COST` 0.05, could only win if the nearest crop
#: job were ~16 tiles further away -- impossible on a 10x10 board.
#:
#: Raising only the herd target therefore buys 11 animals that are never placed:
#: measured, 9 cows and 2 sheep sat in the shed from day 12, hit the 100-item cap
#: alongside the melon, and silently discarded every later harvest. Final money
#: 45,945 -> 1,050.
#:
#: Parity is not enough, and that is measurable. `candidate_jobs` sorts ties by
#: position and `assign_workers` keeps the first on a tie, so at exactly equal
#: value the low-coordinate crop tiles take every tie and the herd is never
#: tended: at parity this agent issued 13 FEED actions in a whole season, where
#: `field_rival` issues 153.
#:
#: So an animal job is floored ABOVE a crop job, which is also what the game
#: says: an unfed animal escapes permanently, losing its whole 400-500 purchase,
#: while an unwatered plant survives a day and is worth ~100 when it does die.
#: At 1.5x, an animal job outranks any crop job within 10 tiles of the worker.
ANIMAL_JOB_PREMIUM = 1.5
LABOUR_FLOOR = ANIMAL_JOB_PREMIUM * npx.CROP_JOB_VALUE / npx.ANIMAL_JOB_SCALE


def floor_herd(knobs):
    """The champion's knobs with the livestock business switched back on.

    Floors, not pins: where the network already asks for more herd or more herd
    labour it keeps authority and the knobs are returned untouched. Both knobs
    move together because they are entangled -- one without the other cannot
    fire, as the constants above record.

    Every non-livestock knob is passed through unchanged. The crop line is the
    control in this experiment (#187).
    """
    if (knobs.herd_target_scale >= HERD_FLOOR
            and knobs.livestock_labor_share >= LABOUR_FLOOR):
        return knobs
    return knobs._replace(
        herd_target_scale=max(knobs.herd_target_scale, HERD_FLOOR),
        livestock_labor_share=max(knobs.livestock_labor_share, LABOUR_FLOOR),
    )


#: The sim accepts this many market orders per turn; feed is appended only into
#: slots the champion's own controller left free, so it can never displace a sell.
MAX_ORDERS = npx.economy.CONFIG_DEFAULTS["maxMarketOrdersPerTurn"]

#: Wheat held per animal. Each FEED spends one wheat and an animal escapes at
#: `consecutive_unfed >= 2`, so two per head covers a feeding plus the trip back.
FEED_PER_ANIMAL = 2


def _placed_animals(state) -> int:
    me = state["farms"][state.get("player", 0)]
    return sum(1 for row in me["tiles"] for t in row
               if isinstance(t, dict) and t.get("animal"))


def feed_target(animals: int) -> int:
    """Wheat the shed should hold for a herd of `animals`."""
    return FEED_PER_ANIMAL * animals


def feed_orders(state, action) -> list:
    """A `BUY_PRODUCT WHEAT` order when the herd is short of feed.

    The champion's only `BUY_PRODUCT` is FERTILIZER -- it never buys wheat. FEED
    spends wheat from a worker's own inventory, taken from the shed, so unless
    `crop_mix` happens to select wheat the herd simply starves: measured, cows
    cycled buy -> place -> starve -> escape -> re-buy at 400 a head and
    livestock revenue never left zero.

    Appended only into slots the controller left free, so feed can never
    displace a sell.
    """
    animals = _placed_animals(state)
    if not animals:
        return []
    room = MAX_ORDERS - len(action.get("market") or [])
    if room <= 0:
        return []
    shed = (state.get("private") or {}).get("shed") or {}
    short = feed_target(animals) - int(shed.get("WHEAT", 0))
    if short <= 0:
        return []
    money = state["farms"][state.get("player", 0)].get("money", 0)
    price = max(1, int((state.get("market") or {}).get("prices", {}).get("WHEAT", 25)))
    buy = min(short, int(money // price))
    # Length three is not optional: the sim's `_parse_order` discards a shorter
    # order without a word, which reads exactly like being unable to afford it.
    return [["BUY_PRODUCT", "WHEAT", buy]] if buy > 0 else []


def keep_feed(state, orders) -> list:
    """Trim any `SELL WHEAT` down to the feed buffer.

    The champion's `_sell_orders` liquidates every sellable item in the shed,
    wheat included. Buying feed and dumping it in the same turn would churn
    money into the spread every turn -- the defect `field_rival` had (#181).
    """
    animals = _placed_animals(state)
    if not animals:
        return orders
    keep = feed_target(animals)
    shed = (state.get("private") or {}).get("shed") or {}
    have = int(shed.get("WHEAT", 0))
    out = []
    for order in orders:
        if isinstance(order, list) and order[:2] == ["SELL", "WHEAT"]:
            sellable = max(0, have - keep)
            trimmed = min(int(order[2]), sellable)
            if trimmed > 0:
                out.append(["SELL", "WHEAT", trimmed])
            continue
        out.append(order)
    return out


class DualIncomeStrategy(npx.NeuroPilotStrategy):
    """`neuropilot`, with its switched-off herd switched back on."""

    name = "dual_income"
    benchmark = False

    def act(self, state) -> dict:
        knobs = floor_herd(npx.decode_knobs(self.mlp.forward(npx.features(state))))
        action = npx.controller(knobs, state)
        market = keep_feed(state, action.get("market") or [])
        action["market"] = (market + feed_orders(state, {"market": market}))[:MAX_ORDERS]
        return action


STRATEGY = DualIncomeStrategy
