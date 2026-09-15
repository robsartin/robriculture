"""fert_eight's second run (#286): controls, criterion, arm B — the planting bar dropped.

#284 VOIDed on a bar that read the closing board of the lever's first day.
The lever's price -- a planting delay of about two days during the NE
expansion, level by day 13 -- is printed here by day and judged by the
criterion; the three mechanism bars are the lever's own. Seeds are #284's
declared-unplayed 1105-1119 plus 1120 as the control seed.

    .venv/bin/python -m harness.eight2_bench --controls
    .venv/bin/python -m harness.eight2_bench --criterion
    .venv/bin/python -m harness.eight2_bench --recorded
"""

from __future__ import annotations

import argparse
import os

from harness.cashflow import play  # noqa: F401  -- pinned by the tests
from harness.eight_bench import (  # noqa: F401  -- the same contender, the same stubs
    ARM_B,
    ARM_B_FROM,
    CHAMPION,
    CONTENDER,
    LONESPEAR,
    _arm_b_agents,
    arm_b_class,
    load_reference,
    off_class,
)
from harness.evolve import DEFAULT_ANCHORS
from harness.farm_census import planted_by_crop
from harness.feed_bench import board_on_day
from harness.fert_bench import action_counts, units_sold
from harness.reserve_bench import MADHUR, PILKWANG, REFERENCE  # noqa: F401  -- pinned by the tests
from harness.rival_bench import (  # noqa: F401  -- pinned by the tests to rival_bench's own
    criterion,
    format_external,
    format_rows,
    paired_external_rows,
)
from harness.six_bench import dawn_cash

SEEDS = tuple(range(1105, 1121))
CONTROL_SEED = 1120
CHAMPION_BAR = 0.60
ANCHOR_BAR = 0.90
FERTILIZE_BAR = 100
STRAWBERRY_FACTOR = 1.5
EARLY_DAYS = range(1, 8)
PLANT_DAYS = range(6, 14)


def reading(steps, seat) -> dict:
    """The three mechanism readings plus the planting by day, printed never gated."""
    planted = []
    for d in PLANT_DAYS:
        board = board_on_day(steps, seat, d)
        if board is None:
            raise ValueError(f"no board for day {d}: the game ended early")
        planted.append(sum(planted_by_crop(board["tiles"]).values()))
    a, u = action_counts(steps, seat), units_sold(steps, seat)
    return {"fertilize": a.get("FERTILIZE", 0), "strawberry": u.get("STRAWBERRY", 0),
            "melon": u.get("MELON", 0), "dawn_1_7": dawn_cash(steps, seat, EARLY_DAYS),
            "planted": planted}


def mechanism_failures(contender, champion) -> list:
    failed = []
    if contender["fertilize"] < FERTILIZE_BAR:
        failed.append("fertilize")
    if contender["strawberry"] < STRAWBERRY_FACTOR * champion["strawberry"]:
        failed.append("strawberry")
    if contender["dawn_1_7"] != champion["dawn_1_7"]:
        failed.append("dawn_1_7")
    return failed


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
    ap = argparse.ArgumentParser(description="fert_eight, second run: the planting bar dropped")
    ap.add_argument("--controls", action="store_true")
    ap.add_argument("--criterion", action="store_true")
    ap.add_argument("--recorded", action="store_true", help="arm B (recorded, not gated)")
    args = ap.parse_args(argv)

    if args.recorded:
        print(format_rows(run_recorded()))
        print(f"recorded, not gated: arm B ({ARM_B}: the same from day {ARM_B_FROM}) vs {CHAMPION}")
        return 0

    do_controls = args.controls or not args.criterion
    do_criterion = args.criterion or not args.controls

    if do_controls:
        ctl = run_controls()
        print(f"control identity: {'OK' if ctl['identity']['ok'] else 'FAIL -- RUN VOID'}  {ctl['identity']}")
        c, b = ctl["mechanism"]["contender"], ctl["mechanism"]["champion"]
        print(f"control mechanism: {'OK' if ctl['mechanism']['ok'] else 'FAIL -- RUN VOID'}  "
              f"(declared: FERTILIZE >= {FERTILIZE_BAR}, strawberry >= {STRAWBERRY_FACTOR} x champion's, "
              f"dawn cash days 1-7 == champion's)  contender {c}  {CHAMPION} {b}  failed={ctl['mechanism']['failed'] or 'none'}")
        print(f"printed, not gated: planted by day {list(PLANT_DAYS)}: contender {c['planted']}  {CHAMPION} {b['planted']}; "
              f"melon {c['melon']} vs {b['melon']}")
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
