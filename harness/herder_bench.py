"""#239: does a third herder on the pasture lead beat the champion?

    python -m harness.herder_bench --controls     # the three declared controls
    python -m harness.herder_bench --criterion    # 16 seeds x 7 opponents, arm A
    python -m harness.herder_bench --recorded     # arms B and C, dense_farm, the ceiling
    python -m harness.herder_bench                # controls then criterion

Declared before the criterion ran (issue #239, comment of 2026-09-07): seeds
816-831 -- fresh; 100-115, 200-215, 300-331, 400-415, 500-515, 600-615,
700-703 and 800-815 are spent -- sides alternated by list position
(`harness.triage.head_to_head_rate`), PROMOTE only at >= 60% of 16 vs the
champion `rival_aware` AND >= 90% vs each DEFAULT_ANCHOR; a tie is not a win.
Controls run first and a failed control voids the run -- and when a control
fails, arms B and C are NOT scored either. Exit codes: 0 PROMOTE, 1 REJECTED,
2 VOID. Runs under ROBRICULTURE_STRICT=1.

The verdict and formatting logic is `harness.rival_bench`'s and the bench's
shape is `harness.pasture_bench`'s, both imported rather than re-implemented.

**What is new, and why.** #237's mechanism control was stated as two absolute
numbers -- the fifth pasture tile by day 2, under 120 turns with head in the
shed -- and both were unreachable by arithmetic rather than by luck: the
frozen `ANIMAL_RAMP` holds one head through day 3, so `placed + 3` cannot
reach 5 before day 4. Its VOID comment says the next declaration must state
the limbs as **deltas against the champion measured on the same seed**. So
every bar here is a paired difference: A must place `HEAD_DELTA_BAR` more head
than `rival_aware` by day `MECHANISM_DAY`, cut `SHED_DELTA_BAR` turns off its
shed wait, and keep its crop line within `PLANTED_GAP_BAR` tiles of it.
"""

from __future__ import annotations

import argparse
import os

from harness.evolve import DEFAULT_ANCHORS
from harness.farm_census import aggregate
from harness.rival_bench import (  # noqa: F401  -- re-exported on purpose
    criterion,
    format_rows,
)
from strategies import field_rival as fr

CONTENDER = "third_herder"
CHAMPION = "rival_aware"

#: Recorded, never gated: the previous champion, so arm A's rate against it
#: can be read beside #219's and #237's own 15/16.
REFERENCE = "dense_farm"

#: Recorded, never gated: the external ceiling (#234). It beat all
#: eight of our baselines 32/32, so the one question worth asking is whether
#: an arm takes a single game off it. Recorded here as a single reference row;
#: since #152 it is also a member of `external_pool.EXTERNAL_ANCHORS`, the
#: gate's paired external limb, which later benches use instead of this row.
EXTERNAL = "lonespear_kaggriculture_v21"

#: Fresh. 100-115 and 200-215 (#202), 300-331 (#211), 400-415 (#219), 500-515
#: (#222), 600-615 (#225), 700-703 (#229/#234) and 800-815 (#237) are spent.
SEEDS = tuple(range(816, 832))
EXTERNAL_SEEDS = SEEDS[:4]
CHAMPION_BAR = 0.60
ANCHOR_BAR = 0.90
CONTROL_SEED = 816

#: Arm B: the pasture lead with #237's placebo ramp instead of a third herder,
#: two herders. Copied verbatim from `pasture_bench.PLACEBO_RAMP` as a literal
#: rather than imported, because #237 recorded it as a *declared constant of
#: that experiment* and this one must be readable on its own page.
RAISED_RAMP = ((0, 3), (4, 5), (8, 8), (12, 10), (16, 11), (24, 11))

#: Arm B's name. Never registered in `strategies/`, so it cannot be promoted
#: or packaged by accident -- it is built in-process below.
ARM_B = "raised_ramp"

#: Arm C: #237's contender exactly as registered, now on 16 seeds so its 4/4
#: gets a real sample. B and C are the ablations arm A is read against: B is
#: the ramp without the labour, C is the lead alone.
ARM_C = "pasture_ahead"

