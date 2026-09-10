"""dawn_reserve: does keeping back dawn's wages and the herd's feed hold the crew, the herd and the field?

    python -m harness.reserve_bench --controls     # identity, crew and head at day 8, the paired crop line
    python -m harness.reserve_bench --criterion    # 16 seeds: champion, anchors, the external limb
    python -m harness.reserve_bench --recorded     # arm B (recorded, not gated)
    python -m harness.reserve_bench                # controls then criterion

Declared on #256 before any code: seeds 928-943 -- fresh; 100-115, 200-215,
300-331, 400-415, 500-515, 600-615, 700-703 and 800-927 are spent -- sides
alternated by list position (`harness.triage.head_to_head_rate`); PROMOTE
only at >= 60% of 16 vs the champion `third_herder` AND >= 90% vs each
DEFAULT_ANCHOR AND, for each `external_pool.EXTERNAL_ANCHORS` member, no fewer
wins than the champion on the same seeds in the same run (#152's paired limb);
a tie is not a win. Controls run first and a failed control voids the run --
arm B is then not scored either. Exit codes: 0 PROMOTE, 1 REJECTED, 2 VOID.
Runs under ROBRICULTURE_STRICT=1.

**The controls.** #254's herd_first stood 8 head by day 8 and beat the champion
14/16, then lost the field with 2 hands at dawn and no feed wheat. This arm
keeps back dawn's wages and the herd's feed, so the mechanism control is two
absolute bars at day 8 -- hands >= 8 (the crew the reserve exists to keep) and
head placed >= 8 (herd_first's gain, not to be given back) -- and the crop line
is PAIRED against herd_first on the same seed. The madhur row is the reading
the hypothesis lives on.

Readers are `harness.order_bench`'s; the verdict is `harness.rival_bench`'s.
"""

from __future__ import annotations

import argparse
import os

from harness import external_pool
from harness.evolve import DEFAULT_ANCHORS
from harness.order_bench import (  # noqa: F401  -- pinned by the tests to order_bench's own
    CROP_DAY,
    HEAD_BAR,
    HEAD_DAY,
    PLANTED_GAP_BAR,
    crop_line_ok,
    format_order_shape,
    order_reading,
)
from harness.pace_bench import PILKWANG, REFERENCE  # noqa: F401  -- pinned by the tests
from harness.rival_bench import (  # noqa: F401  -- pinned by the tests to rival_bench's own
    criterion,
    format_external,
    format_rows,
    paired_external_rows,
)

CONTENDER = "dawn_reserve"
CHAMPION = "third_herder"
BASELINE = "herd_first"

#: The reading the hypothesis lives on: herd_first regressed here, 5/16 vs 11/16.
MADHUR = external_pool.EXTERNAL_ANCHORS[4]
assert MADHUR.startswith("madhur")

#: Fresh. Everything through 927 is spent (912-927 were #254's).
SEEDS = tuple(range(928, 944))
CHAMPION_BAR = 0.60
ANCHOR_BAR = 0.90
CONTROL_SEED = 928

#: Arm B: the wage bill alone, no feed term. If B matches A, feed was not the
#: starving line. Never registered.
ARM_B = "wage_reserve"

#: The crew bar: herd_first had 2 hands at day 8 (field_pace 9).
HANDS_BAR = 8


def crew_ok(reading):
    """Control (ii-a): the crew the reserve exists to keep is at work at day 8."""
    return reading["hands"] >= HANDS_BAR


def mechanism_failures(reading):
    """Control (ii): both bars must hold; the names of the ones that did not."""
    failed = []
    if not crew_ok(reading):
        failed.append("hands")
    if reading["head_placed"] < HEAD_BAR:
        failed.append("head_placed")
    return failed


def arm_b_class():
    """`herd_first` keeping back tomorrow's wages only. Never registered."""
    from strategies import load
    from strategies.dawn_reserve import wage_bill

    def capital_reserve(self, day=None, animals=None):
        return wage_bill(self.hire_target(day + 1))

    return type("WageReserve", (load(BASELINE),), {"capital_reserve": capital_reserve})


def off_class():
    """The identity control's subject: the contender with every seam switched
    off (the frozen None) and dense_farm's caps. Built here, not inside
    `run_controls`, so a test can prove it survives a turn whenever a hook's
    arity changes (#256)."""
    from strategies import load
    return type("Off", (load(CONTENDER),), {
        "herd_preference": lambda self, obs: None,
        "pasture_count": lambda self, day, animals: None,
        "herd_target": lambda self, day: None,
        "livestock_workers": lambda self, day: None,
        "layout": lambda self: None,
        "land_target": lambda self, day: None,
        "hire_target": lambda self, day: None,
        "pivot_day": lambda self: None,
        "cluster_size": lambda self: None,
        "capital_reserve": lambda self, day=None, animals=None: None,
        "buy_order": lambda self: None,
        "CAPS": load(REFERENCE).CAPS,
    })


