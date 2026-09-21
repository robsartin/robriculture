"""The second_melon experiment (#334): controls and criterion -- judged under
ADR-0007 as amended 2026-09-16 and 2026-09-20, corrected 2026-09-17.

Declared on #334 before any code. Controls first -- identity (every seam
off, seventeen, is the frozen benchmark to the value) and mechanism (at
least MELON_BAR melon tiles standing on day 14 and more than the champion's;
more melon units sold than the champion's in the same game); a failed
control is a VOID run (exit 2). Then rival_bench's criterion on the decided
row: >= 60% of the decided games vs fert_sixteen (VOID if fewer than
MIN_DECIDED are decided), >= 90% vs each anchor, the paired external limb as
a whole. No arm B.

    .venv/bin/python -m harness.melon2_bench --controls
    .venv/bin/python -m harness.melon2_bench --criterion
"""

from __future__ import annotations

import argparse
import os

from harness.cashflow import play  # noqa: F401  -- pinned by the tests
from harness.evolve import DEFAULT_ANCHORS
from harness.external_pool import EXTERNAL_ANCHORS
from harness.feed_bench import board_on_day
from harness.fert_bench import units_sold
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
from strategies import field_pace as fp
from strategies import field_rival as fr

CONTENDER = "second_melon"
CHAMPION = "fert_sixteen"
SEEDS = tuple(range(1671, 1687))
CONTROL_SEED = 1671
CHAMPION_BAR = 0.60
ANCHOR_BAR = 0.90
MELON_DAY = 14
LATE_DAY = 20
MELON_BAR = 5
LONESPEAR = EXTERNAL_ANCHORS[0]
assert LONESPEAR.startswith("lonespear"), LONESPEAR  # the pool order is the pin (review)


def load_reference():
    from strategies import load
    return load(REFERENCE)


def _melon(steps, seat, day):
    board = board_on_day(steps, seat, day)
    return None if board is None else fr.standing_crops(board["tiles"]).get("MELON", 0)


def reading(steps, seat) -> dict:
    """One side's standing melon on days 14 and 20, and its melon and strawberry
    units sold. Day 20 may be None (printed, never gated); day 14 may not."""
    melon_14 = _melon(steps, seat, MELON_DAY)
    if melon_14 is None:
        raise ValueError(f"no board for day {MELON_DAY}: the game ended early")
    u = units_sold(steps, seat)
    return {"melon_14": melon_14, "melon_20": _melon(steps, seat, LATE_DAY),
            "melon_units": u.get("MELON", 0), "strawberry_units": u.get("STRAWBERRY", 0)}


def mechanism_failures(contender, champion) -> list:
    """Control 2's bars; the names of the ones that did not hold."""
    failed = []
    if contender["melon_14"] < MELON_BAR or not contender["melon_14"] > champion["melon_14"]:
        failed.append("melon_14")
    if not contender["melon_units"] > champion["melon_units"]:
        failed.append("melon_units")
    return failed


def off_class():
    """Every seam off (seventeen), the reference's caps, and the frozen herd ramp."""
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
    ap = argparse.ArgumentParser(description="second_melon: a second melon wave on days 12-13")
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
              f"(declared: melon tiles at day {MELON_DAY} >= {MELON_BAR} and > {CHAMPION}'s, melon units > {CHAMPION}'s)  "
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
              f"failing limbs: {v['failing'] or 'none'} -> {verdict}; external net {v['external_net']:+d}; "
              f"paired rows (contender, champion): madhur {v['external'].get(MADHUR)}, lonespear {v['external'].get(LONESPEAR)}")
        if v["void"]:
            return 2
        return 0 if v["passed"] else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
