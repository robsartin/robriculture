"""The town_herd experiment (#302): controls, criterion, arm B.

Declared on #302 before any code. Controls first -- identity (every seam off
is the frozen benchmark to the value) and mechanism (on seed 1174, whose town
draws two yarn stores by day 9, the contender holds more head of the kind the
day-12 town favours than four_at_eight at day 14 and earns more in that
product); a failed control is a VOID run (exit 2). Then rival_bench's
criterion against four_at_eight, the anchors and the paired externals under
the 2026-09-15 amended limb. Arm B (`shop_count`: the same rule ignoring
owned head) is recorded, never gated. The day-12 shops and head lost to
escapes are printed, never gated.

    .venv/bin/python -m harness.town_bench --controls
    .venv/bin/python -m harness.town_bench --criterion
    .venv/bin/python -m harness.town_bench --recorded
"""

from __future__ import annotations

import argparse
import os

from harness.cashflow import play  # noqa: F401  -- pinned by the tests
from harness.episode_analysis import _slot, decompose
from harness.evolve import DEFAULT_ANCHORS
from harness.external_pool import EXTERNAL_ANCHORS
from harness.farm_census import animals_placed
from harness.feed_bench import board_on_day
from harness.four8_bench import escapes
from harness.reserve_bench import MADHUR, PILKWANG, REFERENCE  # noqa: F401  -- pinned by the tests
from harness.rival_bench import (  # noqa: F401  -- pinned by the tests to rival_bench's own
    criterion,
    format_external,
    format_rows,
    paired_external_rows,
)
from harness.sheep_bench import _seam_names
from strategies import field_pace as fp
from strategies import town_herd as th

CONTENDER = "town_herd"
CHAMPION = "four_at_eight"
SEEDS = tuple(range(1171, 1187))
CONTROL_SEED = 1174
CHAMPION_BAR = 0.60
ANCHOR_BAR = 0.90
KIND_DAY = 12
HEAD_DAY = 14
ARM_B = "shop_count"
#: The reading keys the mechanism bars compare, by the favoured kind.
HEAD_KEY = {"COW": "cows_14", "SHEEP": "sheep_14"}
PRODUCT_KEY = {"COW": "milk", "SHEEP": "wool"}
LONESPEAR = EXTERNAL_ANCHORS[1]
assert LONESPEAR.startswith("lonespear"), LONESPEAR  # the pool order is the pin (review)


def load_reference():
    from strategies import load
    return load(REFERENCE)


def town_on_day(steps, seat, day):
    """The town's unlocked shops on the last observation of `day`; None if unreached."""
    shops = None
    for t in range(len(steps)):
        obs = (_slot(steps, t, seat) or {}).get("observation") or {}
        if obs.get("day") != day:
            continue
        shops = list((obs.get("town") or {}).get("unlocked_shops") or [])
    return shops


def reading(steps, seat) -> dict:
    """One side's favoured kind from the day-12 town, its head at day 14, and
    its milk and wool revenue."""
    shops = town_on_day(steps, seat, KIND_DAY)
    if shops is None:
        raise ValueError(f"no observation for day {KIND_DAY}: the game ended early")
    board = board_on_day(steps, seat, HEAD_DAY)
    if board is None:
        raise ValueError(f"no board for day {HEAD_DAY}: the game ended early")
    placed = animals_placed(board["tiles"])
    rev = decompose(steps, seat)["revenue"]
    return {"favoured": th.town_kind(shops, 0, 0), "shops_12": tuple(shops),
            "cows_14": placed.get("COW", 0), "sheep_14": placed.get("SHEEP", 0),
            "milk": rev.get("MILK", 0), "wool": rev.get("WOOL", 0)}


def mechanism_failures(contender, champion) -> list:
    """Control 2's bars; the names of the ones that did not hold. A town that
    favours neither kind fails the control as `favoured`."""
    kind = contender["favoured"]
    if kind is None:
        return ["favoured"]
    return [key for key in (HEAD_KEY[kind], PRODUCT_KEY[kind]) if not contender[key] > champion[key]]


def off_class():
    """Every seam off (sixteen), the reference's caps, and the frozen herd ramp."""
    from strategies import load
    body = {n: (lambda self, *a, **k: None) for n in _seam_names()}
    body["CAPS"] = load_reference().CAPS
    body["HERD_RAMP_F"] = fp.HERD_RAMP_F
    return type("Off", (load(CONTENDER),), body)


def arm_b_class():
    """`town_herd` with owned head ignored: the kind with the larger shop
    capacity, COW on a tie. Never registered."""
    from strategies import load
    return type("ShopCount", (load(CONTENDER),), {"owned": lambda self, obs: (0, 0)})


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
    ap = argparse.ArgumentParser(description="town_herd: the animal kind from the town's shops")
    ap.add_argument("--controls", action="store_true")
    ap.add_argument("--criterion", action="store_true")
    ap.add_argument("--recorded", action="store_true", help="arm B (recorded, not gated)")
    args = ap.parse_args(argv)

    if args.recorded:
        print(format_rows(run_recorded()))
        print(f"recorded, not gated: arm B ({ARM_B}: the town's rule ignoring owned head) vs {CHAMPION}")
        return 0

    do_controls = args.controls or not args.criterion
    do_criterion = args.criterion or not args.controls

    if do_controls:
        ctl = run_controls()
        print(f"control identity: {'OK' if ctl['identity']['ok'] else 'FAIL -- RUN VOID'}  {ctl['identity']}")
        c, b = ctl["mechanism"]["contender"], ctl["mechanism"]["champion"]
        print(f"control mechanism: {'OK' if ctl['mechanism']['ok'] else 'FAIL -- RUN VOID'}  "
              f"(declared: the day-{KIND_DAY} town favours a kind; the contender's head of it at day {HEAD_DAY} "
              f"> {CHAMPION}'s and its revenue in that product > {CHAMPION}'s)  "
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