#: The day the board is read for the mechanism control. #234's ceiling has all
#: 14 head placed by day 9 and our champion 7 placed with 3 held at day 16; 16
#: is also the last step of `HAND_RAMP`, so the crew is at full size and the
#: labour split has had eight days to show.
MECHANISM_DAY = 16

#: The three declared limbs, as deltas against the champion on `CONTROL_SEED`
#: (#237's VOID: absolute bars set without checking the frozen ramps are how a
#: control becomes unreachable). Head and shed are the mechanism; the crop gap
#: is the cost the arm is allowed to pay before it stops being one change.
HEAD_DELTA_BAR = 3
SHED_DELTA_BAR = 100
PLANTED_GAP_BAR = 5


def raised_target(day: int) -> int:
    """Head arm B runs on `day` -- `RAISED_RAMP` read with the benchmark's own
    step-table rule, so the two ramps differ in their numbers and in nothing
    else."""
    return fr._ramp(RAISED_RAMP, day)


def last_census_on_day(turns, day):
    """The last census recorded on `day`, or ``None`` if the game never
    reached it.

    The day's CLOSING board: a pasture built at hour 20 counts on the day it
    was built, and a plant that died overnight is gone by the reading.
    """
    found = None
    for d, census in turns:
        if d == day:
            found = census
    return found


def mechanism_reading(turns, day=MECHANISM_DAY):
    """One side's numbers for the declared controls, off one game.

    `turns` is `harness.farm_census.census_series`' ``[(day, census), ...]``.

    A game that never reached `day` raises rather than reporting zeroes: "the
    run stopped early" and "the mechanism placed no head" are different
    findings and must not look the same (#237's own lesson, and the parser
    rule -- a reading that cannot be taken is not a reading of zero).
    """
    end = last_census_on_day(turns, day)
    if end is None:
        raise ValueError(f"no census recorded on day {day}: the game covers "
                         f"days {turns[0][0]}-{turns[-1][0]}" if turns else
                         f"no census recorded on day {day}: no turns at all")
    totals = aggregate(turns)
    return {
        "head_placed_at_day": end["head_placed"],
        "planted_tiles_at_day": end["planted_tiles"],
        "turns_with_head_in_shed": totals["turns_with_head_in_shed"],
        "turns": totals["turns"],
        "max_pasture": totals["max_pasture"],
        "max_head_placed": totals["max_head_placed"],
    }


def mechanism_deltas(contender, champion):
    """The three declared differences, each signed so bigger is better --
    except the crop gap, which is unsigned: a crop line that ran AWAY from the
    champion's is as much a confound as one that collapsed."""
    return {
        "head_delta": (contender["head_placed_at_day"]
                       - champion["head_placed_at_day"]),
        "shed_delta": (champion["turns_with_head_in_shed"]
                       - contender["turns_with_head_in_shed"]),
        "planted_gap": abs(contender["planted_tiles_at_day"]
                           - champion["planted_tiles_at_day"]),
    }


def mechanism_ok(deltas):
    """Control (ii): the labour actually converted bought head into placed
    head, and took the wait off the shed."""
    return (deltas["head_delta"] >= HEAD_DELTA_BAR
            and deltas["shed_delta"] >= SHED_DELTA_BAR)


def crop_line_ok(deltas):
    """Control (iii): the crop line did not collapse (or run away)."""
    return deltas["planted_gap"] <= PLANTED_GAP_BAR


def format_mechanism(rows):
    """One line per side: all six declared numbers, contender above champion."""
    lines = [f"{'side':<16} {'head @16':>9} {'shed turns':>12} "
             f"{'planted @16':>12} {'max pasture':>12} {'max head':>9}"]
    for label, r in rows:
        lines.append(f"{label:<16} {r['head_placed_at_day']:>9} "
                     f"{r['turns_with_head_in_shed']:>5}/{r['turns']:<6} "
                     f"{r['planted_tiles_at_day']:>12} {r['max_pasture']:>12} "
                     f"{r['max_head_placed']:>9}")
    return "\n".join(lines)


