"""Steal the opening book (issue #207): pick it, control it, then measure it.

#157 decomposed 63 real ladder matches and found the field's shape, not its
tactics, is what beats us: the 40-60% livestock-share cohort went **13 of 13**
against us with a median final of 74,332. `meta_bot` was written from a
*description* of that build. Nobody has ever run the actual recorded actions.

This module does, in the order #207 declared, stopping at the first failure:

1. **Select the book.** The cohort is recomputed from the replays rather than
   quoted from `docs/findings.md`, by the rule declared before any code was
   written: rival final money > the 3,000 it started with, livestock+fertilizer
   revenue share in [0.40, 0.60), and of those the richest -- ties broken by
   episode name so the choice can never depend on iteration order.
2. **The positive control**, which is #207's necessary condition: replaying that
   opening must reproduce **the source opponent's own day-3 money** to within
   #157's 7.3% residual. Both seats are scripted, because #204 established that
   the two farms sell into one shared market and a book whose counterparty plays
   something else is not replaying its episode. **And a control that cannot fail
   proves nothing**, so the same probe is run against a book holding the exact
   #157 off-by-one (`shift_script`), which must MISS, and against the starting
   3,000, which the recorded day-3 money must not equal. Fail any arm and the
   run is void: the tolerance is not weakened.
3. **The day-16 necessary condition** -- #196's bar, over 6 fresh seeds: animals
   >= 8, livestock revenue >= 30%, planted >= 30, on *every* seed (the stricter
   reading of "over 6 fresh seeds", declared before the numbers existed).
4. **The pass criterion**, verbatim: 16 fresh seeds, sides alternated, beat the
   champion in >= 60% of 16 and hold >= 90% against each anchor. Ties are losses.

Usage (replays are not in the repo -- they are downloaded, see #157):

    python -m harness.opening_bench --replays <dir>
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys

from harness.episode_analysis import decompose
from harness.evolve import DEFAULT_ANCHORS
from harness.ghost_bench import episode_seed, residual_fraction, seat_of
from kaggisim import economy
from strategies.ghost import Ghost
from strategies.opening_book import OPENING_TURNS, OpeningBookStrategy, shift_script

# --- The criteria, declared on #207 before any code was written (ADR-0007) ---

#: Livestock revenue as #157 counts it. Fertilizer is in: it is a free byproduct
#: of owning animals and 17% of the winning field's revenue on its own.
LIVESTOCK_ITEMS = ("MILK", "WOOL", "EGG", "FERTILIZER")

#: The cohort #207 names, half-open so 60% belongs to the next bucket up.
COHORT_BAND = (0.40, 0.60)

#: `docs/findings.md`'s buckets are over the opponents that finished above the
#: money they started with; a farm that did not is not a winner to copy.
START_MONEY = economy.CONFIG_DEFAULTS["startingMoney"]

#: #157's median reconstruction residual, declared by #204 and reused by #207.
RESIDUAL_TOLERANCE = 0.073

#: The control's probe: the first turn of day 3, i.e. one turn past the opening.
CONTROL_STEP = OPENING_TURNS

#: The second necessary condition's probe, on the same clock.
DAY16_STEP = 16 * economy.CONFIG_DEFAULTS["turnsPerDay"]
MIN_ANIMALS = 8
MIN_LIVESTOCK_SHARE = 0.30
MIN_PLANTED = 30
#: Fresh: #202 used 100-115 and 200-215, #211 used 300-331.
DAY16_SEEDS = tuple(range(400, 406))

#: The pass criterion. 16 seeds, because the seed-to-seed stdev on a fixed
#: pairing is 6,000-11,200 (#181) and four games resolve nothing under ~10,000.
CRITERION_SEEDS = tuple(range(500, 516))
CHAMPION_BAR = 0.60
ANCHOR_BAR = 0.90

#: The frozen comparability pool, so #207 is measured on the same bar as #196
#: and #202.
ANCHORS = tuple(DEFAULT_ANCHORS)

#: A full season, as the ladder runs it.
EPISODE_STEPS = economy.CONFIG_DEFAULTS["episodeSteps"]


def _gate_opponent(path=os.path.join(os.path.dirname(__file__), "champion.json")):
    """The designated `gate_opponent` -- what ADR-0007 measures against.

    Not `submit_default`: CLAUDE.md keeps the two roles apart deliberately, and
    the gate wants the most demanding representative bar even when that is a
    vendored benchmark.
    """
    with open(path) as handle:
        return json.load(handle)["gate_opponent"]


#: The current champion for #207's purposes, pinned to the copy of
#: `harness/champion.json` committed on this branch.
CHAMPION = _gate_opponent()


# --- Selecting the book ---

def livestock_share(revenue):
    """Milk/wool/egg/fertilizer as a share of all revenue. 0.0 if nothing sold."""
    total = sum(revenue.values())
    if not total:
        return 0.0
    return sum(revenue.get(item, 0.0) for item in LIVESTOCK_ITEMS) / total


def in_cohort(row):
    """Is this rival in #207's 40-60% livestock-share cohort?"""
    low, high = COHORT_BAND
    return (row["final_money"] > START_MONEY
            and low <= livestock_share(row["revenue"]) < high)


