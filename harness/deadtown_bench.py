"""The town_melon experiment (#337): screen, controls and criterion -- judged
under ADR-0007 as amended 2026-09-16, 2026-09-20 and 2026-09-21, corrected
2026-09-17.

Declared on #337 before any code. The seeds are screened (2026-09-21): the
first SEED_COUNT seeds at or above SCAN_FROM whose day-9 town under the
champion's own self-play has no strawberry shop; LIVE_SEED is the first
whose town has one. Controls first -- identity (every seam off, eighteen, is
the frozen benchmark to the value), mechanism (melon units sold at least
MELON_UNITS_BAR and more than the champion's, fewer strawberry units, and
the contender's first divergence from the champion's own stream at or after
day 9) and live identity (on LIVE_SEED the contender's stream is the
champion's own); a failed control is a VOID run (exit 2). Then rival_bench's
criterion on the decided row over the screened seeds: >= 60% of the decided
games vs second_melon (VOID if fewer than MIN_DECIDED are decided), >= 90% vs
each anchor, the paired external limb as a whole.

    .venv/bin/python -m harness.deadtown_bench --scan
    .venv/bin/python -m harness.deadtown_bench --controls --seeds A,B,... --live-seed L
    .venv/bin/python -m harness.deadtown_bench --criterion --seeds A,B,... --live-seed L

Without --seeds/--live-seed the run scans first and prints the screen.
"""

from __future__ import annotations

import argparse
import itertools
import os

from harness.cashflow import play  # noqa: F401  -- pinned by the tests
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
    seat_actions,
)
from harness.sheep_bench import _seam_names
from harness.sixteend_bench import first_divergence
from harness.town_bench import town_on_day
from strategies import field_pace as fp
from strategies import field_rival as fr
from strategies.town_melon import DEAD_DAY, straw_dead

CONTENDER = "town_melon"
CHAMPION = "second_melon"
CHAMPION_BAR = 0.60
ANCHOR_BAR = 0.90
SCAN_FROM = 2359
SEED_COUNT = 16
MELON_UNITS_BAR = 100
#: The first step of DEAD_DAY: the contender may not diverge before it.
DEAD_STEP = DEAD_DAY * fr.TURNS_PER_DAY
LONESPEAR = EXTERNAL_ANCHORS[0]
assert LONESPEAR.startswith("lonespear"), LONESPEAR  # the pool order is the pin (review)


def load_reference():
    from strategies import load
    return load(REFERENCE)


# --- the screen ---------------------------------------------------------------

def screen(seeds, dead_of, count) -> dict:
    """The first `count` seeds of `seeds`, in order, for which `dead_of(seed)`
    is true; the first for which it is false; and how many were read.
    Reads every seed when fewer than `count` are dead."""
    kept, live, read = [], None, 0
    for seed in seeds:
        read += 1
        if dead_of(seed):
            kept.append(seed)
            if len(kept) == count:
                break
        elif live is None:
            live = seed
    return {"seeds": tuple(kept), "live_seed": live, "read": read}


def _own_steps(seed):  # pragma: no cover
    from harness.rival_bench import _default_steps
    from harness.triage import _default_agents
    agents = _default_agents()
    return _default_steps()(agents(CHAMPION), agents(CHAMPION), seed)


def scan(start=SCAN_FROM, count=SEED_COUNT):  # pragma: no cover
    """The screen, live: the champion against itself from `start` in seed
    order, the day-DEAD_DAY town read from seat 0."""
    def dead_of(seed):
        shops = town_on_day(_own_steps(seed), 0, DEAD_DAY)
        if shops is None:
            raise ValueError(f"seed {seed}: no observation for day {DEAD_DAY}")
        return straw_dead(shops)
    return screen(itertools.count(start), dead_of, count)


# --- readings ---------------------------------------------------------------

def reading(steps, seat) -> dict:
    """One side's melon and strawberry units sold."""
    u = units_sold(steps, seat)
    return {"melon_units": u.get("MELON", 0), "strawberry_units": u.get("STRAWBERRY", 0)}


def mechanism_failures(contender, champion, *, first_diff) -> list:
    """Control 2's bars; the names of the ones that did not hold."""
    failed = []
    if contender["melon_units"] < MELON_UNITS_BAR or not contender["melon_units"] > champion["melon_units"]:
        failed.append("melon_units")
    if not contender["strawberry_units"] < champion["strawberry_units"]:
        failed.append("strawberry_units")
    if first_diff is None or first_diff < DEAD_STEP:
        failed.append("first_divergence")
    return failed


def live_failures(ours, own) -> list:
    """Control 3: the contender's seat-0 stream equals the champion's own."""
    return [] if seat_actions(ours, 0) == seat_actions(own, 0) else ["live_identity"]


