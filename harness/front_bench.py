"""Pasture first: does fronting the herd beat the champion?

    python -m harness.front_bench --controls     # the three declared controls
    python -m harness.front_bench --criterion    # 16 seeds: champion, anchors, the external limb
    python -m harness.front_bench --recorded     # arm B (recorded, not gated)
    python -m harness.front_bench                # controls then criterion

Declared before the criterion ran (the issue's declaration comment): seeds
864-879 -- fresh; 100-115, 200-215, 300-331, 400-415, 500-515, 600-615,
700-703 and 800-863 are spent -- sides alternated by list position
(`harness.triage.head_to_head_rate`); PROMOTE only at >= 60% of 16 vs the
champion `third_herder` AND >= 90% vs each DEFAULT_ANCHOR AND, for each
`external_pool.EXTERNAL_ANCHORS` member, no fewer wins than the champion on
the same seeds in the same run (#152's paired limb, its first use); a tie is
not a win. Controls run first and a failed control voids the run -- arm B is
then not scored either. Exit codes: 0 PROMOTE, 1 REJECTED, 2 VOID. Runs
under ROBRICULTURE_STRICT=1.

The verdict, the row and external formatting and the paired external rows
are `harness.rival_bench`'s; the census is `harness.farm_census`'; the day
reading is `harness.herder_bench`'s -- imported rather than re-implemented.

**What the mechanism control reads, and why.** Under the frozen layout
`PASTURE_TILES` is five NW tiles plus seven NE tiles, and NE is bought on day
12, so pasture is land-capped at five until then: "pasture standing before
the head" cannot fire before day 12 whatever the rule says. Measured on spent
seed 816 before this was declared: both farms sit on 5 pasture from day 0 to
day 11 and reach 8 placed on day 12; what the arm moves is head OWNED --
bought and waiting -- 12 against 4 on day 9. So control (ii) is owned head at
`OWNED_DAY` as a paired delta, and placement, shed-turns and the crop line
are recorded beside it. This arm buys head BEFORE it can place them, so its
shed-turn count is expected to be worse than the champion's, not better; it
is reported, not gated.
"""

from __future__ import annotations

import argparse
import os

from harness.evolve import DEFAULT_ANCHORS
from harness.farm_census import aggregate
from harness.herder_bench import last_census_on_day
from harness.rival_bench import (  # noqa: F401  -- re-exported on purpose
    criterion,
    format_external,
    format_rows,
    paired_external_rows,
)
from strategies import field_rival as fr

CONTENDER = "pasture_first"
CHAMPION = "third_herder"

#: Fresh. 100-115 and 200-215 (#202), 300-331 (#211), 400-415 (#219), 500-515
#: (#222), 600-615 (#225), 700-703 (#229/#234), 800-815 (#237), 816-831
#: (#239), 832-847 (#239 A vs C) and 848-863 (#152 baseline) are spent.
SEEDS = tuple(range(864, 880))
CHAMPION_BAR = 0.60
ANCHOR_BAR = 0.90
CONTROL_SEED = 864

#: Arm B: the front ramp on `pasture_ahead` -- two herders, no third. The
#: labour ablation: if B matches A, the finding is the ramp, not the crew.
#: Never registered, so it cannot be promoted or packaged by accident.
ARM_B = "front_ramp"

#: The day owned head is read: the ceiling has every head placed by day 9
#: (#234), and it is the last day before melon money lands on day 10, so it
#: reads what the ramp bought out of the opening bankroll alone.
OWNED_DAY = 9

#: The day the crop line is read: the last step of `HAND_RAMP`, as #239.
CROP_DAY = 16

#: Paired deltas against the champion on `CONTROL_SEED` (#237's VOID: an
#: absolute bar set without checking the frozen ramps is how a control becomes
#: unreachable). Owned head is the mechanism; the crop gap is the cost the arm
#: is allowed to pay before it stops being one change.
OWNED_DELTA_BAR = 4
PLANTED_GAP_BAR = 5


