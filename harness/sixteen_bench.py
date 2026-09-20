"""The fert_sixteen experiment (#324): controls, criterion, arm B -- judged
under ADR-0007's amendment of 2026-09-16 as corrected 2026-09-17.

Declared on #324 before any code. Controls first -- identity (every seam off
is the frozen benchmark to the value) and mechanism (at least FERTILIZE_BAR
FERTILIZE actions, strawberry units at least STRAWBERRY_FACTOR times the
champion's, and dawn cash on days 1-16 equal to the champion's: the lever
must not touch the early economy); a failed control is a VOID run (exit 2).
Then rival_bench's criterion on the decided row: >= 60% of the decided games
vs twelve_head (VOID if fewer than MIN_DECIDED are decided), >= 90% vs each
anchor, paired external non-regression. Arm B (`from_twelve`) is recorded,
never gated.

    .venv/bin/python -m harness.sixteen_bench --controls
    .venv/bin/python -m harness.sixteen_bench --criterion
    .venv/bin/python -m harness.sixteen_bench --recorded
"""

from __future__ import annotations

import argparse
import os

from harness.cashflow import play  # noqa: F401  -- pinned by the tests
from harness.evolve import DEFAULT_ANCHORS
from harness.external_pool import EXTERNAL_ANCHORS
from harness.fert_bench import action_counts, units_sold
from harness.four8_bench import escapes
from harness.reserve_bench import MADHUR, REFERENCE  # noqa: F401  -- pinned by the tests
from harness.rival_bench import (  # noqa: F401  -- pinned by the tests to rival_bench's own
    criterion,
    decided_row,
    format_external,
    format_rows,
    paired_external_rows,
)
from harness.sheep_bench import _seam_names
from harness.six_bench import dawn_cash
from strategies import field_pace as fp

CONTENDER = "fert_sixteen"
CHAMPION = "twelve_head"
SEEDS = tuple(range(1511, 1527))
CONTROL_SEED = 1511
CHAMPION_BAR = 0.60
ANCHOR_BAR = 0.90
FERTILIZE_BAR = 100
STRAWBERRY_FACTOR = 1.5
EARLY_DAYS = range(1, 17)
ARM_B = "from_twelve"
ARM_B_FROM = 12
LONESPEAR = EXTERNAL_ANCHORS[0]
assert LONESPEAR.startswith("lonespear"), LONESPEAR  # the pool order is the pin (review)


def load_reference():
    from strategies import load
    return load(REFERENCE)


def reading(steps, seat) -> dict:
    """One side's FERTILIZE count, strawberry and fertilizer units sold, and
    dawn cash on days 1-16."""
    a, u = action_counts(steps, seat), units_sold(steps, seat)
    return {"fertilize": a.get("FERTILIZE", 0), "strawberry": u.get("STRAWBERRY", 0),
            "fertilizer_sold": u.get("FERTILIZER", 0), "dawn_1_16": dawn_cash(steps, seat, EARLY_DAYS)}


def mechanism_failures(contender, champion) -> list:
    """Control 2's bars; the names of the ones that did not hold."""
    failed = []
    if contender["fertilize"] < FERTILIZE_BAR:
        failed.append("fertilize")
    if contender["strawberry"] < STRAWBERRY_FACTOR * champion["strawberry"]:
        failed.append("strawberry")
    if contender["dawn_1_16"] != champion["dawn_1_16"]:
        failed.append("dawn_1_16")
    return failed


def off_class():
    """Every seam off (sixteen), the reference's caps, and the frozen herd ramp."""
    from strategies import load
    body = {n: (lambda self, *a, **k: None) for n in _seam_names()}
    body["CAPS"] = load_reference().CAPS
    body["HERD_RAMP_F"] = fp.HERD_RAMP_F
    return type("Off", (load(CONTENDER),), body)


def arm_b_class():
    """`fert_sixteen` from day twelve. Never registered."""
    from strategies import load
    return type("FromTwelve", (load(CONTENDER),), {"FERT_FROM": ARM_B_FROM})


# --- live games -------------------------------------------------------------

def _arm_b_agents(name):  # pragma: no cover
    from harness.triage import _default_agents
    from kaggisim.strategy import make_agent
    arm_b = arm_b_class()
    default_agents = _default_agents()

    def agents(who):
        return make_agent(arm_b()) if who == name else default_agents(who)
    return agents


def run_controls(seed=CONTROL_SEED):  # pragma: no cover
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    from harness.tournament import play_rewards
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
    contender, champion = reading(steps, 0), reading(steps, 1)
    contender["escapes"], champion["escapes"] = escapes(steps, 0), escapes(steps, 1)
    failed = mechanism_failures(contender, champion)
    out["mechanism"] = {"ok": not failed, "failed": failed, "contender": contender, "champion": champion}
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
    ap = argparse.ArgumentParser(description="fert_sixteen: the fertilizer line from day 16")
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
        c, b = ctl["mechanism"]["contender"], ctl["mechanism"]["champion"]
        print(f"control mechanism: {'OK' if ctl['mechanism']['ok'] else 'FAIL -- RUN VOID'}  "
              f"(declared: FERTILIZE >= {FERTILIZE_BAR}, strawberry units >= {STRAWBERRY_FACTOR}x {CHAMPION}'s, "
              f"dawn cash days 1-16 equal)  contender {c}  {CHAMPION} {b}  failed={ctl['mechanism']['failed'] or 'none'}")
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
              f"failing limbs: {v['failing'] or 'none'} -> {verdict}; "
              f"paired rows (contender, champion): madhur {v['external'].get(MADHUR)}, lonespear {v['external'].get(LONESPEAR)}")
        if v["void"]:
            return 2
        return 0 if v["passed"] else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
