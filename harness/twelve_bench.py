"""The twelve_head experiment (#320): controls and criterion -- judged under
ADR-0007's amendment of 2026-09-16 as corrected 2026-09-17 (`decided_row`).

Declared on #320 before any code. Controls first -- identity (every seam off
is the frozen benchmark to the value) and mechanism (fewer animals pending
in the shed on day 20 than free_straw and less spent on animals in the same
game); a failed control is a VOID run (exit 2). Then rival_bench's criterion
on the decided row: >= 60% of the decided games vs free_straw (VOID if fewer
than MIN_DECIDED are decided), >= 90% vs each anchor, paired external
non-regression. No arm B.

    .venv/bin/python -m harness.twelve_bench --controls
    .venv/bin/python -m harness.twelve_bench --criterion
"""

from __future__ import annotations

import argparse
import os

from harness.cashflow import play  # noqa: F401  -- pinned by the tests
from harness.episode_analysis import decompose
from harness.evolve import DEFAULT_ANCHORS
from harness.external_pool import ANCHORS_2026_09_07
from harness.farm_census import animals_placed
from harness.feed_bench import board_on_day
from harness.four8_bench import escapes
from harness.fourth_bench import pending_at
from harness.reserve_bench import MADHUR, PILKWANG, REFERENCE  # noqa: F401  -- pinned by the tests
from harness.rival_bench import (  # noqa: F401  -- pinned by the tests to rival_bench's own
    criterion,
    decided_row,
    format_external,
    format_rows,
    paired_external_rows,
)
from harness.sheep_bench import _seam_names
from strategies import field_pace as fp

CONTENDER = "twelve_head"
CHAMPION = "free_straw"
SEEDS = tuple(range(1463, 1479))
CONTROL_SEED = 1463
CHAMPION_BAR = 0.60
ANCHOR_BAR = 0.90
HEAD_DAY = 20
LONESPEAR = ANCHORS_2026_09_07[1]
assert LONESPEAR.startswith("lonespear"), LONESPEAR  # the pool order is the pin (review)


def load_reference():
    from strategies import load
    return load(REFERENCE)


def reading(steps, seat) -> dict:
    """One side's placed and pending head on day 20, its animal spend, and its
    milk and wool revenue."""
    board = board_on_day(steps, seat, HEAD_DAY)
    if board is None:
        raise ValueError(f"no board for day {HEAD_DAY}: the game ended early")
    d = decompose(steps, seat)
    rev, spend = d["revenue"], d["spend"]
    return {"head_20": sum(animals_placed(board["tiles"]).values()),
            "pending_20": pending_at(steps, seat, HEAD_DAY),
            "animal_spend": spend.get("animal", 0),
            "milk_wool": rev.get("MILK", 0) + rev.get("WOOL", 0)}


def mechanism_failures(contender, champion) -> list:
    """Control 2's bars; the names of the ones that did not hold."""
    failed = []
    if not contender["pending_20"] < champion["pending_20"]:
        failed.append("pending_20")
    if not contender["animal_spend"] < champion["animal_spend"]:
        failed.append("animal_spend")
    return failed


def off_class():
    """Every seam off (sixteen), the reference's caps, and the frozen herd ramp."""
    from strategies import load
    body = {n: (lambda self, *a, **k: None) for n in _seam_names()}
    body["CAPS"] = load_reference().CAPS
    body["HERD_RAMP_F"] = fp.HERD_RAMP_F
    return type("Off", (load(CONTENDER),), body)


# --- live games -------------------------------------------------------------

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


def main(argv=None):  # pragma: no cover
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    ap = argparse.ArgumentParser(description="twelve_head: the herd target's last step is twelve")
    ap.add_argument("--controls", action="store_true")
    ap.add_argument("--criterion", action="store_true")
    args = ap.parse_args(argv)

    do_controls = args.controls or not args.criterion
    do_criterion = args.criterion or not args.controls

    if do_controls:
        ctl = run_controls()
        print(f"control identity: {'OK' if ctl['identity']['ok'] else 'FAIL -- RUN VOID'}  {ctl['identity']}")
        c, b = ctl["mechanism"]["contender"], ctl["mechanism"]["champion"]
        print(f"control mechanism: {'OK' if ctl['mechanism']['ok'] else 'FAIL -- RUN VOID'}  "
              f"(declared: pending head on day {HEAD_DAY} < {CHAMPION}'s, animal spend < {CHAMPION}'s)  "
              f"contender {c}  {CHAMPION} {b}  failed={ctl['mechanism']['failed'] or 'none'}")
        if not all(r["ok"] for r in ctl.values()):
            print("a control failed: the run is VOID")
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
              f"paired rows (contender, champion): madhur {v['external'].get(MADHUR)}, "
              f"pilkwang {v['external'].get(PILKWANG)}, lonespear {v['external'].get(LONESPEAR)}")
        if v["void"]:
            return 2
        return 0 if v["passed"] else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