def off_class():
    """Every seam off (eighteen), the reference's caps, and the frozen herd ramp."""
    from strategies import load
    body = {n: (lambda self, *a, **k: None) for n in _seam_names()}
    body["CAPS"] = load_reference().CAPS
    body["HERD_RAMP_F"] = fp.HERD_RAMP_F
    return type("Off", (load(CONTENDER),), body)


# --- live games -------------------------------------------------------------

def run_controls(control_seed, live_seed):  # pragma: no cover
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    from harness.tournament import play_rewards
    from kaggisim.strategy import make_agent
    from strategies import load
    out = {}
    off = off_class()
    base = play_rewards(make_agent(load(REFERENCE)()), make_agent(load(REFERENCE)()), control_seed)
    got = play_rewards(make_agent(off()), make_agent(load(REFERENCE)()), control_seed)
    precondition_ok = base[0] > 0
    out["identity"] = {"ok": got == base and precondition_ok, "base": base, "got": got,
                       "precondition_ok": precondition_ok}
    steps = play(CONTENDER, CHAMPION, control_seed)
    own = _own_steps(control_seed)
    contender, champion = reading(steps, 0), reading(steps, 1)
    first_diff = first_divergence(steps, own, 0)
    failed = mechanism_failures(contender, champion, first_diff=first_diff)
    out["mechanism"] = {"ok": not failed, "failed": failed, "first_diff": first_diff,
                        "contender": contender, "champion": champion,
                        "town": town_on_day(steps, 0, DEAD_DAY)}
    live_steps = play(CONTENDER, CHAMPION, live_seed)
    failed = live_failures(live_steps, _own_steps(live_seed))
    out["live"] = {"ok": not failed, "failed": failed, "town": town_on_day(live_steps, 0, DEAD_DAY)}
    return out


def run_criterion(seeds):  # pragma: no cover
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    from harness.triage import head_to_head_rate
    champion_row = decided_row(CONTENDER, CHAMPION, seeds)
    anchor_rows = [head_to_head_rate(CONTENDER, a, seeds) for a in DEFAULT_ANCHORS]
    pairs = paired_external_rows(CONTENDER, CHAMPION, seeds)
    return champion_row, anchor_rows, pairs


def main(argv=None):  # pragma: no cover
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    ap = argparse.ArgumentParser(description="town_melon: melon from day 9 while the town has no strawberry shop")
    ap.add_argument("--scan", action="store_true")
    ap.add_argument("--controls", action="store_true")
    ap.add_argument("--criterion", action="store_true")
    ap.add_argument("--seeds", help="the screened seeds, comma-separated (from --scan)")
    ap.add_argument("--live-seed", type=int, help="the first live seed (from --scan)")
    args = ap.parse_args(argv)

    if args.scan or not (args.seeds and args.live_seed):
        got = scan()
        print(f"screen from {SCAN_FROM}: read {got['read']} seeds; dead at day {DEAD_DAY}: "
              f"{','.join(str(s) for s in got['seeds'])}; live seed {got['live_seed']}")
        if len(got["seeds"]) < SEED_COUNT or got["live_seed"] is None:
            print("the screen came up short: the run is VOID")
            return 2
        seeds, live_seed = got["seeds"], got["live_seed"]
        if args.scan and not (args.controls or args.criterion):
            return 0
    else:
        seeds = tuple(int(s) for s in args.seeds.split(","))
        live_seed = args.live_seed

    do_controls = args.controls or not args.criterion
    do_criterion = args.criterion or not args.controls

    if do_controls:
        ctl = run_controls(seeds[0], live_seed)
        print(f"control identity: {'OK' if ctl['identity']['ok'] else 'FAIL -- RUN VOID'}  {ctl['identity']}")
        m = ctl["mechanism"]
        print(f"control mechanism: {'OK' if m['ok'] else 'FAIL -- RUN VOID'}  "
              f"(declared: melon units >= {MELON_UNITS_BAR} and > {CHAMPION}'s, strawberry units < {CHAMPION}'s, "
              f"first divergence >= step {DEAD_STEP})  contender {m['contender']}  {CHAMPION} {m['champion']}  "
              f"first_diff={m['first_diff']}  town@{DEAD_DAY}={m['town']}  failed={m['failed'] or 'none'}")
        lv = ctl["live"]
        print(f"control live identity: {'OK' if lv['ok'] else 'FAIL -- RUN VOID'}  seed {live_seed} town@{DEAD_DAY}={lv['town']}  failed={lv['failed'] or 'none'}")
        if not all(r["ok"] for r in ctl.values()):
            print("a control failed: the run is VOID")
            return 2

    if do_criterion:
        champion_row, anchor_rows, pairs = run_criterion(seeds)
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
