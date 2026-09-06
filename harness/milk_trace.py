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


#: The two counterfactuals #228 names, as pure seams. The in-process variants
#: below are three lines each that call these; the rules themselves are unit
#: tested, so what the counterfactual actually did is not taken on trust from a
#: class built inside a run function.
COW_CAP = 6
LAST_COW_DAY = 20


def our_cows(obs):
    """Our own cow head: what stands on our tiles plus what waits in the shed.

    `field_rival.market_orders` counts a bought-but-unplaced animal as *pending*
    against the ramp, because an animal only becomes livestock when a herder
    walks it out. A cap that counted placed head alone would re-buy the same cow
    on every one of the day's 24 turns -- the defect that module records as 79
    sheep filling a 100-item shed.
    """
    me = obs["farms"][obs["player"]]
    shed = (obs.get("private") or {}).get("shed") or {}
    return count_cows(me.get("tiles")) + int(shed.get("COW", 0))


def capped_cow_preference(obs, cap=COW_CAP):
    """`rival_aware`'s rule, stopped at `cap` cows (#228 counterfactual a).

    Returning ``None`` is not "buy nothing": it hands the choice back to the
    benchmark's own budget rule, which buys sheep when it can afford three of
    them. So the cap redirects the rest of the ramp into wool, it does not
    shrink the herd.
    """
    from strategies import field_rival as fr
    from strategies.rival_aware import SHEEP_THRESHOLD
    if fr.rival_sheep(obs) < SHEEP_THRESHOLD:
        return None
    return "COW" if our_cows(obs) < cap else None


def dated_cow_preference(obs, last_day=LAST_COW_DAY):
    """`rival_aware`'s rule, switched off from `last_day` on (#228 (b))."""
    from strategies import field_rival as fr
    from strategies.rival_aware import SHEEP_THRESHOLD
    if obs.get("day", 0) >= last_day:
        return None
    return "COW" if fr.rival_sheep(obs) >= SHEEP_THRESHOLD else None


#: The days the cumulative curve is reported at. Day 8 is a cow's first yield,
#: day 28 is the last full day of a 30-day season.
DAY_MARKS = (8, 12, 16, 20, 24, 28)

#: The two bands the CLI reports the price leaving: the base band itself, and
#: half of base -- the level #225's late window fell through on seed 601.
BANDS = (1.0, 0.5)


def _at_days(cumulative, days=DAY_MARKS):
    """The cumulative curve read at `days`, holding the last known total.

    A day the trace never reached reads "-" rather than 0: a season that ended
    early has no volume to report there, and 0 would read as "sold none".
    """
    out = []
    last_day = max(cumulative) if cumulative else None
    for day in days:
        seen = [v for d, v in cumulative.items() if d <= day]
        out.append(seen[-1] if seen and last_day is not None and day <= last_day else None)
    return out


def format_seed_report(record):
    """The per-seed block the CLI prints: control first, then the reading."""
    r = record
    lines = [
        f"seed {r['seed']}  {r['our_name']} in seat {r['seat']}, "
        f"{r['their_name']} in seat {1 - r['seat']}",
    ]
    c = r["control"]
    lines.append(
        f"  control  trace {c['trace_units']} units / {c['trace_revenue']:.0f} revenue "
        f"vs price_realisation {c['season_units']} / {c['season_revenue']:.0f}"
        f"  -> {'OK' if c['ok'] else 'MISMATCH -- the trace is not believed'}")
    lines.append(
        f"  town     {r['milk_shops']} milk shop instances of {r['shop_instances']}, "
        f"arriving on days {r['milk_shop_days']}, "
        f"season draw {r['season_demand']} units")
    band, half = r["first_day_band"], r["first_day_half"]
    lines.append(
        f"  price    left the base band on day {band if band is not None else 'never'}; "
        f"below 50% of base on day {half if half is not None else 'never'}")
    marks = "  ".join(f"{d:>5}" for d in DAY_MARKS)
    ours = "  ".join(f"{v if v is not None else '-':>5}" for v in _at_days(r["our_by_day"]))
    theirs = "  ".join(f"{v if v is not None else '-':>5}" for v in _at_days(r["their_by_day"]))
    lines.append(f"  milk units by day     {marks}")
    lines.append(f"    {r['our_name']:<18} {ours}")
    lines.append(f"    {r['their_name']:<18} {theirs}")
    lines.append(
        f"  volume   {r['combined_units']} units into a {r['season_demand']}-unit draw "
        f"= {r['draw_ratio']:.2f}x the town")
    if r.get("reference_seed") is not None:
        lines.append(
            f"  revenue  our {r['our_units']} units fetched {r['revenue_here']:,.0f} here "
            f"vs {r['revenue_reference']:,.0f} on seed {r['reference_seed']}'s price path "
            f"-> {r['revenue_here'] - r['revenue_reference']:+,.0f}")
    return "\n".join(lines)


