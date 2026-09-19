"""The four_herders experiment (#289): controls, criterion, arm B.

Declared on #289 before any code. Controls first -- identity (every seam off,
sixteen of them, is the frozen benchmark to the value) and mechanism (placed
head at day 14 at least PLACED_BAR and at least the champion's, milk units
above the champion's, both sides of one game); a failed control is a VOID run
(exit 2). Then rival_bench's criterion. Arm B (`from_eight`) is recorded,
never gated. Animals pending in the shed and the day-16 planted count are
printed, never gated.

    .venv/bin/python -m harness.fourth_bench --controls
    .venv/bin/python -m harness.fourth_bench --criterion
    .venv/bin/python -m harness.fourth_bench --recorded
"""

from __future__ import annotations

import argparse
import os

from harness.cashflow import play  # noqa: F401  -- pinned by the tests
from harness.episode_analysis import _slot
from harness.evolve import DEFAULT_ANCHORS
from harness.external_pool import ANCHORS_2026_09_07
from harness.farm_census import animals_placed, planted_by_crop
from harness.feed_bench import board_on_day
from harness.fert_bench import units_sold
from harness.reserve_bench import MADHUR, PILKWANG, REFERENCE  # noqa: F401  -- pinned by the tests
from harness.rival_bench import (  # noqa: F401  -- pinned by the tests to rival_bench's own
    criterion,
    format_external,
    format_rows,
    paired_external_rows,
)
from harness.sheep_bench import _seam_names
from strategies import field_pace as fp

CONTENDER = "four_herders"
CHAMPION = "ten_melon"
SEEDS = tuple(range(1122, 1138))
CONTROL_SEED = 1122
CHAMPION_BAR = 0.60
ANCHOR_BAR = 0.90
PLACED_DAY = 14
PLACED_BAR = 12
PENDING_DAYS = (14, 20)
PLANTED_DAY = 16
ARM_B = "from_eight"
ARM_B_FROM = 8
LONESPEAR = ANCHORS_2026_09_07[1]
assert LONESPEAR.startswith("lonespear"), LONESPEAR


def load_reference():
    from strategies import load
    return load(REFERENCE)


def pending_at(steps, seat, day):
    """COW + SHEEP in the seat's shed on the last observation of `day`; None if unreached."""
    pending = None
    for t in range(len(steps)):
        obs = (_slot(steps, t, seat) or {}).get("observation") or {}
        if obs.get("day") != day:
            continue
        shed = (obs.get("private") or {}).get("shed") or {}
        pending = int(shed.get("COW", 0) or 0) + int(shed.get("SHEEP", 0) or 0)
    return pending


def reading(steps, seat) -> dict:
    b14 = board_on_day(steps, seat, PLACED_DAY)
    if b14 is None:
        raise ValueError(f"no board for day {PLACED_DAY}: the game ended early")
    b16 = board_on_day(steps, seat, PLANTED_DAY)
    return {"placed_14": sum(animals_placed(b14["tiles"]).values()),
            "milk": units_sold(steps, seat).get("MILK", 0),
            "pending": {d: pending_at(steps, seat, d) for d in PENDING_DAYS},
            "planted_16": None if b16 is None else sum(planted_by_crop(b16["tiles"]).values())}


def mechanism_failures(contender, champion) -> list:
    failed = []
    if contender["placed_14"] < PLACED_BAR or contender["placed_14"] < champion["placed_14"]:
        failed.append("placed_14")
    if contender["milk"] <= champion["milk"]:
        failed.append("milk")
    return failed


def off_class():
    """Every seam off (sixteen), the reference's caps, and the frozen herd ramp."""
    from strategies import load
    body = {n: (lambda self, *a, **k: None) for n in _seam_names()}
    body["CAPS"] = load_reference().CAPS
    body["HERD_RAMP_F"] = fp.HERD_RAMP_F
    return type("Off", (load(CONTENDER),), body)


def arm_b_class():
    """`four_herders` with the fourth herder from day eight. Never registered."""
    from strategies import load
    return type("FromEight", (load(CONTENDER),), {"FOURTH_DAY": ARM_B_FROM})


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


def run_recorded(seeds=SEEDS):  # pragma: no cover
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    from harness.triage import head_to_head_rate
    return [head_to_head_rate(ARM_B, CHAMPION, seeds, agents=_arm_b_agents(ARM_B))]


def main(argv=None):  # pragma: no cover
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    ap = argparse.ArgumentParser(description="four_herders: a fourth herder from day 12")
    ap.add_argument("--controls", action="store_true")
    ap.add_argument("--criterion", action="store_true")
    ap.add_argument("--recorded", action="store_true", help="arm B (recorded, not gated)")
    args = ap.parse_args(argv)

    if args.recorded:
        print(format_rows(run_recorded()))
        print(f"recorded, not gated: arm B ({ARM_B}: the fourth herder from day {ARM_B_FROM}) vs {CHAMPION}")
        return 0

    do_controls = args.controls or not args.criterion
    do_criterion = args.criterion or not args.controls

    if do_controls:
        ctl = run_controls()
        print(f"control identity: {'OK' if ctl['identity']['ok'] else 'FAIL -- RUN VOID'}  {ctl['identity']}")
        c, b = ctl["mechanism"]["contender"], ctl["mechanism"]["champion"]
        print(f"control mechanism: {'OK' if ctl['mechanism']['ok'] else 'FAIL -- RUN VOID'}  "
              f"(declared: placed at day {PLACED_DAY} >= {PLACED_BAR} and >= champion's, milk > champion's)  "
              f"contender {c}  {CHAMPION} {b}  failed={ctl['mechanism']['failed'] or 'none'}")
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
              f"paired rows (contender, champion): madhur {v['external'].get(MADHUR)}, "
              f"pilkwang {v['external'].get(PILKWANG)}, lonespear {v['external'].get(LONESPEAR)}")
        return 0 if v["passed"] else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
