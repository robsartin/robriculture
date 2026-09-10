"""herd_first: does funding the herd before land and seed stand the field's herd, and beat the champion?

    python -m harness.order_bench --controls     # identity, head placed at day 8, the paired crop line
    python -m harness.order_bench --criterion    # 16 seeds: champion, anchors, the external limb
    python -m harness.order_bench --recorded     # arm B (recorded, not gated)
    python -m harness.order_bench                # controls then criterion

Declared on #254 before any code: seeds 912-927 -- fresh; 100-115, 200-215,
300-331, 400-415, 500-515, 600-615, 700-703 and 800-896 are spent -- sides
alternated by list position (`harness.triage.head_to_head_rate`); PROMOTE
only at >= 60% of 16 vs the champion `third_herder` AND >= 90% vs each
DEFAULT_ANCHOR AND, for each `external_pool.EXTERNAL_ANCHORS` member, no fewer
wins than the champion on the same seeds in the same run (#152's paired limb);
a tie is not a win. Controls run first and a failed control voids the run --
arm B is then not scored either. Exit codes: 0 PROMOTE, 1 REJECTED, 2 VOID.
Runs under ROBRICULTURE_STRICT=1.

**The controls.** #252 VOIDed on head placed at day 8 (6 against a bar of 8)
because the benchmark's buy order funds land and seed before the herd. This
arm moves the herd first, so the mechanism control is that same bar, absolute,
read off the contender's own census. The cost it may pay is a later crop
line, so the crop control is PAIRED against `field_pace` on the same seed:
planted tiles at day 12 within `PLANTED_GAP_BAR` of field_pace's.

The verdict, the row and external formatting and the paired external rows
are `harness.rival_bench`'s; the census readers are `harness.pace_bench`'s.
"""

from __future__ import annotations

import argparse
import os

from harness.evolve import DEFAULT_ANCHORS
from harness.pace_bench import (  # noqa: F401  -- the tests pin these to pace_bench's own
    PAYDAY_MONEY,
    PILKWANG,
    REFERENCE,
    format_shape,
    shape_reading,
)
from harness.rival_bench import (  # noqa: F401  -- the tests pin these to rival_bench's own
    criterion,
    format_external,
    format_rows,
    paired_external_rows,
)

CONTENDER = "herd_first"
CHAMPION = "third_herder"
PACE = "field_pace"

#: Fresh. Everything through 896 is spent; 897-911 were declared for #252 and
#: never played, and are not reused.
SEEDS = tuple(range(912, 928))
CHAMPION_BAR = 0.60
ANCHOR_BAR = 0.90
CONTROL_SEED = 912

#: Arm B: the herd before seed but after land. If B matches A, land's priority
#: is not what moved. Never registered.
ARM_B = "herd_mid"
ORDER_B = ("hires", "land", "herd", "seed")

#: The mechanism: the bar #252 failed at 6.
HEAD_DAY = 8
HEAD_BAR = 8

#: The cost the arm may pay: planted tiles at day 12 within this many of
#: field_pace's on the same seed (field_pace measured 47 on seed 896).
CROP_DAY = 12
PLANTED_GAP_BAR = 12


def order_reading(turns, head_day=HEAD_DAY, crop_day=CROP_DAY):
    """`pace_bench.shape_reading` plus the two numbers a head-placed miss needs
    to be root-caused: head bought and still in the shed, and pasture tiles
    standing free, both on the closing board of `head_day` (#254 review I1).
    "Could not afford the head" reads held 0 / free > 0; "bought them and the
    herders could not place them" reads held > 0."""
    from harness.herder_bench import last_census_on_day
    reading = shape_reading(turns, head_day, crop_day)
    at = last_census_on_day(turns, head_day)
    reading["head_held"] = at["head_held"]
    reading["pasture_free"] = at["structures"]["PASTURE"]["free"]
    return reading


def format_order_shape(rows):
    """`format_shape`'s line per side, with held head and free pasture added."""
    lines = [f"{'side':<16} {'placed@8':>9} {'held@8':>7} {'free@8':>7} {'planted@8':>10} "
             f"{'quads@8':>8} {'hands@8':>8} {'money@8':>8} {'planted@12':>11} {'money@12':>9} {'payday':>8}"]
    for label, r in rows:
        payday = "never" if r["payday"] is None else f"day {r['payday']}"
        lines.append(f"{label:<16} {r['head_placed']:>9} {r['head_held']:>7} {r['pasture_free']:>7} "
                     f"{r['planted']:>10} {r['quadrants']:>8} {r['hands']:>8} {r['money_at_shape_day']:>8.0f} "
                     f"{r['planted_at_crop_day']:>11} {r['money_at_crop_day']:>9.0f} {payday:>8}")
    return "\n".join(lines)