def select_book(rows):
    """The cohort's richest member; ties broken by episode name ascending.

    Raises rather than falling back to a near-miss: #207 is BLOCKED if the
    cohort has no member, not quietly re-specified onto a different cohort.
    """
    cohort = [row for row in rows if in_cohort(row)]
    if not cohort:
        raise ValueError("the 40-60% livestock-share cohort is empty; #207 is blocked")
    return min(cohort, key=lambda row: (-row["final_money"], row["episode"]))


# --- Reading a game ---

def _observation(steps, index, player):
    """One player's observation at state `index`, or None past the end."""
    if index >= len(steps) or player >= len(steps[index]):
        return None
    return (steps[index][player] or {}).get("observation") or None


def _farm(steps, index, player):
    """`player`'s own farm dict at state `index`.

    Read off the *shared* observation (player 0's slot), which is where both a
    downloaded replay and a live env keep every farm -- player 1's stored
    observation is the private half only.
    """
    obs = _observation(steps, index, 0)
    farms = (obs or {}).get("farms") or []
    return farms[player] if player < len(farms) else None


def money_at(steps, index, player):
    """`player`'s cash at state `index`, or None if the episode ended first."""
    farm = _farm(steps, index, player)
    return None if farm is None else float(farm.get("money", 0))


def farm_shape(steps, index, player):
    """Planted tiles and animal tiles on `player`'s board at state `index`.

    Counted exactly as `harness/production_report.py::snapshot_turn` counts
    them, so #207's day-16 numbers are the same measurement #196's were.
    """
    farm = _farm(steps, index, player) or {}
    tiles = farm.get("tiles") or []
    return {
        "planted": sum(1 for row in tiles for t in row
                       if isinstance(t, dict) and t.get("kind") == "PLANT"),
        "animals": sum(1 for row in tiles for t in row
                       if isinstance(t, dict) and t.get("animal")),
    }


# --- The verdicts ---

def control_verdict(positive, negative, recorded):
    """Did the control pass on all three arms?

    `positive` is the residual of the faithful replay, `negative` that of the
    same book holding the #157 off-by-one, and `recorded` the source's own
    day-3 money. All three matter: a faithful match is only evidence if the
    wrong book misses, and only meaningful if day 3 had moved off the starting
    cash at all.
    """
    return (positive <= RESIDUAL_TOLERANCE
            and negative > RESIDUAL_TOLERANCE
            and recorded != START_MONEY)


def day16_passed(row):
    """All three of #207's day-16 bars, not two of three."""
    return (row["animals"] >= MIN_ANIMALS
            and row["livestock_share"] >= MIN_LIVESTOCK_SHARE
            and row["planted"] >= MIN_PLANTED)


def day16_verdict(rows):
    """Every seed, the stricter reading of "over 6 fresh seeds" (declared)."""
    return bool(rows) and all(day16_passed(row) for row in rows)


def our_seat(index):
    """Sides alternated: player 0 on even seeds, player 1 on odd."""
    return index % 2


def won(row):
    """A tie is not a win -- the stricter reading of "beats" / "holds"."""
    return row["ours"] > row["theirs"]


def win_rate(rows):
    """Wins over every game played, ties included in the denominator."""
    return sum(1 for row in rows if won(row)) / len(rows) if rows else 0.0


