"""field_pace: does the field's schedule, as one package, beat the champion?

    python -m harness.pace_bench --controls     # identity, then the absolute shape control
    python -m harness.pace_bench --criterion    # 16 seeds: champion, anchors, the external limb
    python -m harness.pace_bench --recorded     # arm B (recorded, not gated)
    python -m harness.pace_bench                # controls then criterion

Declared on #252 before any code: seeds 896-911 -- fresh; 100-115, 200-215,
300-331, 400-415, 500-515, 600-615, 700-703 and 800-895 are spent -- sides
alternated by list position (`harness.triage.head_to_head_rate`); PROMOTE
only at >= 60% of 16 vs the champion `third_herder` AND >= 90% vs each
DEFAULT_ANCHOR AND, for each `external_pool.EXTERNAL_ANCHORS` member, no fewer
wins than the champion on the same seeds in the same run (#152's paired limb);
a tie is not a win. Controls run first and a failed control voids the run --
arm B is then not scored either. Exit codes: 0 PROMOTE, 1 REJECTED, 2 VOID.
Runs under ROBRICULTURE_STRICT=1.

**The shape control is absolute, not paired.** The package was copied from the
field's medians; a contender that does not reproduce that shape on the board
has not tested the hypothesis, whatever the score says (#198's own necessary
condition, transplanted). The bars are the medians less a margin: by the close
of day 8 planted >= 30 (field 37), quadrants >= 2, hands >= 8 (field 10), head
placed >= 8 (field 13); by the close of day 12 planted >= 45 (field 62). A
miss names the knob that did not take. Recorded beside it: money at both days,
the first day money reaches 5,000 (the melon payday; the field's is day 10),
strawberry tiles at day 8, and the champion's readings from the same game.

The verdict, the row and external formatting and the paired external rows
are `harness.rival_bench`'s; the census is `harness.farm_census`'.
"""

from __future__ import annotations

import argparse
import os

from harness import external_pool
from harness.evolve import DEFAULT_ANCHORS
from harness.herder_bench import last_census_on_day
from harness.rival_bench import (  # noqa: F401  -- the tests pin these to rival_bench's own
    criterion,
    first_day_at_or_above,
    format_external,
    format_rows,
    paired_external_rows,
)

CONTENDER = "field_pace"
CHAMPION = "third_herder"

#: The identity/shape controls' reference agent -- declared once, `herder_bench`'s own name.
REFERENCE = "dense_farm"

#: The pinned gate external this module reports the paired row for. Asserted below to catch
#: a rename in `external_pool` rather than silently printing ``None`` (#252 review M5).
PILKWANG = external_pool.EXTERNAL_ANCHORS[0]
assert PILKWANG.startswith("pilkwang")

#: Fresh. Everything through 895 is spent (see the module docstring).
SEEDS = tuple(range(896, 912))
CHAMPION_BAR = 0.60
ANCHOR_BAR = 0.90
CONTROL_SEED = 896

#: Arm B: the crop-and-land schedule with no reserve, on third_herder's herd.
#: Never registered, so it cannot be promoted or packaged by accident.
ARM_B = "crop_pace"

SHAPE_DAY = 8
CROP_DAY = 12
SHAPE_BARS = {"planted": 30, "quadrants": 2, "hands": 8, "head_placed": 8}
PLANTED_AT_CROP_DAY_BAR = 45
PAYDAY_MONEY = 5000


def _closing(turns, day):
    census = last_census_on_day(turns, day)
    if census is None:
        span = f"the game covers days {turns[0][0]}-{turns[-1][0]}" if turns else "no turns at all"
        raise ValueError(f"no census recorded on day {day}: {span}")
    return census


def shape_reading(turns, shape_day=SHAPE_DAY, crop_day=CROP_DAY):
    """One side's shape off one game's census series ``[(day, census), ...]``:
    the closing board of `shape_day` and `crop_day`, and the payday."""
    at_shape, at_crop = _closing(turns, shape_day), _closing(turns, crop_day)
    money_series = [(day, c["money"]) for day, c in turns]
    return {
        "planted": at_shape["planted_tiles"],
        "quadrants": len(at_shape["quadrants"]),
        "hands": at_shape["hands"],
        "head_placed": at_shape["head_placed"],
        "strawberry": at_shape["planted"].get("STRAWBERRY", 0),
        "money_at_shape_day": at_shape["money"],
        "planted_at_crop_day": at_crop["planted_tiles"],
        "money_at_crop_day": at_crop["money"],
        "payday": first_day_at_or_above(money_series, PAYDAY_MONEY),
    }