# --- live games -------------------------------------------------------------

def seat_for(seed):
    """Seat 0 on an even seed, seat 1 on an odd one -- the repo's alternation
    (`harness.triage.head_to_head_rate` alternates by list position; on the
    contiguous 600-607 range the two coincide)."""
    return 0 if seed % 2 == 0 else 1


def _drive(our_agent, their_agent, seed, seat, episode_steps=720):  # pragma: no cover
    """Play one game turn by turn, recording the milk market from both seats.

    Everything is read off each seat's observation *before* it acts, which is
    the state its order is applied to; the env mutates those observations in
    place as the game continues, so nothing here may be deferred.
    """
    from kaggle_environments import make

    from harness.episode_analysis import banked_this_turn, unit_prices

    env = make("kaggriculture", configuration={"episodeSteps": episode_steps, "seed": seed})
    env.reset(2)
    agents = [None, None]
    agents[seat] = our_agent
    agents[1 - seat] = their_agent

    trace = []
    for _ in range(episode_steps - 1):
        obs = [env.state[i].observation for i in (0, 1)]
        market = obs[0]["market"]
        prices, inventory = market["prices"], market["inventory"]
        step = int(obs[0]["step"])
        shops = list((obs[0].get("town") or {}).get("unlocked_shops") or [])
        acts = [agents[i](obs[i]) for i in (0, 1)]

        seqs = []
        for i in (0, 1):
            private = obs[i]["private"]
            banked = banked_this_turn(acts[i], private.get("inventories") or [])
            seqs.append(unit_prices(acts[i].get("market") or [], prices,
                                    private.get("shed") or {}, banked,
                                    inventory).get(ITEM, []))
        us, them = seqs[seat], seqs[1 - seat]
        trace.append({
            "step": step, "day": int(obs[0]["day"]), "hour": int(obs[0]["hour"]),
            "seat": seat,
            "milk_inventory": int(inventory[ITEM]), "milk_price": int(prices[ITEM]),
            "our_cows": count_cows(obs[seat]["farms"][seat]["tiles"]),
            "their_cows": count_cows(obs[seat]["farms"][1 - seat]["tiles"]),
            "our_milk_sold": len(us), "their_milk_sold": len(them),
            "our_milk_revenue": sum(us), "their_milk_revenue": sum(them),
            # Sales at the $1 floor add no market supply (the sim's own rule),
            # so the supply check has to count the others only.
            "milk_supplied": sum(1 for p in us + them if p > 1),
            "milk_drawn": town_draw(shops, step, ITEM),
            "shops": len(shops),
            "milk_shops": sum(1 for s in shops if ITEM in (SHOP_DEMAND.get(s) or [])),
        })
        env.step(acts)
    return trace, env


def trace_game(our_name, their_name, seed, episode_steps=720):  # pragma: no cover
    """Per-turn milk trace of `our_name` vs `their_name` on `seed`."""
    from kaggisim.strategy import make_agent
    from strategies import load
    seat = seat_for(seed)
    trace, _ = _drive(make_agent(load(our_name)()), make_agent(load(their_name)()),
                      seed, seat, episode_steps)
    return trace


def _measure(trace, env, seed, seat, our_name, their_name):  # pragma: no cover
    """The reading taken off one driven game, control first."""
    from harness.episode_analysis import price_realisation
    analysis = price_realisation(env.steps, seat)
    summary = (analysis.get("items") or {}).get(ITEM) or {}
    season_demand = sum(row["milk_drawn"] for row in trace)
    our_by_day = cumulative_by_day(trace, "our_milk_sold")
    their_by_day = cumulative_by_day(trace, "their_milk_sold")
    our_units = sum(row["our_milk_sold"] for row in trace)
    their_units = sum(row["their_milk_sold"] for row in trace)
    final_inventory = int(env.state[0].observation["market"]["inventory"][ITEM])
    supplied = sum(row["milk_supplied"] for row in trace)
    shops = list((env.state[0].observation.get("town") or {}).get("unlocked_shops") or [])
    return {
        "seed": seed, "seat": seat, "our_name": our_name, "their_name": their_name,
        "control": reconciliation(trace, analysis),
        "shop_instances": len(shops),
        "shop_list": shops,
        "milk_shops": sum(1 for s in shops if ITEM in (SHOP_DEMAND.get(s) or [])),
        "milk_shop_days": shop_arrival_days(trace),
        "season_demand": season_demand,
        "first_day_band": first_day_below(trace, BANDS[0]),
        "first_day_half": first_day_below(trace, BANDS[1]),
        "our_by_day": our_by_day, "their_by_day": their_by_day,
        "our_units": our_units, "their_units": their_units,
        "combined_units": our_units + their_units,
        "draw_ratio": draw_ratio(our_units + their_units, season_demand),
        "units_by_turn": {row["step"]: row["our_milk_sold"] for row in trace},
        "prices_by_turn": {row["step"]: row["milk_price"] for row in trace},
        "realised_revenue": summary.get("revenue", 0),
        "realised_pct_of_base": summary.get("pct_of_base", 0.0),
        "late_pct_of_base": summary.get("late_pct_of_base", 0.0),
        "final_money": float(env.state[0].observation["farms"][seat]["money"]),
        "their_money": float(env.state[0].observation["farms"][1 - seat]["money"]),
        # Independent of the reconstruction's *prices*: the market's own
        # inventory identity. 10,000 anchor + every non-floor unit both farms
        # sold - everything the town drew should be exactly what is left.
        "supply_check": {
            "predicted": 10000 + supplied - season_demand,
            "observed": final_inventory,
        },
    }