def format_pairings(rows):
    """`format_rows` keyed on BOTH sides. Arms B and C both play the champion,
    so a table keyed on the opponent alone prints the same label twice and
    hides which row is which."""
    lines = [f"{'arm':<16} {'opponent':<16} {'wins':>7} {'ties':>4} {'rate':>6}"]
    for r in rows:
        games = r["games"]
        rate = (r["wins"] / games) if games else 0.0
        lines.append(f"{r['name']:<16} {r['opponent']:<16} "
                     f"{r['wins']:>3}/{games:<3} {r.get('ties', 0):>4} {rate:>6.1%}")
    return "\n".join(lines)


# --- live games -------------------------------------------------------------

def _arm_b_class():  # pragma: no cover
    """`pasture_ahead` with the raised ramp, built in-process and never
    registered -- an ablation must not be promotable or packageable."""
    from strategies import load
    return type("RaisedRamp", (load(ARM_C),),
                {"herd_target": lambda self, day: raised_target(day)})


def _arm_b_agents(name):  # pragma: no cover
    """`head_to_head_rate`'s `agents` hook, resolving arm B by name and
    everything else through triage's own loader."""
    from harness.triage import _default_agents
    from kaggisim.strategy import make_agent
    arm_b = _arm_b_class()
    default_agents = None

    def agents(who):
        if who == name:
            return make_agent(arm_b())
        nonlocal default_agents
        if default_agents is None:
            default_agents = _default_agents()
        return default_agents(who)
    return agents


def _external_agents(name):  # pragma: no cover
    """`head_to_head_rate`'s `agents` hook with the external agent
    injected by name (#234's convention). Raises if the download is absent --
    a missing opponent must not silently become a different measurement."""
    from harness.external_pool import discover_external_agents
    from harness.triage import _default_agents
    found = discover_external_agents()
    if name not in found:
        raise RuntimeError(f"external agent {name!r} not found; run "
                           f"scripts/fetch_external_agents.py")
    default_agents = None

    def agents(who):
        if who == name:
            return found[name]
        nonlocal default_agents
        if default_agents is None:
            default_agents = _default_agents()
        return default_agents(who)
    return agents


def run_controls(seed=CONTROL_SEED):  # pragma: no cover
    """The three declared controls, in order. A failure voids the run, and
    arms B and C are then not scored at all."""
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")   # an instrument surfaces crashes
    from harness.farm_census import census_series
    from harness.tournament import play_rewards
    from kaggisim.strategy import make_agent
    from strategies import load
    out = {}

    # 1. identity: every hook off -- herd_preference, pasture_count,
    #    herd_target and livestock_workers -- must be `dense_farm` to the
    #    value on a full seeded game. This pins the whole seam stack, #239's
    #    own included, in one number.
    off = type("Off", (load(CONTENDER),),
               {"herd_preference": lambda self, obs: None,
                "pasture_count": lambda self, day, animals: None,
                "herd_target": lambda self, day: None,
                "livestock_workers": lambda self, day: None})
    base = play_rewards(make_agent(load(REFERENCE)()), make_agent(load(REFERENCE)()), seed)
    got = play_rewards(make_agent(off()), make_agent(load(REFERENCE)()), seed)
    # Positive control: base[0] > 0 is the identity control's own precondition
    # -- if no money moved, "got == base" is a vacuous match, not evidence.
    precondition_ok = base[0] > 0
    out["identity"] = {"ok": got == base and precondition_ok, "base": base, "got": got,
                       "precondition_ok": precondition_ok}

    # 2 & 3. the deltas, for the contender AND the champion it played, off the
    #        same game so the two boards are paired seed for seed.
    ours, theirs = census_series(make_agent(load(CONTENDER)()),
                                 make_agent(load(CHAMPION)()), seed)
    contender, champion = mechanism_reading(ours), mechanism_reading(theirs)
    deltas = mechanism_deltas(contender, champion)
    out["mechanism"] = {"ok": mechanism_ok(deltas), "deltas": deltas,
                        "contender": contender, "champion": champion}
    out["crop_line"] = {"ok": crop_line_ok(deltas), "deltas": deltas}
    return out