def mechanism_ok(reading):
    """Control (ii): the herd the buy order was moved for is actually standing."""
    return reading["head_placed"] >= HEAD_BAR


def crop_line_ok(contender, pace):
    """Control (iii): the crop line paid no more than the declared gap."""
    return abs(contender["planted_at_crop_day"] - pace["planted_at_crop_day"]) <= PLANTED_GAP_BAR


def arm_b_class():
    """`field_pace` with the herd before seed, after land. Never registered."""
    from strategies import load

    return type("HerdMid", (load(PACE),), {"buy_order": lambda self: ORDER_B})


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
    """Identity, then head placed at day 8, then the paired crop line."""
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    from harness.farm_census import census_series
    from harness.tournament import play_rewards
    from kaggisim.strategy import make_agent
    from strategies import load
    out = {}

    off = type("Off", (load(CONTENDER),), {
        "herd_preference": lambda self, obs: None,
        "pasture_count": lambda self, day, animals: None,
        "herd_target": lambda self, day: None,
        "livestock_workers": lambda self, day: None,
        "layout": lambda self: None,
        "land_target": lambda self, day: None,
        "hire_target": lambda self, day: None,
        "pivot_day": lambda self: None,
        "cluster_size": lambda self: None,
        "capital_reserve": lambda self: None,
        "buy_order": lambda self: None,
        "CAPS": load(REFERENCE).CAPS,
    })
    base = play_rewards(make_agent(load(REFERENCE)()), make_agent(load(REFERENCE)()), seed)
    got = play_rewards(make_agent(off()), make_agent(load(REFERENCE)()), seed)
    precondition_ok = base[0] > 0
    out["identity"] = {"ok": got == base and precondition_ok, "base": base, "got": got,
                       "precondition_ok": precondition_ok}

    ours, theirs = census_series(make_agent(load(CONTENDER)()), make_agent(load(CHAMPION)()), seed)
    pace_turns, _ = census_series(make_agent(load(PACE)()), make_agent(load(CHAMPION)()), seed)
    contender = order_reading(ours)
    champion = order_reading(theirs)
    pace = order_reading(pace_turns)
    out["mechanism"] = {"ok": mechanism_ok(contender), "contender": contender,
                        "champion": champion, "pace": pace}
    out["crop_line"] = {"ok": crop_line_ok(contender, pace),
                        "gap": abs(contender["planted_at_crop_day"] - pace["planted_at_crop_day"])}
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
    ap = argparse.ArgumentParser(description="herd_first: the herd funded before land and seed")
    ap.add_argument("--controls", action="store_true")
    ap.add_argument("--criterion", action="store_true")
    ap.add_argument("--recorded", action="store_true", help="arm B (recorded, not gated)")
    args = ap.parse_args(argv)

    if args.recorded:
        print(format_rows(run_recorded()))
        print(f"recorded, not gated: arm B ({ARM_B}: the herd before seed, after land) vs {CHAMPION}")
        return 0

    do_controls = args.controls or not args.criterion
    do_criterion = args.criterion or not args.controls

    if do_controls:
        ctl = run_controls()
        print(f"control identity: {'OK' if ctl['identity']['ok'] else 'FAIL -- RUN VOID'}"
              f"  {ctl['identity']}")
        c = ctl["mechanism"]["contender"]
        print(f"control mechanism: {'OK' if ctl['mechanism']['ok'] else 'FAIL -- RUN VOID'}  "
              f"(declared: head placed at day {HEAD_DAY} >= {HEAD_BAR})  head_placed={c['head_placed']}")
        print(f"control crop line: {'OK' if ctl['crop_line']['ok'] else 'FAIL -- RUN VOID'}  "
              f"(declared: |planted at day {CROP_DAY} - field_pace's| <= {PLANTED_GAP_BAR})  "
              f"gap={ctl['crop_line']['gap']}")
        print(format_order_shape([(CONTENDER, c), (PACE, ctl["mechanism"]["pace"]),
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
              f"pilkwang paired row (contender, champion): {v['external'].get(PILKWANG)}")
        return 0 if v["passed"] else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