def measure_seed(our_name, their_name, seed, episode_steps=720,
                 seat=None):  # pragma: no cover
    """Drive one seeded game and read the milk market off it.

    `seat` pins which side we play instead of taking the alternation. It is not
    cosmetic: the sim's `_end_of_day` draws weeds for farm 0 then farm 1 from
    the *same* per-day RNG it then draws the town's next shop from, so swapping
    seats shifts every later shop draw. Seed 601's town is a different town on
    each side.
    """
    from kaggisim.strategy import make_agent
    from strategies import load
    seat = seat_for(seed) if seat is None else seat
    trace, env = _drive(make_agent(load(our_name)()), make_agent(load(their_name)()),
                        seed, seat, episode_steps)
    return _measure(trace, env, seed, seat, our_name, their_name)


def run_seeds(seeds, our_name, their_name, reference_seed=600,
              episode_steps=720, seat=None):  # pragma: no cover
    """One record per seed, each carrying the counterfactual revenue against
    `reference_seed`'s price path once that seed has been measured."""
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")   # an instrument surfaces crashes
    records = [measure_seed(our_name, their_name, seed, episode_steps, seat)
               for seed in seeds]
    reference = next((r for r in records if r["seed"] == reference_seed), None)
    for r in records:
        r["revenue_here"] = revenue_at(r["units_by_turn"], r["prices_by_turn"])
        if reference is not None:
            r["reference_seed"] = reference_seed
            r["revenue_reference"] = revenue_if(r["units_by_turn"],
                                                reference["prices_by_turn"])
    return records


#: A late window at or above this share of base is the issue's reading of "the
#: price held"; below it the market spent the end of the season on the floor.
HELD_BAND = 0.5


def format_counterfactuals(rows):
    """The #228 question-4 table: one line per variant per seed.

    A variant whose cow head matches the unmodified agent's on the same seed is
    called out: its money and its price are the champion's, so reporting it as
    a counterfactual result would be reporting the champion twice.
    """
    lines = [f"{'variant':<20} {'seed':>4} {'money':>10} {'vs base':>10} {'cows':>5} "
             f"{'units':>6} {'milk %base':>11} {'late %base':>11}  price"]
    head = {}
    for r in rows:
        baseline = r["seed"] not in head
        base_head = head.setdefault(r["seed"], r["max_cows"])
        note = ""
        if not baseline and r["delta_money"] == 0.0 and r["max_cows"] == base_head:
            note = "   <- mechanism did not fire"
        lines.append(
            f"{r['variant']:<20} {r['seed']:>4} {r['final_money']:>10,.0f} "
            f"{r['delta_money']:>+10,.0f} {r['max_cows']:>5} {r['our_units']:>6} "
            f"{r['realised_pct_of_base']:>10.1%} {r['late_pct_of_base']:>11.1%}  "
            f"{'held' if r['held'] else 'floored'}{note}")
    return "\n".join(lines)


#: The matchup #228 names: the champion against the one anchor that runs a big
#: herd of its own (9 cows, 4 sheep), on the seed range #225 measured.
US = "rival_aware"
THEM = "meta_bot"
SEEDS = tuple(range(600, 608))
REFERENCE_SEED = 600
COUNTERFACTUAL_SEEDS = (600, 601)