def shape_failures(reading):
    """The declared bars that did not hold, in declaration order; ``[]`` passes."""
    failed = [name for name, bar in SHAPE_BARS.items() if reading[name] < bar]
    if reading["planted_at_crop_day"] < PLANTED_AT_CROP_DAY_BAR:
        failed.append("planted_at_crop_day")
    return failed


def format_shape(rows):
    """One line per side, contender above champion."""
    lines = [f"{'side':<16} {'planted@8':>9} {'quads@8':>8} {'hands@8':>8} {'head@8':>7} "
             f"{'straw@8':>8} {'money@8':>8} {'planted@12':>10} {'money@12':>9} {'payday':>8}"]
    for label, r in rows:
        payday = "never" if r["payday"] is None else f"day {r['payday']}"
        lines.append(f"{label:<16} {r['planted']:>9} {r['quadrants']:>8} {r['hands']:>8} "
                     f"{r['head_placed']:>7} {r['strawberry']:>8} {r['money_at_shape_day']:>8.0f} "
                     f"{r['planted_at_crop_day']:>10} {r['money_at_crop_day']:>9.0f} {payday:>8}")
    return "\n".join(lines)


def arm_b_class():
    """`field_pace` with the herd package returned to `third_herder`'s: the
    crop-and-land schedule alone. Built in-process and never registered."""
    from strategies import load
    from strategies.third_herder import ThirdHerderStrategy

    return type("CropPace", (load(CONTENDER),), {
        "herd_target": ThirdHerderStrategy.herd_target,
        "layout": ThirdHerderStrategy.layout,
        "pasture_count": ThirdHerderStrategy.pasture_count,
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
        "CAPS": load(REFERENCE).CAPS,
    })


def run_controls(seed=CONTROL_SEED):  # pragma: no cover
    """Identity, then the absolute shape control. A failure voids the run."""
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

    ours, theirs = census_series(make_agent(load(CONTENDER)()),
                                 make_agent(load(CHAMPION)()), seed)
    contender, champion = shape_reading(ours), shape_reading(theirs)
    failed = shape_failures(contender)
    out["shape"] = {"ok": not failed, "failed": failed, "contender": contender, "champion": champion}
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
    ap = argparse.ArgumentParser(description="field_pace: the field's schedule as one package")
    ap.add_argument("--controls", action="store_true")
    ap.add_argument("--criterion", action="store_true")
    ap.add_argument("--recorded", action="store_true", help="arm B (recorded, not gated)")
    args = ap.parse_args(argv)

    if args.recorded:
        print(format_rows(run_recorded()))
        print(f"recorded, not gated: arm B ({ARM_B}: the crop-and-land schedule with no "
              f"reserve, on third_herder's herd) vs {CHAMPION}")
        return 0

    do_controls = args.controls or not args.criterion
    do_criterion = args.criterion or not args.controls

    if do_controls:
        ctl = run_controls()
        print(f"control identity: {'OK' if ctl['identity']['ok'] else 'FAIL -- RUN VOID'}"
              f"  {ctl['identity']}")
        print(f"control shape: {'OK' if ctl['shape']['ok'] else 'FAIL -- RUN VOID'}  "
              f"(declared: by day {SHAPE_DAY} {SHAPE_BARS}; by day {CROP_DAY} planted >= "
              f"{PLANTED_AT_CROP_DAY_BAR})  failed={ctl['shape']['failed'] or 'none'}")
        print(format_shape([(CONTENDER, ctl["shape"]["contender"]),
                            (CHAMPION, ctl["shape"]["champion"])]))
        if not all(r["ok"] for r in ctl.values()):
            print("a control failed: the run is VOID and arm B is NOT scored")
            return 2

    if do_criterion:
        champion_row, anchor_rows, pairs = run_criterion()
        print(format_rows([champion_row] + anchor_rows))
        print(format_external(pairs))
        v = criterion(champion_row, anchor_rows, CHAMPION_BAR, ANCHOR_BAR, external_pairs=pairs)
        pilkwang = v.get("external", {}).get(PILKWANG)
        print(f"champion {v['champion_rate']:.1%} (bar {CHAMPION_BAR:.0%}); failing limbs: "
              f"{v['failing'] or 'none'} -> {'PROMOTE' if v['passed'] else 'REJECTED'}; "
              f"pilkwang paired row (contender, champion): {pilkwang}")
        return 0 if v["passed"] else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
