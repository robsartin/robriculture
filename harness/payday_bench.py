"""The payday_herd experiment (#274): controls, criterion, census and arm B.

Declared on #274 before any code. Controls first -- identity (every seam off
and the frozen ramp is the frozen benchmark to the value) and mechanism (no
head lost over days 0-16, ten hands on day 10, at least the champion's head
at day 16, both sides of one game); a failed control is a VOID run (exit 2).
Then rival_bench's criterion. `--recorded` plays the escape census and arm B
(`hold6`: the herd held at six until day 12); neither is gated.

    .venv/bin/python -m harness.payday_bench --controls
    .venv/bin/python -m harness.payday_bench --criterion
    .venv/bin/python -m harness.payday_bench --recorded
"""

from __future__ import annotations

import argparse
import os

from harness.cashflow import play  # noqa: F401  -- pinned by the tests
from harness.evolve import DEFAULT_ANCHORS
from harness.fed_bench import census_summary, head_by_day, head_lost
from harness.feed_bench import hands_on_day
from harness.reserve_bench import MADHUR, PILKWANG, REFERENCE  # noqa: F401  -- pinned by the tests
from harness.rival_bench import (  # noqa: F401  -- pinned by the tests to rival_bench's own
    criterion,
    format_external,
    format_rows,
    paired_external_rows,
)
from harness.sheep_bench import _seam_names
from strategies import field_pace as fp

CONTENDER = "payday_herd"
CHAMPION = "lean_feed"
SEEDS = tuple(range(1040, 1056))
CONTROL_SEED = 1040
CHAMPION_BAR = 0.60
ANCHOR_BAR = 0.90
CENSUS_DAYS = range(0, 17)
HEAD_LOST_BAR = 0
CREW_DAY = 10
CREW_BAR = 10
HEAD_DAY = 16
ARM_B = "hold6"
HOLD6_RAMP = ((0, 4), (6, 6), (12, 13))


def load_reference():
    from strategies import load
    return load(REFERENCE)


def reading(steps, seat) -> dict:
    """One side's head lost over the census days, crew on CREW_DAY, head at HEAD_DAY."""
    heads = head_by_day(steps, seat, CENSUS_DAYS)
    idx = list(CENSUS_DAYS).index(HEAD_DAY)
    if heads[idx] is None:
        raise ValueError(f"no board for day {HEAD_DAY}: the game ended early")
    return {"lost": head_lost(heads), "hands_10": hands_on_day(steps, seat, CREW_DAY),
            "head_16": heads[idx], "heads": heads}


def mechanism_failures(contender, champion) -> list:
    failed = []
    if contender["lost"] > HEAD_LOST_BAR:
        failed.append("lost")
    if (contender["hands_10"] or 0) < CREW_BAR:
        failed.append("hands_10")
    if contender["head_16"] < champion["head_16"]:
        failed.append("head_16")
    return failed


def off_class():
    """Every seam off, the reference's caps, and the frozen ramp."""
    from strategies import load
    body = {n: (lambda self, *a, **k: None) for n in _seam_names()}
    body["CAPS"] = load_reference().CAPS
    body["HERD_RAMP_F"] = fp.HERD_RAMP_F
    return type("Off", (load(CONTENDER),), body)


def arm_b_class():
    """`lean_feed` held at six head until day 12. Never registered."""
    from strategies import load
    return type("Hold6", (load(CHAMPION),), {"HERD_RAMP_F": HOLD6_RAMP})


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
                      "contender_lost": head_lost(head_by_day(env.steps, seat, CENSUS_DAYS)),
                      "champion_lost": head_lost(head_by_day(env.steps, 1 - seat, CENSUS_DAYS))})
    return games


def run_recorded(seeds=SEEDS):  # pragma: no cover
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    from harness.triage import head_to_head_rate
    return run_census(seeds), [head_to_head_rate(ARM_B, CHAMPION, seeds, agents=_arm_b_agents(ARM_B))]


def main(argv=None):  # pragma: no cover
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    ap = argparse.ArgumentParser(description="payday_herd: the herd waits for payday")
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
        print(f"recorded, not gated: arm B ({ARM_B}: lean_feed held at six head until day 12) vs {CHAMPION}")
        return 0

    do_controls = args.controls or not args.criterion
    do_criterion = args.criterion or not args.controls

    if do_controls:
        ctl = run_controls()
        print(f"control identity: {'OK' if ctl['identity']['ok'] else 'FAIL -- RUN VOID'}  {ctl['identity']}")
        c, b = ctl["mechanism"]["contender"], ctl["mechanism"]["champion"]
        print(f"control mechanism: {'OK' if ctl['mechanism']['ok'] else 'FAIL -- RUN VOID'}  "
              f"(declared: head lost days 0-16 <= {HEAD_LOST_BAR}, hands on day {CREW_DAY} >= {CREW_BAR}, "
              f"head at day {HEAD_DAY} >= lean_feed's)  contender lost {c['lost']} hands_10 {c['hands_10']} "
              f"head_16 {c['head_16']} heads {c['heads']}  lean_feed lost {b['lost']} hands_10 {b['hands_10']} "
              f"head_16 {b['head_16']} heads {b['heads']}  failed={ctl['mechanism']['failed'] or 'none'}")
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