def run_counterfactuals(seeds=COUNTERFACTUAL_SEEDS, our_name=US, their_name=THEM,
                        episode_steps=720, seat=None):  # pragma: no cover
    """#228 question 4, recorded and never gated.

    Two variants of the champion, built in-process with `type()` and never
    registered under `strategies/`, so neither can be promoted or packaged by
    accident: (a) the same rule stopped at `COW_CAP` cows, (b) the same rule
    switched off from day `LAST_COW_DAY`. Both go through the benchmark's
    `herd_preference` seam and change nothing else, and both rules are the unit
    tested pure functions above rather than logic written inside this function.

    The unmodified champion is played first on each seed in the same loop, so
    the money delta is a difference between two games driven identically rather
    than a comparison against a number quoted from another run.
    """
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")   # an instrument surfaces crashes
    from kaggisim.strategy import make_agent
    from strategies import load

    base = load(our_name)
    variants = [
        (our_name, base),
        (f"cap_{COW_CAP}_cows", type("CappedCows", (base,), {
            "herd_preference": lambda self, obs: capped_cow_preference(obs)})),
        (f"cows_to_day_{LAST_COW_DAY}", type("CowsUntilDay", (base,), {
            "herd_preference": lambda self, obs: dated_cow_preference(obs)})),
    ]

    rows, baseline = [], {}
    for label, cls in variants:
        for seed in seeds:
            side = seat_for(seed) if seat is None else seat
            trace, env = _drive(make_agent(cls()), make_agent(load(their_name)()),
                                seed, side, episode_steps)
            rec = _measure(trace, env, seed, side, label, their_name)
            money = rec["final_money"]
            baseline.setdefault(seed, money)
            rows.append({
                "variant": label, "seed": seed, "final_money": money,
                "delta_money": money - baseline[seed],
                "max_cows": max((row["our_cows"] for row in trace), default=0),
                "our_units": rec["our_units"],
                "realised_pct_of_base": rec["realised_pct_of_base"],
                "late_pct_of_base": rec["late_pct_of_base"],
                "held": rec["late_pct_of_base"] >= HELD_BAND,
                "control": rec["control"],
                "their_money": rec["their_money"],
            })
    return rows


def main(argv=None):  # pragma: no cover
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")   # an instrument surfaces crashes
    ap = argparse.ArgumentParser(
        description="#228: per-turn MILK market trace (a measurement, not an experiment)")
    ap.add_argument("--seeds", type=int, nargs="+", default=list(SEEDS))
    ap.add_argument("--us", default=US)
    ap.add_argument("--them", default=THEM)
    ap.add_argument("--reference-seed", type=int, default=REFERENCE_SEED,
                    help="the price path the same units are re-priced against")
    ap.add_argument("--seat", type=int, choices=(0, 1), default=None,
                    help="pin our seat instead of alternating; the seat changes "
                         "the town, so #225's seat-0 reading needs --seat 0")
    ap.add_argument("--counterfactuals", action="store_true",
                    help="the two in-process herd variants (recorded, not gated)")
    args = ap.parse_args(argv)

    if args.counterfactuals:
        rows = run_counterfactuals(our_name=args.us, their_name=args.them,
                                   seat=args.seat)
        bad = [r for r in rows if not r["control"]["ok"]]
        print(format_counterfactuals(rows))
        print(f"\ncontrols: {len(rows) - len(bad)}/{len(rows)} games reconciled to "
              f"price_realisation" + ("" if not bad else "  -- MISMATCHES, NOT BELIEVED"))
        print(f"recorded, not gated: {US} variants vs {args.them}, "
              f"cap {COW_CAP} cows / cows to day {LAST_COW_DAY}")
        return 0 if not bad else 2

    records = run_seeds(args.seeds, args.us, args.them, args.reference_seed,
                        seat=args.seat)
    for r in records:
        print(format_seed_report(r))
        print(f"  shops    {r['shop_list']}")
        s = r["supply_check"]
        print(f"  supply   market inventory {s['observed']} vs 10,000 + non-floor sales "
              f"- town draw = {s['predicted']}  (gap {s['observed'] - s['predicted']})")
        print()
    collapsed = [r["seed"] for r in records if r["first_day_half"] is not None]
    print(f"collapsed (price below 50% of base at some point): "
          f"{len(collapsed)}/{len(records)} seeds {collapsed}")
    return 0 if all(r["control"]["ok"] for r in records) else 2


if __name__ == "__main__":
    raise SystemExit(main())


def shop_arrival_days(trace, key="milk_shops"):
    """The day each milk-carrying shop instance appeared in the town.

    Not how many shops the town ended with -- *when* it got them. The town
    unlocks eight instances over the season, one every three days, drawn from
    the eight types with replacement, and a milk shop that arrives on day 21
    has drained six days of a thirty-day season. Two instances unlocking on the
    same day are two entries: the count is what drives the draw.
    """
    days, seen = [], 0
    for row in trace:
        count = row.get(key) or 0
        while count > seen:
            days.append(row["day"])
            seen += 1
    return days
