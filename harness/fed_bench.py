"""The fed_herd experiment (#270): controls, criterion, census and arm B.

Declared on #270 before any code. Controls first -- identity (every seam off
is the frozen benchmark to the value) and mechanism (no head lost over days
0-16 and at least the champion's head at day 12, both sides of one game); a
failed control is a VOID run (exit 2). Then rival_bench's criterion against
lean_feed, the anchors and the paired externals. `--recorded` plays the
escape census (head lost per side per game on the same seeds) and arm B
(`feed_floor`: lean_feed with a feed-only spend floor); neither is gated.

    .venv/bin/python -m harness.fed_bench --controls
    .venv/bin/python -m harness.fed_bench --criterion
    .venv/bin/python -m harness.fed_bench --recorded
"""

from __future__ import annotations

import argparse
import os
import statistics

from harness.cashflow import play  # noqa: F401  -- pinned by the tests
from harness.evolve import DEFAULT_ANCHORS
from harness.farm_census import animals_placed
from harness.feed_bench import board_on_day
from harness.reserve_bench import MADHUR, PILKWANG, REFERENCE  # noqa: F401  -- pinned by the tests
from harness.rival_bench import (  # noqa: F401  -- pinned by the tests to rival_bench's own
    criterion,
    format_external,
    format_rows,
    paired_external_rows,
)
from harness.sheep_bench import _seam_names

CONTENDER = "fed_herd"
CHAMPION = "lean_feed"
SEEDS = tuple(range(1008, 1024))
CONTROL_SEED = 1008
CHAMPION_BAR = 0.60
ANCHOR_BAR = 0.90
CENSUS_DAYS = range(0, 17)
HEAD_LOST_BAR = 0
HEAD_DAY = 12
ARM_B = "feed_floor"
#: Wheat's anchor price for the floor arm when the market has not been read.
WHEAT_BASE = 25


def load_reference():
    from strategies import load
    return load(REFERENCE)


def head_by_day(steps, seat, days=CENSUS_DAYS) -> list:
    """Placed head on each day's closing board; ``None`` for a day never reached."""
    out = []
    for d in days:
        board = board_on_day(steps, seat, d)
        out.append(None if board is None else sum(animals_placed(board["tiles"]).values()))
    return out


def head_lost(heads) -> int:
    """The sum of day-over-day decreases -- animals that escaped -- skipping unreached days."""
    lost, prev = 0, None
    for h in heads:
        if h is None:
            continue
        if prev is not None and h < prev:
            lost += prev - h
        prev = h
    return lost


def head_reading(steps, seat) -> dict:
    heads = head_by_day(steps, seat, CENSUS_DAYS)
    idx = list(CENSUS_DAYS).index(HEAD_DAY)
    if heads[idx] is None:
        raise ValueError(f"no board for day {HEAD_DAY}: the game ended early")
    return {"lost": head_lost(heads), "head_12": heads[idx], "heads": heads}


def mechanism_failures(contender, champion) -> list:
    failed = []
    if contender["lost"] > HEAD_LOST_BAR:
        failed.append("lost")
    if contender["head_12"] < champion["head_12"]:
        failed.append("head_12")
    return failed


def off_class():
    """The identity control's subject: the contender with every seam off and the reference's caps."""
    from strategies import load
    body = {n: (lambda self, *a, **k: None) for n in _seam_names()}
    body["CAPS"] = load_reference().CAPS
    return type("Off", (load(CONTENDER),), body)


def feed_floor(animals, shed, prices) -> int:
    """Tomorrow's feed shortfall for two feedings, at today's wheat price. No wages."""
    short = max(0, 2 * int(animals or 0) - int((shed or {}).get("WHEAT", 0)))
    return short * int((prices or {}).get("WHEAT", WHEAT_BASE))


def arm_b_class():
    """`lean_feed` with a feed-only spend floor; its shed stock stays one feeding. Never registered."""
    from strategies import load
    return type("FeedFloor", (load(CHAMPION),), {
        "spend_floor": lambda self, day=None, animals=None, shed=None, prices=None:
            feed_floor(animals, shed, prices)})


def census_summary(games) -> dict:
    return {"games": len(games),
            "contender_lost_median": statistics.median(g["contender_lost"] for g in games) if games else None,
            "champion_lost_median": statistics.median(g["champion_lost"] for g in games) if games else None,
            "contender_games_with_escapes": sum(g["contender_lost"] > 0 for g in games),
            "champion_games_with_escapes": sum(g["champion_lost"] > 0 for g in games)}


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
    contender, champion = head_reading(steps, 0), head_reading(steps, 1)
    failed = mechanism_failures(contender, champion)
    out["mechanism"] = {"ok": not failed, "failed": failed, "contender": contender, "champion": champion}
    return out


