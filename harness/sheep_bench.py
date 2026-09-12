"""The sheep_first experiment (#268): controls, criterion, arm B.

Declared on #268 before any code. Controls first -- identity (every seam off
is the frozen benchmark to the value) and mechanism (four sheep by day 8, six
by day 16, more wool than lean_feed in the same game); a failed control is a
VOID run (exit 2). Then rival_bench's criterion against lean_feed, the anchors
and the paired externals; the lonespear and pilkwang pairs -- the archetype
this contender exists for -- are printed whatever the verdict. Arm B
(`drop_rule`: lean_feed with the rival-sheep rule removed and no sheep target)
is recorded, never gated.

    .venv/bin/python -m harness.sheep_bench --controls
    .venv/bin/python -m harness.sheep_bench --criterion
    .venv/bin/python -m harness.sheep_bench --recorded
"""

from __future__ import annotations

import argparse
import os

from harness.cashflow import play  # noqa: F401  -- pinned by the tests
from harness.episode_analysis import decompose
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
from strategies import field_rival as fr

CONTENDER = "sheep_first"
CHAMPION = "lean_feed"
SEEDS = tuple(range(992, 1008))
CONTROL_SEED = 992
CHAMPION_BAR = 0.60
ANCHOR_BAR = 0.90
ARM_B = "drop_rule"
SHEEP_DAY = 8
SHEEP_BAR = 4
SHEEP_DAY_16 = 16
SHEEP_BAR_16 = 6
LONESPEAR = "lonespear_kaggriculture_v21"


def load_reference():
    from strategies import load
    return load(REFERENCE)


def sheep_reading(steps, seat) -> dict:
    """One side's sheep at day 8 and 16, cows at 16, and its wool and milk revenue."""
    boards = {d: board_on_day(steps, seat, d) for d in (SHEEP_DAY, SHEEP_DAY_16)}
    missing = [d for d, b in boards.items() if b is None]
    if missing:
        raise ValueError(f"no board for day {missing[0]}: the game ended early")
    a8 = animals_placed(boards[SHEEP_DAY]["tiles"])
    a16 = animals_placed(boards[SHEEP_DAY_16]["tiles"])
    rev = decompose(steps, seat)["revenue"]
    return {"sheep_8": a8.get("SHEEP", 0), "sheep_16": a16.get("SHEEP", 0), "cows_16": a16.get("COW", 0),
            "wool": rev.get("WOOL", 0), "milk": rev.get("MILK", 0)}


def mechanism_failures(contender, champion) -> list:
    """Control 2's bars; the names of the ones that did not hold."""
    failed = []
    if contender["sheep_8"] < SHEEP_BAR:
        failed.append("sheep_8")
    if contender["sheep_16"] < SHEEP_BAR_16:
        failed.append("sheep_16")
    if not contender["wool"] > champion["wool"]:
        failed.append("wool")
    return failed


def _seam_names():
    """Every seam on the frozen benchmark: a public method whose docstring says so."""
    return [n for n in dir(fr.FieldRivalStrategy)
            if callable(getattr(fr.FieldRivalStrategy, n)) and not n.startswith("_") and n != "act"
            and getattr(fr.FieldRivalStrategy, n).__doc__
            and "seam" in getattr(fr.FieldRivalStrategy, n).__doc__.lower()]


def off_class():
    """The identity control's subject: the contender with every seam switched
    off and the reference's caps. Derived from the seam list so a seam added
    after this bench was written cannot be left on."""
    from strategies import load
    body = {n: (lambda self, *a, **k: None) for n in _seam_names()}
    body["CAPS"] = load_reference().CAPS
    return type("Off", (load(CONTENDER),), body)


def arm_b_class():
    """`lean_feed` with the rival-sheep rule removed: the frozen mix, no target. Never registered."""
    from strategies import load
    return type("DropRule", (load(CHAMPION),), {"herd_preference": lambda self, obs: None})


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
    contender, champion = sheep_reading(steps, 0), sheep_reading(steps, 1)
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


def run_recorded(seeds=SEEDS):  # pragma: no cover
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    from harness.triage import head_to_head_rate
    return [head_to_head_rate(ARM_B, CHAMPION, seeds, agents=_arm_b_agents(ARM_B))]


def main(argv=None):  # pragma: no cover
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    ap = argparse.ArgumentParser(description="sheep_first: six sheep, bought first")
    ap.add_argument("--controls", action="store_true")
    ap.add_argument("--criterion", action="store_true")
    ap.add_argument("--recorded", action="store_true", help="arm B (recorded, not gated)")
    args = ap.parse_args(argv)

    if args.recorded:
        print(format_rows(run_recorded()))
        print(f"recorded, not gated: arm B ({ARM_B}: lean_feed without the rival-sheep rule) vs {CHAMPION}")
        return 0

    do_controls = args.controls or not args.criterion
    do_criterion = args.criterion or not args.controls

    if do_controls:
        ctl = run_controls()
        print(f"control identity: {'OK' if ctl['identity']['ok'] else 'FAIL -- RUN VOID'}  {ctl['identity']}")
        c, b = ctl["mechanism"]["contender"], ctl["mechanism"]["champion"]
        print(f"control mechanism: {'OK' if ctl['mechanism']['ok'] else 'FAIL -- RUN VOID'}  "
              f"(declared: sheep at day {SHEEP_DAY} >= {SHEEP_BAR}, at day {SHEEP_DAY_16} >= {SHEEP_BAR_16}, "
              f"wool > lean_feed's)  contender {c}  lean_feed {b}  failed={ctl['mechanism']['failed'] or 'none'}")
        if not all(r["ok"] for r in ctl.values()):
            print("a control failed: the run is VOID and arm B is NOT scored")
            return 2

    if do_criterion:
        champion_row, anchor_rows, pairs = run_criterion()
        print(format_rows([champion_row] + anchor_rows))
        print(format_external(pairs))
        v = criterion(champion_row, anchor_rows, CHAMPION_BAR, ANCHOR_BAR, external_pairs=pairs)
        print(f"champion {v['champion_rate']:.1%} (bar {CHAMPION_BAR:.0%}); failing limbs: "
              f"{v['failing'] or 'none'} -> {'PROMOTE' if v['passed'] else 'REJECTED'}; "
              f"archetype pairs (contender, champion): lonespear {v['external'].get(LONESPEAR)}, "
              f"pilkwang {v['external'].get(PILKWANG)}; madhur {v['external'].get(MADHUR)}")
        return 0 if v["passed"] else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
