"""fert_sixteen's fourth run (#331): the mechanism control corrected, on fresh seeds.

#329 voided on a bar that compared the contender's seat with the champion's
*other* seat in the same game -- two different farms. Here the champion is
replayed against itself on the control seed (the amendment's own instrument,
`rival_bench.decided_row`'s) and the contender's seat is compared with the
champion's own play in that seat: dawn cash on days 1-16 equal, and the first
differing action on or after the first turn of LEVER_DAY. The FERTILIZE and
strawberry bars, the criterion (ADR-0007 as amended 2026-09-20) and arm B are
sixteen_bench's.

    .venv/bin/python -m harness.sixteend_bench --controls
    .venv/bin/python -m harness.sixteend_bench --criterion
    .venv/bin/python -m harness.sixteend_bench --recorded
"""

from __future__ import annotations

import argparse
import os

from harness.cashflow import play  # noqa: F401  -- pinned by the tests
from harness.evolve import DEFAULT_ANCHORS
from harness.fert_bench import action_counts, units_sold
from harness.four8_bench import escapes
from harness.reserve_bench import MADHUR, REFERENCE  # noqa: F401  -- pinned by the tests
from harness.rival_bench import (
    criterion,
    decided_row,
    format_external,
    format_rows,
    paired_external_rows,
    seat_actions,
)
from harness.six_bench import dawn_cash
from harness.sixteen_bench import (  # noqa: F401  -- the same contender, bars and stubs
    ANCHOR_BAR,
    ARM_B,
    ARM_B_FROM,
    CHAMPION,
    CHAMPION_BAR,
    CONTENDER,
    EARLY_DAYS,
    FERTILIZE_BAR,
    LONESPEAR,
    STRAWBERRY_FACTOR,
    _arm_b_agents,
    arm_b_class,
    off_class,
)

SEEDS = tuple(range(1559, 1575))
CONTROL_SEED = 1559
#: The day the lever starts; the contender's seat must play the champion's own
#: game until the first turn of this day.
LEVER_DAY = 16
TURNS_PER_DAY = 24


def reading(steps, seat) -> dict:
    """One side's FERTILIZE count, strawberry units sold, and dawn cash on days 1-16."""
    return {"fertilize": action_counts(steps, seat).get("FERTILIZE", 0),
            "strawberry": units_sold(steps, seat).get("STRAWBERRY", 0),
            "dawn_1_16": dawn_cash(steps, seat, EARLY_DAYS)}


def first_divergence(ours, own, seat):
    """The first step at which `seat`'s actions in `ours` differ from the same
    seat's in `own` (the champion's self-play), or None when they never do."""
    a, b = seat_actions(ours, seat), seat_actions(own, seat)
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return i
    return None if len(a) == len(b) else min(len(a), len(b))


def mechanism_failures(contender, champion, own, *, first_diff) -> list:
    """Control 2's bars; the names of the ones that did not hold. `champion` is
    the other seat of the control game (the strawberry bar); `own` is the
    champion's own play in the contender's seat (the dawn-cash bar)."""
    failed = []
    if contender["fertilize"] < FERTILIZE_BAR:
        failed.append("fertilize")
    if contender["strawberry"] < STRAWBERRY_FACTOR * champion["strawberry"]:
        failed.append("strawberry")
    if contender["dawn_1_16"] != own["dawn_1_16"]:
        failed.append("dawn_1_16")
    if first_diff is not None and first_diff < LEVER_DAY * TURNS_PER_DAY:
        failed.append("lever_day")
    return failed


def load_reference():
    from strategies import load
    return load(REFERENCE)


# --- live games -------------------------------------------------------------