# --- live games -------------------------------------------------------------

def _arm_b_agents(name):  # pragma: no cover
    """`head_to_head_rate`'s `agents` hook, resolving arm B by name."""
    from harness.triage import _default_agents
    from kaggisim.strategy import make_agent
    arm_b = arm_b_class()
    default_agents = _default_agents()

    def agents(who):
        return make_agent(arm_b()) if who == name else default_agents(who)
    return agents


def run_controls(seed=CONTROL_SEED):  # pragma: no cover
    """Identity, then the two day-8 bars, then the paired crop line."""
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    from harness.farm_census import census_series
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

    ours, theirs = census_series(make_agent(load(CONTENDER)()), make_agent(load(CHAMPION)()), seed)
    base_turns, _ = census_series(make_agent(load(BASELINE)()), make_agent(load(CHAMPION)()), seed)
    contender = order_reading(ours)
    champion = order_reading(theirs)
    baseline = order_reading(base_turns)
    failed = mechanism_failures(contender)
    out["mechanism"] = {"ok": not failed, "failed": failed, "contender": contender,
                        "champion": champion, "baseline": baseline}
    out["crop_line"] = {"ok": crop_line_ok(contender, baseline),
                        "gap": abs(contender["planted_at_crop_day"] - baseline["planted_at_crop_day"])}
    return out


def run_criterion(seeds=SEEDS):  # pragma: no cover
    """The declared criterion: the champion row, the anchors, and the paired
    external limb -- the champion played on the same seeds in this run."""
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    from harness.triage import head_to_head_rate
    champion_row = head_to_head_rate(CONTENDER, CHAMPION, seeds)
    anchor_rows = [head_to_head_rate(CONTENDER, a, seeds) for a in DEFAULT_ANCHORS]
    pairs = paired_external_rows(CONTENDER, CHAMPION, seeds)
    return champion_row, anchor_rows, pairs


def run_recorded(seeds=SEEDS):  # pragma: no cover
    """Recorded, never gated: arm B against the champion."""
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    from harness.triage import head_to_head_rate
    return [head_to_head_rate(ARM_B, CHAMPION, seeds, agents=_arm_b_agents(ARM_B))]


def main(argv=None):  # pragma: no cover
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    ap = argparse.ArgumentParser(description="dawn_reserve: dawn's wages and the herd's feed kept back")
    ap.add_argument("--controls", action="store_true")
    ap.add_argument("--criterion", action="store_true")
    ap.add_argument("--recorded", action="store_true", help="arm B (recorded, not gated)")
    args = ap.parse_args(argv)

    if args.recorded:
        print(format_rows(run_recorded()))
        print(f"recorded, not gated: arm B ({ARM_B}: the wage bill alone) vs {CHAMPION}")
        return 0

    do_controls = args.controls or not args.criterion
    do_criterion = args.criterion or not args.controls

    if do_controls:
        ctl = run_controls()
        print(f"control identity: {'OK' if ctl['identity']['ok'] else 'FAIL -- RUN VOID'}"
              f"  {ctl['identity']}")
        c = ctl["mechanism"]["contender"]
        print(f"control mechanism: {'OK' if ctl['mechanism']['ok'] else 'FAIL -- RUN VOID'}  "
              f"(declared: at day {HEAD_DAY} hands >= {HANDS_BAR} and head placed >= {HEAD_BAR})  "
              f"hands={c['hands']} head_placed={c['head_placed']}  failed={ctl['mechanism']['failed'] or 'none'}")
        print(f"control crop line: {'OK' if ctl['crop_line']['ok'] else 'FAIL -- RUN VOID'}  "
              f"(declared: |planted at day {CROP_DAY} - herd_first's| <= {PLANTED_GAP_BAR})  "
              f"gap={ctl['crop_line']['gap']}")
        print(format_order_shape([(CONTENDER, c), (BASELINE, ctl["mechanism"]["baseline"]),
                                  (CHAMPION, ctl["mechanism"]["champion"])]))
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
              f"madhur paired row (contender, champion): {v['external'].get(MADHUR)}; "
              f"pilkwang: {v['external'].get(PILKWANG)}")
        return 0 if v["passed"] else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
