"""NW pasture block: does opening the pasture before the head beat the champion?

    python -m harness.layout_bench --controls     # the three declared controls
    python -m harness.layout_bench --criterion    # 16 seeds: champion, anchors, the external limb
    python -m harness.layout_bench --recorded     # arm B (recorded, not gated)
    python -m harness.layout_bench                # controls then criterion

Declared before any code (#246's declaration comment): seeds 880-895 --
fresh; 100-115, 200-215, 300-331, 400-415, 500-515, 600-615, 700-703 and
800-879 are spent -- sides alternated by list position
(`harness.triage.head_to_head_rate`); PROMOTE only at >= 60% of 16 vs the
champion `third_herder` AND >= 90% vs each DEFAULT_ANCHOR AND, for each
`external_pool.EXTERNAL_ANCHORS` member, no fewer wins than the champion on
the same seeds in the same run (#152's paired limb); a tie is not a win.
Controls run first and a failed control voids the run -- arm B is then not
scored either. Exit codes: 0 PROMOTE, 1 REJECTED, 2 VOID. Runs under
ROBRICULTURE_STRICT=1.

The verdict, the row and external formatting and the paired external rows
are `harness.rival_bench`'s; the census is `harness.farm_census`'; the day
readings and the deltas are `harness.front_bench`'s -- imported rather than
re-implemented.

**What the mechanism control reads, and why.** #244's control read head
OWNED at day 9 because the frozen layout land-capped pasture at five tiles
until day 12; it passed (+6) and the arm lost, because the head it bought
sat in the shed. With the block inside NW nothing caps it, so this control
reads head PLACED at `PLACED_DAY` as a paired delta -- the number the arm
exists to move -- and records owned head, shed-turns and the first day
`PASTURE_STANDING` tiles stood beside it. Planted tiles at `EARLY_CROP_DAY`
are recorded beside it: the block costs the crop line seven of twenty NW
tiles on days 0-7 and the day-16 control cannot see that.
"""

from __future__ import annotations

import argparse
import os

from harness.evolve import DEFAULT_ANCHORS
from harness.farm_census import aggregate
from harness.front_bench import mechanism_deltas  # noqa: F401  -- re-exported on purpose
from harness.front_bench import mechanism_reading as _front_reading
from harness.herder_bench import last_census_on_day
from harness.rival_bench import (  # noqa: F401  -- re-exported on purpose
    criterion,
    first_day_at_or_above,
    format_external,
    format_rows,
    paired_external_rows,
)
from strategies import field_rival as fr

CONTENDER = "nw_pasture"
CHAMPION = "third_herder"

#: Fresh. 100-115 and 200-215 (#202), 300-331 (#211), 400-415 (#219), 500-515
#: (#222), 600-615 (#225), 700-703 (#229/#234), 800-815 (#237), 816-831
#: (#239), 832-847 (#239 A vs C), 848-863 (#152 baseline) and 864-879 (#244)
#: are spent.
SEEDS = tuple(range(880, 896))
CHAMPION_BAR = 0.60
ANCHOR_BAR = 0.90
CONTROL_SEED = 880

#: Arm B: the contender with NE bought on day 6 instead of 12 -- the day
#: FRONT_RAMP steps to twelve head. If B beats A, the pre-day-12 crop cost
#: was the binding term, not the block. Never registered, so it cannot be
#: promoted or packaged by accident.
ARM_B = "early_land"
LAND_RAMP_B = ((0, 1), (6, 2), (16, 3))

#: The day placed head is read: the ceiling has every head placed by day 9
#: (#234), and #244 read owned head on the same day, so the two benches
#: compare turn for turn.
PLACED_DAY = 9

#: The day the crop line is read: the last step of `HAND_RAMP`, as #239 and #244.
CROP_DAY = 16

#: Recorded, not gated: planted tiles at the end of the opening crew's window.
#: Days 0-7 the champion's five crop hands work all 20 NW crop tiles; the
#: contender's layout leaves 13 workable until NE opens (slot 3 straddles,
#: slot 4 is wholly NE). The day-16 control cannot see that deficit --
#: by then both layouts expose the same tiles -- so it is read here, on the
#: last day before the third herder and the day-8 hire change the crew.
EARLY_CROP_DAY = 8

#: Paired deltas against the champion on `CONTROL_SEED`. Placed head is the
#: mechanism (#244's arm owned 10 by day 9 under the cap; the champion places
#: 4); the crop gap is the cost the arm is allowed to pay before it stops
#: being one change.
PLACED_DELTA_BAR = 4
PLANTED_GAP_BAR = 5

#: Recorded, not gated: the first day this many pasture tiles stand. The
#: champion's is day 12 (NE); the contender's must be earlier or the block
#: is not being built.
PASTURE_STANDING = 8


def mechanism_reading(turns, placed_day=PLACED_DAY, crop_day=CROP_DAY, early_day=EARLY_CROP_DAY):
    """One side's numbers off one game's census series ``[(day, census), ...]``:
    `front_bench`'s reading at `placed_day` plus the first day
    `PASTURE_STANDING` tiles stood (``None`` if never), plus planted tiles at
    `early_day`. Raises, as `front_bench` does, when a declared day was
    never reached."""
    reading = _front_reading(turns, placed_day, crop_day)
    at_early = last_census_on_day(turns, early_day)
    if at_early is None:
        raise ValueError(f"no census recorded on day {early_day}: the game covers "
                         f"days {turns[0][0]}-{turns[-1][0]}" if turns else
                         f"no census recorded on day {early_day}: no turns at all")
    reading["planted_tiles_at_early_day"] = at_early["planted_tiles"]
    series = aggregate(turns)["pasture_series"]
    reading["first_day_pasture_standing"] = first_day_at_or_above(series, PASTURE_STANDING)
    return reading