def criterion_passed(champion_rate, anchor_rates):
    """#207 verbatim: >= 60% of 16 vs the champion AND >= 90% vs each anchor.

    An anchor missing from `anchor_rates` fails: absence of a measurement is
    not a pass.
    """
    return (champion_rate >= CHAMPION_BAR
            and all(anchor_rates.get(name, -1.0) >= ANCHOR_BAR for name in ANCHORS))


# --- Full-game entrypoints: whole seasons a call, integration by nature ---


def _digest(name, replay):  # pragma: no cover
    """What the bench needs from one replay, with the observations released."""
    seat = seat_of(replay)
    rival = 1 - seat
    return {
        "episode": name,
        "seed": episode_seed(replay),
        "seat": rival,
        "our_seat": seat,
        "final_money": float((replay.get("rewards") or [0.0, 0.0])[rival] or 0.0),
        "revenue": decompose(replay["steps"], rival)["revenue"],
        "day3_money": money_at(replay["steps"], CONTROL_STEP, rival),
        "scripts": [Ghost.from_replay(replay, 0).script,
                    Ghost.from_replay(replay, 1).script],
    }


def load_rows(directory):  # pragma: no cover
    """Digest every downloaded replay, one resident at a time (~21 MB each)."""
    rows = []
    for path in sorted(glob.glob(os.path.join(directory, "*.json"))):
        with open(path) as handle:
            replay = json.load(handle)
        try:
            rows.append(_digest(os.path.basename(path), replay))
        except ValueError as exc:               # OUR_TEAM did not play it
            print(f"  skipped {os.path.basename(path)}: {exc}")
        del replay
    return rows


def _make_env(seed):  # pragma: no cover
    from kaggle_environments import make
    config = {"episodeSteps": EPISODE_STEPS}
    if seed is not None:
        config["seed"] = seed
    return make("kaggriculture", configuration=config)


def _agent(strategy):  # pragma: no cover
    """A Strategy is not an agent. Passing one straight to `env.run` cost #204 a
    whole 63-episode run that came back DONE with the starting cash untouched."""
    from kaggisim.strategy import make_agent
    return make_agent(strategy)


def control_run(row, script):  # pragma: no cover
    """Replay `script` as the source's opening in the source's own episode.

    Both seats scripted: the book plays the source's seat and the counterparty
    is ghosted from the same replay, because the two farms sell into one shared
    market (#204).
    """
    seat = row["seat"]
    players = [None, None]
    players[seat] = _agent(OpeningBookStrategy(script=script,
                                               handover=Ghost(script)))
    players[1 - seat] = _agent(Ghost(row["scripts"][1 - seat]))
    env = _make_env(row["seed"])
    env.run(players)
    return money_at(env.steps, CONTROL_STEP, seat)


def bench_game(book, opponent, seed, index):  # pragma: no cover
    """One criterion game: the opening book against a registered opponent."""
    from strategies import load

    us = our_seat(index)
    players = [None, None]
    players[us] = _agent(OpeningBookStrategy(script=book["scripts"][book["seat"]]))
    players[1 - us] = _agent(load(opponent)())
    env = _make_env(seed)
    env.run(players)
    rewards = [s.reward or 0 for s in env.steps[-1]]
    return {"seed": seed, "opponent": opponent, "ours": float(rewards[us]),
            "theirs": float(rewards[1 - us]),
            "statuses": [s.status for s in env.steps[-1]]}


def day16_game(book, seed, index):  # pragma: no cover
    """One day-16 probe game against the champion."""
    from strategies import load

    us = our_seat(index)
    players = [None, None]
    players[us] = _agent(OpeningBookStrategy(script=book["scripts"][book["seat"]]))
    players[1 - us] = _agent(load(CHAMPION)())
    env = _make_env(seed)
    env.run(players)
    shape = farm_shape(env.steps, DAY16_STEP, us)
    revenue = decompose(env.steps[:DAY16_STEP + 1], us)["revenue"]
    return dict(shape, seed=seed, livestock_share=livestock_share(revenue),
                revenue=revenue)


