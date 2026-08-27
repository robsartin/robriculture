"""The market's revenue ceiling as a linear program (#136).

Every experiment in this repo measures an agent against *other agents* — pool
share, win-rate against anchors. That answers "are we better than us", never
"how much of this game is there to win". This gives a denominator that does not
move: the town's own demand.

**What the game is, in OR terms.** It is a Production Routing Problem — three
studied pieces bolted together:

* **capacitated lot-sizing** — which crop on which tile, when, under a capital
  constraint;
* **periodic vehicle routing with time windows** — every planted tile needs a
  visit every 2 days or the sim turns it into a WEED, and workers are the
  vehicles. This is the NP-hard core, and why travel eats 42-55% of worker-turns
  (#132);
* **revenue management with price impact** — selling walks the price down its
  own curve while the town replenishes demand on a fixed schedule.

All of it wrapped in Cournot competition, because `state[i].observation.market`
is *the same object* for both players: our sales move the price our opponent
faces. That makes optimal play an equilibrium problem rather than an
optimisation, so this module deliberately solves a **relaxation**, not the game.

**The relaxation.** Drop routing to a measured travel fraction, drop the
opponent, drop time, and ask a steady-state question: what mix of crops and
livestock maximises season revenue subject to labour, land, and demand? That is
a small LP, solved exactly in milliseconds.

**Read the answer as a floor, not a ceiling.** Every unit is priced at `base`,
and `base` is what the market pays at its resting inventory `I0`. The town
drains inventory every 4 and 12 turns, and a drained market pays a *premium* —
measured at 2.1x base for WHEAT, 2.0x STRAWBERRY, 1.9x MILK. `pilkwang` banks
168,915 against this model's 120,396, and that 40% gap is the premium it earns
by selling into scarcity. Timing is a lever this model cannot see and our agent
does not use.

What it does tell us, and did not cost a 14-hour run to learn:

* **land binds, labour does not** — the optimum uses all 87 non-animal tiles at
  ~54% of worker capacity, independently confirming the ~39% idle measured in
  #132, and saying more hands would not help;
* **melon caps at ~12 tiles on demand alone** — the town buys 140 melons a
  season, both players combined, which is the smallest segment on the board;
* **the optimum wants livestock at full capacity**, even though #121 measured a
  herd as a net loss *for our controller*.

Usage::

    python -m harness.ceiling_lp
    python -m harness.ceiling_lp --workers 10 --travel 0.45
"""
from __future__ import annotations

import argparse
import collections
import math
import sys

import kaggle_environments.envs.kaggriculture.kaggriculture as sim

from kaggisim import economy

SEASON_DAYS = 30
TURNS_PER_DAY = 24
TURNS = SEASON_DAYS * TURNS_PER_DAY
SHOP_INTERVAL = 4
CENTER_INTERVAL = 12

#: Non-animal tiles on a fully-bought 10x10 board (100 less the 13 animal tiles).
CROP_TILES = 87
#: Animal structure tiles in the reachable layout (9 cow + 4 sheep).
ANIMAL_TILES = 13

CROPS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON")
ANIMALS = ("COW", "SHEEP", "GOOSE")


def town_demand(turns: int = TURNS) -> dict:
    """Units of each product the town will absorb over `turns`.

    The town is the *only* thing removing market inventory, so this bounds what
    either player can sell all season. Shops consume every `SHOP_INTERVAL`
    turns (doubled for single-product shops); the town centre consumes every
    `CENTER_INTERVAL` turns at a multiplier that steps up by day band.

    Assumes every shop unlocked. They unlock progressively, so early-season
    demand is lower and this is an upper bound on the schedule.
    """
    demand: dict = collections.Counter()
    for step in range(0, turns, CENTER_INTERVAL):
        day = step // TURNS_PER_DAY
        mult = next(m for threshold, m in sim.TOWN_CENTER_DEMAND_SCHEDULE if day >= threshold)
        for item in sim.TOWN_CENTER_PRODUCTS:
            demand[item] += mult
    for step in range(0, turns, SHOP_INTERVAL):
        for products in sim.SHOPS.values():
            mult = 2 if len(products) == 1 else 1
            for item in products:
                demand[item] += mult
    return dict(demand)