def run_criterion(seeds=SEEDS):  # pragma: no cover
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    from harness.triage import head_to_head_rate
    champion_row = head_to_head_rate(CONTENDER, CHAMPION, seeds)
    anchor_rows = [head_to_head_rate(CONTENDER, a, seeds) for a in DEFAULT_ANCHORS]
    pairs = paired_external_rows(CONTENDER, CHAMPION, seeds)
    return champion_row, anchor_rows, pairs


def run_census(seeds=SEEDS):  # pragma: no cover
    """Contender vs champion on the seeds, contender seat 0 on even list positions."""
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    from kaggle_environments import make
    from kaggisim.strategy import make_agent
    from strategies import load
    games = []
    for i, seed in enumerate(seeds):
        seat = i % 2
        pair = [make_agent(load(CONTENDER)()), make_agent(load(CHAMPION)())]
        if seat == 1:
            pair.reverse()
        env = make("kaggriculture", configuration={"seed": seed, "episodeSteps": 720})
        env.run(pair)
        games.append({"seed": seed, "seat": seat,
                      "contender_lost": head_lost(head_by_day(env.steps, seat)),
                      "champion_lost": head_lost(head_by_day(env.steps, 1 - seat))})
    return games


def run_recorded(seeds=SEEDS):  # pragma: no cover
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    from harness.triage import head_to_head_rate
    return run_census(seeds), [head_to_head_rate(ARM_B, CHAMPION, seeds, agents=_arm_b_agents(ARM_B))]


def main(argv=None):  # pragma: no cover
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    ap = argparse.ArgumentParser(description="fed_herd: two feedings in the shed")
    ap.add_argument("--controls", action="store_true")
    ap.add_argument("--criterion", action="store_true")
    ap.add_argument("--recorded", action="store_true", help="escape census + arm B (recorded, not gated)")
    args = ap.parse_args(argv)

    if args.recorded:
        games, rows = run_recorded()
        print("escape census (seed, contender seat, contender lost, champion lost): "
              + str([(g["seed"], g["seat"], g["contender_lost"], g["champion_lost"]) for g in games]))
        print(f"census summary: {census_summary(games)}")
        print(format_rows(rows))
        print(f"recorded, not gated: arm B ({ARM_B}: lean_feed with a feed-only spend floor) vs {CHAMPION}")
        return 0

    do_controls = args.controls or not args.criterion
    do_criterion = args.criterion or not args.controls

    if do_controls:
        ctl = run_controls()
        print(f"control identity: {'OK' if ctl['identity']['ok'] else 'FAIL -- RUN VOID'}  {ctl['identity']}")
        c, b = ctl["mechanism"]["contender"], ctl["mechanism"]["champion"]
        print(f"control mechanism: {'OK' if ctl['mechanism']['ok'] else 'FAIL -- RUN VOID'}  "
              f"(declared: head lost days 0-16 <= {HEAD_LOST_BAR}, head at day {HEAD_DAY} >= lean_feed's)  "
              f"contender lost {c['lost']} head_12 {c['head_12']} heads {c['heads']}  "
              f"lean_feed lost {b['lost']} head_12 {b['head_12']} heads {b['heads']}  "
              f"failed={ctl['mechanism']['failed'] or 'none'}")
        if not all(r["ok"] for r in ctl.values()):
            print("a control failed: the run is VOID and the recorded arms are NOT scored")
            return 2

    if do_criterion:
        champion_row, anchor_rows, pairs = run_criterion()
        print(format_rows([champion_row] + anchor_rows))
        print(format_external(pairs))
        v = criterion(champion_row, anchor_rows, CHAMPION_BAR, ANCHOR_BAR, external_pairs=pairs)
        print(f"champion {v['champion_rate']:.1%} (bar {CHAMPION_BAR:.0%}); failing limbs: "
              f"{v['failing'] or 'none'} -> {'PROMOTE' if v['passed'] else 'REJECTED'}; "
              f"madhur paired row (contender, champion): {v['external'].get(MADHUR)}; "
              f"pilkwang: {v['external'].get(PILKWANG)}")
        return 0 if v["passed"] else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