def run_controls(seed=CONTROL_SEED):  # pragma: no cover
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    from harness.rival_bench import _default_steps
    from harness.tournament import play_rewards
    from harness.triage import _default_agents
    from kaggisim.strategy import make_agent
    from strategies import load
    out = {}
    off = off_class()
    base = play_rewards(make_agent(load(REFERENCE)()), make_agent(load(REFERENCE)()), seed)
    got = play_rewards(make_agent(off()), make_agent(load(REFERENCE)()), seed)
    precondition_ok = base[0] > 0
    out["identity"] = {"ok": got == base and precondition_ok, "base": base, "got": got,
                       "precondition_ok": precondition_ok}
    steps = play(CONTENDER, CHAMPION, seed)
    agents = _default_agents()
    own_steps = _default_steps()(agents(CHAMPION), agents(CHAMPION), seed)
    contender, champion, own = reading(steps, 0), reading(steps, 1), reading(own_steps, 0)
    contender["escapes"], champion["escapes"] = escapes(steps, 0), escapes(steps, 1)
    first_diff = first_divergence(steps, own_steps, 0)
    failed = mechanism_failures(contender, champion, own, first_diff=first_diff)
    out["mechanism"] = {"ok": not failed, "failed": failed, "first_diff": first_diff,
                        "contender": contender, "champion": champion, "own": own}
    return out


def run_criterion(seeds=SEEDS):  # pragma: no cover
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    from harness.triage import head_to_head_rate
    champion_row = decided_row(CONTENDER, CHAMPION, seeds)
    anchor_rows = [head_to_head_rate(CONTENDER, a, seeds) for a in DEFAULT_ANCHORS]
    pairs = paired_external_rows(CONTENDER, CHAMPION, seeds)
    return champion_row, anchor_rows, pairs


def run_recorded(seeds=SEEDS):  # pragma: no cover
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    return decided_row(ARM_B, CHAMPION, seeds, agents=_arm_b_agents(ARM_B))


def main(argv=None):  # pragma: no cover
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    ap = argparse.ArgumentParser(description="fert_sixteen, fourth run: the control corrected")
    ap.add_argument("--controls", action="store_true")
    ap.add_argument("--criterion", action="store_true")
    ap.add_argument("--recorded", action="store_true", help="arm B (recorded, not gated)")
    args = ap.parse_args(argv)

    if args.recorded:
        row = run_recorded()
        print(format_rows([row]))
        decided = row["games"] - row["identical"]
        print(f"recorded, not gated: arm B ({ARM_B}: the line from day {ARM_B_FROM}) vs {CHAMPION}: "
              f"{row['wins']}W {row['ties']}T {row['losses']}L over {decided} decided ({row['identical']} identical)")
        return 0

    do_controls = args.controls or not args.criterion
    do_criterion = args.criterion or not args.controls

    if do_controls:
        ctl = run_controls()
        print(f"control identity: {'OK' if ctl['identity']['ok'] else 'FAIL -- RUN VOID'}  {ctl['identity']}")
        m = ctl["mechanism"]
        print(f"control mechanism: {'OK' if m['ok'] else 'FAIL -- RUN VOID'}  "
              f"(declared: FERTILIZE >= {FERTILIZE_BAR}, strawberry units >= {STRAWBERRY_FACTOR}x the other seat's, "
              f"dawn cash days 1-16 equal to the champion's own seat, first differing action >= step {LEVER_DAY * TURNS_PER_DAY})  "
              f"first_diff={m['first_diff']}  contender {m['contender']}  other seat {m['champion']}  "
              f"champion's own seat {m['own']}  failed={m['failed'] or 'none'}")
        if not all(r["ok"] for r in ctl.values()):
            print("a control failed: the run is VOID and arm B is NOT scored")
            return 2

    if do_criterion:
        champion_row, anchor_rows, pairs = run_criterion()
        print(format_rows([champion_row] + anchor_rows))
        print(format_external(pairs))
        v = criterion(champion_row, anchor_rows, CHAMPION_BAR, ANCHOR_BAR, external_pairs=pairs,
                      identical=champion_row["identical"])
        verdict = "VOID (under-powered)" if v["void"] else ("PROMOTE" if v["passed"] else "REJECTED")
        print(f"champion {champion_row['wins']}W {champion_row['ties']}T {champion_row['losses']}L over {v['decided']} decided "
              f"= {v['champion_rate']:.1%} (bar {CHAMPION_BAR:.0%}; {v['identical']} identical of {champion_row['games']}); "
              f"failing limbs: {v['failing'] or 'none'} -> {verdict}; external net {v['external_net']:+d}; "
              f"paired rows (contender, champion): madhur {v['external'].get(MADHUR)}, lonespear {v['external'].get(LONESPEAR)}")
        if v["void"]:
            return 2
        return 0 if v["passed"] else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