def run_criterion(seeds=SEEDS):  # pragma: no cover
    """The declared criterion -- arm A only. B and C are recorded, not gated."""
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")   # an instrument surfaces crashes
    from harness.triage import head_to_head_rate
    champion_row = head_to_head_rate(CONTENDER, CHAMPION, seeds)
    anchor_rows = [head_to_head_rate(CONTENDER, a, seeds) for a in DEFAULT_ANCHORS]
    return champion_row, anchor_rows


def run_recorded(seeds=SEEDS, external_seeds=EXTERNAL_SEEDS):  # pragma: no cover
    """Recorded, never gated: the two ablations against the champion, the
    previous champion over the full seed set, and the ceiling over four."""
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")   # an instrument surfaces crashes
    from harness.triage import head_to_head_rate
    arm_b = head_to_head_rate(ARM_B, CHAMPION, seeds, agents=_arm_b_agents(ARM_B))
    arm_c = head_to_head_rate(ARM_C, CHAMPION, seeds)
    reference_row = head_to_head_rate(CONTENDER, REFERENCE, seeds)
    external_row = head_to_head_rate(CONTENDER, EXTERNAL, external_seeds,
                                     agents=_external_agents(EXTERNAL))
    return [arm_b, arm_c, reference_row, external_row]


def main(argv=None):  # pragma: no cover
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")   # an instrument surfaces crashes
    ap = argparse.ArgumentParser(description="#239 a third herder on the pasture lead")
    ap.add_argument("--controls", action="store_true")
    ap.add_argument("--criterion", action="store_true")
    ap.add_argument("--recorded", action="store_true",
                    help="arms B and C, dense_farm and the ceiling (recorded, not gated)")
    args = ap.parse_args(argv)

    if args.recorded:
        print(format_pairings(run_recorded()))
        print(f"recorded, not gated: arm B ({ARM_B}) and arm C ({ARM_C}) vs "
              f"{CHAMPION}; {CONTENDER} vs {REFERENCE} and vs the {EXTERNAL} ceiling")
        return 0

    do_controls = args.controls or not args.criterion
    do_criterion = args.criterion or not args.controls

    if do_controls:
        ctl = run_controls()
        print(f"control identity: {'OK' if ctl['identity']['ok'] else 'FAIL -- RUN VOID'}"
              f"  {ctl['identity']}")
        d = ctl["mechanism"]["deltas"]
        print(f"control mechanism: "
              f"{'OK' if ctl['mechanism']['ok'] else 'FAIL -- RUN VOID'}  "
              f"(declared: head placed at day {MECHANISM_DAY} minus the champion's "
              f">= {HEAD_DELTA_BAR}, the champion's shed turns minus ours "
              f">= {SHED_DELTA_BAR})  head_delta={d['head_delta']} "
              f"shed_delta={d['shed_delta']}")
        print(f"control crop line: "
              f"{'OK' if ctl['crop_line']['ok'] else 'FAIL -- RUN VOID'}  "
              f"(declared: |planted tiles at day {MECHANISM_DAY} - the champion's| "
              f"<= {PLANTED_GAP_BAR})  planted_gap={d['planted_gap']}")
        print(format_mechanism([(CONTENDER, ctl["mechanism"]["contender"]),
                                (CHAMPION, ctl["mechanism"]["champion"])]))
        if not all(r["ok"] for r in ctl.values()):
            print("a control failed: the run is VOID and arms B and C are NOT scored")
            return 2

    if do_criterion:
        champion_row, anchor_rows = run_criterion()
        print(format_rows([champion_row] + anchor_rows))
        v = criterion(champion_row, anchor_rows, CHAMPION_BAR, ANCHOR_BAR)
        print(f"champion {v['champion_rate']:.1%} (bar {CHAMPION_BAR:.0%}); anchors below "
              f"{ANCHOR_BAR:.0%}: {v['failing'] or 'none'} -> "
              f"{'PROMOTE' if v['passed'] else 'REJECTED'}")
        return 0 if v["passed"] else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