def main(argv=None):  # pragma: no cover
    ap = argparse.ArgumentParser(description="the opening-book bench (#207)")
    ap.add_argument("--replays", required=True, help="directory of downloaded replays")
    ap.add_argument("--json", default=None, help="write every row here")
    ap.add_argument("--stage", default="all",
                    choices=("cohort", "control", "day16", "criterion", "all"))
    args = ap.parse_args(argv)

    out = {}
    rows = load_rows(args.replays)
    print(f"{len(rows)} replays from {args.replays}\n")

    print("=== the 40-60% livestock-share cohort ===")
    cohort = [r for r in rows if in_cohort(r)]
    for row in sorted(cohort, key=lambda r: -r["final_money"]):
        print(f"  {row['episode']:34s} final {row['final_money']:>9,.0f} "
              f"livestock {livestock_share(row['revenue']):6.1%} "
              f"day3 {row['day3_money']}")
    book = select_book(rows)
    print(f"  n={len(cohort)}   BOOK: {book['episode']} "
          f"(seat {book['seat']}, seed {book['seed']}, final {book['final_money']:,.0f}, "
          f"day-3 money {book['day3_money']})\n")
    out["cohort"] = [{k: v for k, v in r.items() if k != "scripts"} for r in cohort]
    if args.stage == "cohort":
        return _write(args.json, out)

    print("=== positive control: the replayed opening vs its own day-3 money ===")
    script = book["scripts"][book["seat"]]
    recorded = book["day3_money"]
    good = control_run(book, script)
    bad = control_run(book, shift_script(script))
    pos = residual_fraction(good, recorded)
    neg = residual_fraction(bad, recorded)
    print(f"  recorded day-3 money      {recorded:,.0f}  (start {START_MONEY:,})")
    print(f"  faithful replay           {good:,.0f}  residual {pos:.3%}  "
          f"(need <= {RESIDUAL_TOLERANCE:.1%})")
    print(f"  off-by-one arm            {bad:,.0f}  residual {neg:.3%}  "
          f"(must MISS)")
    passed = control_verdict(pos, neg, recorded)
    print(f"  CONTROL: {'PASS' if passed else 'FAIL'}\n")
    out["control"] = {"recorded": recorded, "faithful": good, "shifted": bad,
                      "positive_residual": pos, "negative_residual": neg,
                      "passed": passed}
    if not passed:
        print("Control failed -- the claim is not measured (#207 necessary condition).")
        return _write(args.json, out)
    if args.stage == "control":
        return _write(args.json, out)

    print(f"=== day-16 necessary condition vs {CHAMPION} ===")
    d16 = [day16_game(book, seed, i) for i, seed in enumerate(DAY16_SEEDS)]
    for row in d16:
        print(f"  seed {row['seed']}  planted {row['planted']:>3d} "
              f"animals {row['animals']:>2d} livestock {row['livestock_share']:6.1%}  "
              f"{'PASS' if day16_passed(row) else 'FAIL'}")
    print(f"  need planted >= {MIN_PLANTED}, animals >= {MIN_ANIMALS}, "
          f"livestock >= {MIN_LIVESTOCK_SHARE:.0%} on ALL {len(DAY16_SEEDS)} seeds")
    d16_ok = day16_verdict(d16)
    print(f"  DAY-16 CONDITION: {'PASS' if d16_ok else 'FAIL'}\n")
    out["day16"] = d16
    if args.stage == "day16":
        return _write(args.json, out)

    print("=== pass criterion: 16 fresh seeds, sides alternated ===")
    games, rates = [], {}
    for opponent in ANCHORS:
        rows_o = [bench_game(book, opponent, seed, i)
                  for i, seed in enumerate(CRITERION_SEEDS)]
        games.extend(rows_o)
        rates[opponent] = win_rate(rows_o)
        wins = sum(1 for r in rows_o if won(r))
        print(f"  vs {opponent:15s} {wins:>2d}/{len(rows_o)} = {rates[opponent]:6.1%}")
    champion_rate = rates[CHAMPION]
    print(f"\n  champion ({CHAMPION}) {champion_rate:.1%}  (need >= {CHAMPION_BAR:.0%})")
    print(f"  anchors      min {min(rates.values()):.1%}  (need >= {ANCHOR_BAR:.0%} each)")
    verdict = criterion_passed(champion_rate, rates)
    print(f"  VERDICT: {'PROMOTE' if verdict else 'REJECTED'}")
    out["criterion"] = {"games": games, "rates": rates, "passed": verdict}
    return _write(args.json, out)


def _write(path, out):  # pragma: no cover
    if path:
        with open(path, "w") as handle:
            json.dump(out, handle, indent=2, default=str)
        print(f"\n  rows written to {path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
