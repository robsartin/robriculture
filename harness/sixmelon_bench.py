"""The six_melon experiment (#341): controls and criterion -- judged under
ADR-0007 as amended 2026-09-16, 2026-09-20 and 2026-09-21, corrected
2026-09-17.

Declared on #341 before any code. Controls first -- identity (every seam off,
twenty, is the frozen benchmark to the value) and mechanism (melon units sold
by the end of EARLY_DAY at least EARLY_BAR and more than the champion's -- the
first wave cut at six, none lost -- and melon units over the game more than
the champion's; strawberry units printed, not gated); a failed control is a
VOID run (exit 2). Then rival_bench's criterion on the decided row: >= 60% of
the decided games vs town_melon (VOID if fewer than MIN_DECIDED are decided),
>= 90% vs each anchor, the paired external limb as a whole.

    .venv/bin/python -m harness.sixmelon_bench --controls
    .venv/bin/python -m harness.sixmelon_bench --criterion
"""

from __future__ import annotations

import argparse
import os

from harness.cashflow import play  # noqa: F401  -- pinned by the tests
from harness.episode_analysis import _slot
from harness.evolve import DEFAULT_ANCHORS
from harness.external_pool import EXTERNAL_ANCHORS
from harness.fert_bench import units_sold
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

CONTENDER = "six_melon"
CHAMPION = "town_melon"
SEEDS = tuple(range(2522, 2538))
CONTROL_SEED = 2522
CHAMPION_BAR = 0.60
ANCHOR_BAR = 0.90
#: The first wave is cut by the end of this day; at six a tile, ten tiles clear the bar.
EARLY_DAY = 13
EARLY_BAR = 60
LONESPEAR = EXTERNAL_ANCHORS[0]
assert LONESPEAR.startswith("lonespear"), LONESPEAR  # the pool order is the pin (review)


def load_reference():
    from strategies import load
    return load(REFERENCE)


def units_by_day(steps, seat, item, day) -> int:
    """Units of `item` one seat SELLs on steps whose observation day is at most `day`."""
    total = 0
    for t in range(len(steps)):
        slot = _slot(steps, t, seat) or {}
        obs = slot.get("observation") or {}
        if obs.get("day") is None or obs["day"] > day:
            continue
        for order in ((slot.get("action") or {}).get("market") or []):
            if order and order[0] == "SELL" and order[1] == item:
                total += int(order[2])
    return total


def reading(steps, seat) -> dict:
    """One side's melon units sold by the end of EARLY_DAY, and its melon and
    strawberry units over the game."""
    u = units_sold(steps, seat)
    return {"melon_early": units_by_day(steps, seat, "MELON", EARLY_DAY),
            "melon_units": u.get("MELON", 0), "strawberry_units": u.get("STRAWBERRY", 0)}


def mechanism_failures(contender, champion) -> list:
    """Control 2's bars; the names of the ones that did not hold. Strawberry is
    printed, never gated."""
    failed = []
    if contender["melon_early"] < EARLY_BAR or not contender["melon_early"] > champion["melon_early"]:
        failed.append("melon_early")
    if not contender["melon_units"] > champion["melon_units"]:
        failed.append("melon_units")
    return failed


def off_class():
    """Every seam off (twenty), the reference's caps, and the frozen herd ramp."""
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
    ap = argparse.ArgumentParser(description="six_melon: water a ready melon before cutting it, carry eighteen")
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
              f"(declared: melon units by day {EARLY_DAY} >= {EARLY_BAR} and > {CHAMPION}'s, melon units > {CHAMPION}'s; strawberry recorded)  "
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