def mechanism_reading(turns, owned_day=OWNED_DAY, crop_day=CROP_DAY):
    """One side's numbers off one game's census series ``[(day, census), ...]``.

    A game that never reached a declared day raises rather than reporting
    zeroes: "the run stopped early" and "the ramp bought nothing" must not
    read the same (#237's lesson; the parser rule).
    """
    at_owned = last_census_on_day(turns, owned_day)
    at_crop = last_census_on_day(turns, crop_day)
    for day, census in ((owned_day, at_owned), (crop_day, at_crop)):
        if census is None:
            raise ValueError(f"no census recorded on day {day}: the game covers "
                             f"days {turns[0][0]}-{turns[-1][0]}" if turns else
                             f"no census recorded on day {day}: no turns at all")
    totals = aggregate(turns)
    return {
        "head_owned_at_day": at_owned["head_placed"] + at_owned["head_held"],
        "head_placed_at_day": at_owned["head_placed"],
        "head_held_at_day": at_owned["head_held"],
        "planted_tiles_at_crop_day": at_crop["planted_tiles"],
        "turns_with_head_in_shed": totals["turns_with_head_in_shed"],
        "turns": totals["turns"],
        "max_head_placed": totals["max_head_placed"],
    }


def mechanism_deltas(contender, champion):
    """Signed so bigger is better, except the crop gap, which is unsigned: a
    crop line that ran away from the champion's is as much a confound as one
    that collapsed."""
    return {
        "owned_delta": contender["head_owned_at_day"] - champion["head_owned_at_day"],
        "placed_delta": contender["head_placed_at_day"] - champion["head_placed_at_day"],
        "shed_delta": champion["turns_with_head_in_shed"] - contender["turns_with_head_in_shed"],
        "planted_gap": abs(contender["planted_tiles_at_crop_day"]
                           - champion["planted_tiles_at_crop_day"]),
    }


def mechanism_ok(deltas):
    """Control (ii): the ramp actually bought head the champion had not."""
    return deltas["owned_delta"] >= OWNED_DELTA_BAR


def crop_line_ok(deltas):
    """Control (iii): the crop line did not collapse (or run away)."""
    return deltas["planted_gap"] <= PLANTED_GAP_BAR


def format_mechanism(rows):
    """One line per side, contender above champion."""
    lines = [f"{'side':<16} {'owned @9':>9} {'placed @9':>10} {'held @9':>8} "
             f"{'shed turns':>12} {'planted @16':>12} {'max head':>9}"]
    for label, r in rows:
        lines.append(f"{label:<16} {r['head_owned_at_day']:>9} {r['head_placed_at_day']:>10} "
                     f"{r['head_held_at_day']:>8} "
                     f"{r['turns_with_head_in_shed']:>5}/{r['turns']:<6} "
                     f"{r['planted_tiles_at_crop_day']:>12} {r['max_head_placed']:>9}")
    return "\n".join(lines)


def arm_b_class():
    """`pasture_ahead` on the front ramp, built in-process and never registered."""
    from strategies import load
    from strategies.pasture_first import FRONT_RAMP

    def herd_target(self, day):
        return max(fr._ramp(FRONT_RAMP, day), fr.animal_target(day))

    def pasture_count(self, day, animals):
        return min(len(fr.PASTURE_TILES), max(animals + self.LEAD_TILES, self.herd_target(day)))

    return type("FrontRamp", (load("pasture_ahead"),),
                {"herd_target": herd_target, "pasture_count": pasture_count})


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

    # 1. identity: every seam off must be `dense_farm` to the value (#239's
    #    control, one more seam deep).
    off = type("Off", (load(CONTENDER),),
               {"herd_preference": lambda self, obs: None,
                "pasture_count": lambda self, day, animals: None,
                "herd_target": lambda self, day: None,
                "livestock_workers": lambda self, day: None})
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
    ap = argparse.ArgumentParser(description="pasture first: the herd fronted")
    ap.add_argument("--controls", action="store_true")
    ap.add_argument("--criterion", action="store_true")
    ap.add_argument("--recorded", action="store_true", help="arm B (recorded, not gated)")
    args = ap.parse_args(argv)

    if args.recorded:
        print(format_rows(run_recorded()))
        print(f"recorded, not gated: arm B ({ARM_B}: the front ramp on two herders) vs {CHAMPION}")
        return 0

    do_controls = args.controls or not args.criterion
    do_criterion = args.criterion or not args.controls

    if do_controls:
        ctl = run_controls()
        print(f"control identity: {'OK' if ctl['identity']['ok'] else 'FAIL -- RUN VOID'}"
              f"  {ctl['identity']}")
        d = ctl["mechanism"]["deltas"]
        print(f"control mechanism: {'OK' if ctl['mechanism']['ok'] else 'FAIL -- RUN VOID'}  "
              f"(declared: head owned at day {OWNED_DAY} minus the champion's >= "
              f"{OWNED_DELTA_BAR})  owned_delta={d['owned_delta']}  recorded: "
              f"placed_delta={d['placed_delta']} shed_delta={d['shed_delta']}")
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