def crop_activity(crop: str, season: int = SEASON_DAYS) -> tuple:
    """`(units, worker_actions)` one tile of `crop` yields over a season.

    Actions are the survival watering (one every two days, since two unwatered
    days kill the plant), plus a harvest per yield event and a plant per cycle.
    Travel is excluded here and charged once, globally, as a fraction of worker
    capacity.
    """
    cd = economy.CROPS[crop]
    first, interval = cd["first"], cd.get("interval", 0)
    ongoing, max_yield = cd.get("ongoing", False), cd["max_yield"]
    life = (first + interval * (max_yield - 1) + 1) if (ongoing and interval > 0) else cd["max_day"] + 1
    cycles = max(1, season // life)
    harvests = (max_yield if ongoing else 1) * cycles
    waters = math.ceil(season / 2)
    return max_yield * cycles, waters + harvests + cycles


def animal_activity(kind: str, season: int = SEASON_DAYS) -> tuple:
    """`(units, worker_actions, product)` one animal yields over a season.

    Fed daily -- an animal escapes after two unfed days -- plus one collection
    per yield event and two setup actions (build the pasture, place the animal).
    """
    spec = economy.ANIMALS[kind]
    first, interval = spec["first"], spec["interval"]
    yields = max(0, (season - first) // interval + 1)
    return yields, season + yields + 2, spec["product"]


def build_program(workers: int, travel_fraction: float, season: int = SEASON_DAYS):
    """Assemble the LP as `(activities, objective, A_ub, b_ub)`, all plain lists.

    Separated from the solve so the formulation is testable without scipy: the
    arithmetic that decides the answer is worth pinning independently of the
    solver that reports it.
    """
    demand = town_demand(int(season * TURNS_PER_DAY))
    units, actions, product = {}, {}, {}
    for crop in CROPS:
        units[crop], actions[crop] = crop_activity(crop, season)
        product[crop] = crop
    for animal in ANIMALS:
        units[animal], actions[animal], product[animal] = animal_activity(animal, season)

    activities = list(CROPS) + list(ANIMALS)
    # linprog minimises, so negate to maximise revenue.
    objective = [-units[a] * (economy.base_price(product[a]) or 0) for a in activities]

    A_ub, b_ub = [], []
    A_ub.append([actions[a] for a in activities])
    b_ub.append(workers * season * TURNS_PER_DAY * (1.0 - travel_fraction))
    A_ub.append([1.0 if a in CROPS else 0.0 for a in activities])
    b_ub.append(CROP_TILES)
    A_ub.append([0.0 if a in CROPS else 1.0 for a in activities])
    b_ub.append(ANIMAL_TILES)
    for item in sorted(set(product.values())):
        A_ub.append([units[a] if product[a] == item else 0.0 for a in activities])
        b_ub.append(demand.get(item, 0))
    # Wheat is dual-use: an animal eats one per day, so that wheat cannot be sold.
    A_ub.append([(-units["WHEAT"] if a == "WHEAT" else (season if a in ANIMALS else 0.0))
                 for a in activities])
    b_ub.append(0.0)
    return activities, objective, A_ub, b_ub, units, product


def solve(workers: int = 10, travel_fraction: float = 0.45, season: int = SEASON_DAYS):
    """Solve the relaxation. Requires scipy; raises ImportError with a hint if absent."""
    try:
        from scipy.optimize import linprog
    except ImportError as exc:  # pragma: no cover - environment guard
        raise ImportError(
            "harness.ceiling_lp needs scipy (pinned in requirements.txt); "
            "run `pip install -r requirements.txt`"
        ) from exc
    activities, objective, A_ub, b_ub, units, product = build_program(workers, travel_fraction, season)
    res = linprog(objective, A_ub=A_ub, b_ub=b_ub, bounds=[(0, None)] * len(activities))
    mix = {a: n for a, n in zip(activities, res.x) if n > 1e-6}
    return {"revenue": -res.fun, "mix": mix, "units": units, "product": product,
            "status": res.message, "activities": activities}


def main(argv=None):  # pragma: no cover - CLI
    ap = argparse.ArgumentParser(description="market revenue ceiling as an LP (#136)")
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--travel", type=float, default=0.45,
                    help="fraction of worker-turns spent moving (measured ~0.45, #132)")
    args = ap.parse_args(argv)

    out = solve(args.workers, args.travel)
    print(f"status: {out['status']}\n")
    print(f"{'activity':12s} {'tiles':>8} {'units':>8} {'revenue':>11}")
    for activity, n in sorted(out["mix"].items(), key=lambda kv: -kv[1]):
        price = economy.base_price(out["product"][activity]) or 0
        u = out["units"][activity] * n
        print(f"{activity:12s} {n:>8.1f} {u:>8.0f} {u * price:>11,.0f}")
    print(f"\nLP revenue (at BASE prices, so a floor): {out['revenue']:>12,.0f}")
    print("A drained market pays up to 2.1x base, which this model cannot see —")
    print("read the number as a floor and the MIX as the useful output.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