def mechanism_ok(deltas):
    """Control (ii): the arm actually STOOD UP head the champion had not."""
    return deltas["placed_delta"] >= PLACED_DELTA_BAR


def crop_line_ok(deltas):
    """Control (iii): the crop line did not collapse (or run away)."""
    return deltas["planted_gap"] <= PLANTED_GAP_BAR


def format_mechanism(rows):
    """One line per side, contender above champion."""
    lines = [f"{'side':<16} {'placed @9':>10} {'owned @9':>9} {'held @9':>8} "
             f"{'shed turns':>12} {'planted @8':>10} {'planted @16':>12} {'max head':>9} "
             f"{'8 past by':>10}"]
    for label, r in rows:
        first = r["first_day_pasture_standing"]
        lines.append(f"{label:<16} {r['head_placed_at_day']:>10} {r['head_owned_at_day']:>9} "
                     f"{r['head_held_at_day']:>8} "
                     f"{r['turns_with_head_in_shed']:>5}/{r['turns']:<6} "
                     f"{r['planted_tiles_at_early_day']:>10} "
                     f"{r['planted_tiles_at_crop_day']:>12} {r['max_head_placed']:>9} "
                     f"{'never' if first is None else f'day {first}':>10}")
    return "\n".join(lines)


def arm_b_class():
    """`nw_pasture` buying NE on day 6, built in-process and never registered."""
    from strategies import load

    def land_target(self, day):
        return fr._ramp(LAND_RAMP_B, day)

    return type("EarlyLand", (load(CONTENDER),), {"land_target": land_target})


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
    """The three declared controls, in order. A failure voids the run."""
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    from harness.farm_census import census_series
    from harness.tournament import play_rewards
    from kaggisim.strategy import make_agent
    from strategies import load
    out = {}

    # 1. identity: every seam off must be `dense_farm` to the value (#244's
    #    control, two seams deeper).
    off = type("Off", (load(CONTENDER),),
               {"herd_preference": lambda self, obs: None,
                "pasture_count": lambda self, day, animals: None,
                "herd_target": lambda self, day: None,
                "livestock_workers": lambda self, day: None,
                "layout": lambda self: None,
                "land_target": lambda self, day: None})
    base = play_rewards(make_agent(load("dense_farm")()), make_agent(load("dense_farm")()), seed)
    got = play_rewards(make_agent(off()), make_agent(load("dense_farm")()), seed)
    precondition_ok = base[0] > 0
    out["identity"] = {"ok": got == base and precondition_ok, "base": base, "got": got,
                       "precondition_ok": precondition_ok}

    # 2 & 3. paired deltas off the same game.
    ours, theirs = census_series(make_agent(load(CONTENDER)()),
                                 make_agent(load(CHAMPION)()), seed)
    contender, champion = mechanism_reading(ours), mechanism_reading(theirs)
    deltas = mechanism_deltas(contender, champion)
    out["mechanism"] = {"ok": mechanism_ok(deltas), "deltas": deltas,
                        "contender": contender, "champion": champion}
    out["crop_line"] = {"ok": crop_line_ok(deltas), "deltas": deltas}
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
    ap = argparse.ArgumentParser(description="NW pasture block: the pasture opened before the head")
    ap.add_argument("--controls", action="store_true")
    ap.add_argument("--criterion", action="store_true")
    ap.add_argument("--recorded", action="store_true", help="arm B (recorded, not gated)")
    args = ap.parse_args(argv)

    if args.recorded:
        print(format_rows(run_recorded()))
        print(f"recorded, not gated: arm B ({ARM_B}: NE bought on day 6) vs {CHAMPION}")
        return 0

    do_controls = args.controls or not args.criterion
    do_criterion = args.criterion or not args.controls

    if do_controls:
        ctl = run_controls()
        print(f"control identity: {'OK' if ctl['identity']['ok'] else 'FAIL -- RUN VOID'}"
              f"  {ctl['identity']}")
        d = ctl["mechanism"]["deltas"]
        c = ctl["mechanism"]["contender"]["planted_tiles_at_early_day"]
        k = ctl["mechanism"]["champion"]["planted_tiles_at_early_day"]
        print(f"control mechanism: {'OK' if ctl['mechanism']['ok'] else 'FAIL -- RUN VOID'}  "
              f"(declared: head placed at day {PLACED_DAY} minus the champion's >= "
              f"{PLACED_DELTA_BAR})  placed_delta={d['placed_delta']}  recorded: "
              f"owned_delta={d['owned_delta']} shed_delta={d['shed_delta']} "
              f"planted@8={c}/{k}")
        print(f"control crop line: {'OK' if ctl['crop_line']['ok'] else 'FAIL -- RUN VOID'}  "
              f"(declared: |planted tiles at day {CROP_DAY} - the champion's| <= "
              f"{PLANTED_GAP_BAR})  planted_gap={d['planted_gap']}")
        print(format_mechanism([(CONTENDER, ctl["mechanism"]["contender"]),
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
              f"{v['failing'] or 'none'} -> {'PROMOTE' if v['passed'] else 'REJECTED'}")
        return 0 if v["passed"] else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
