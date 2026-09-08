"""#237: does building pasture ahead of the herd beat the champion?

    python -m harness.pasture_bench --controls     # the three declared controls
    python -m harness.pasture_bench --criterion    # 16 seeds x 7 opponents
    python -m harness.pasture_bench --reference    # dense_farm + lonespear, recorded
    python -m harness.pasture_bench                # controls then criterion

Declared before the criterion ran (issue #237, comment of 2026-09-06): seeds
800-815 -- fresh; 100-115, 200-215, 300-331, 400-415, 500-515, 600-615 and
700-703 are spent -- sides alternated by list position
(`harness.triage.head_to_head_rate`), PROMOTE only at >= 60% of 16 vs the
champion `rival_aware` AND >= 90% vs each DEFAULT_ANCHOR; a tie is not a win.
Controls run first and a failed control voids the run.
Exit codes: 0 PROMOTE, 1 REJECTED, 2 VOID. Runs under ROBRICULTURE_STRICT=1.

The verdict and formatting logic is `harness.rival_bench`'s, imported rather
than re-implemented: `criterion`, `format_rows`, `first_day_at_or_above`.
What is new here is #237's own: the placebo ramp, the mechanism-fired reading
over `harness.farm_census.aggregate`, and a criterion played in two halves so
the contender's first four seeds can be read beside the placebo's four
without playing those games a second time.
"""

from __future__ import annotations

import argparse
import os

from harness.evolve import DEFAULT_ANCHORS
from harness.farm_census import aggregate
from harness.rival_bench import (  # noqa: F401  -- re-exported on purpose
    criterion,
    first_day_at_or_above,
    format_rows,
)
from strategies import field_rival as fr

CONTENDER = "pasture_ahead"
CHAMPION = "rival_aware"

#: Recorded, never gated: the previous champion, so the pasture rule's rate
#: against it can be read beside #219's 15/16 for `rival_aware`.
REFERENCE = "dense_farm"

#: Recorded, never gated: the external ceiling (#234). It beat all
#: eight of our baselines 32/32, so the one question worth asking is whether
#: this contender takes a single game off it. Recorded here as a single
#: reference row; since #152 it is also a member of
#: `external_pool.EXTERNAL_ANCHORS`, the gate's paired external limb, which
#: later benches use instead of this row.
EXTERNAL = "lonespear_kaggriculture_v21"

#: Fresh. 100-115 and 200-215 (#202), 300-331 (#211), 400-415 (#219), 500-515
#: (#222), 600-615 (#225) and 700-703 (#229/#234) are spent.
SEEDS = tuple(range(800, 816))
CHAMPION_BAR = 0.60
ANCHOR_BAR = 0.90
CONTROL_SEED = 800

#: The placebo's four seeds, and the same four the contender's criterion row is
#: split on so the two numbers are read on identical games.
PLACEBO_SEEDS = SEEDS[:4]

#: The mechanism-fired check, declared on #237 before any code: a money win
#: with these unmoved is not this mechanism. Read with `harness.farm_census`.
PASTURE_TILES_FIRED = 5
PASTURE_DAY_BAR = 2
SHED_TURNS_BAR = 120

#: The placebo: `rival_aware` with the animal ramp raised three head at each
#: step and the pasture rule untouched. If more head alone reproduces the
#: effect, the finding is herd size rather than pasture. Declared verbatim.
PLACEBO_RAMP = ((0, 3), (4, 5), (8, 8), (12, 10), (16, 11), (24, 11))
PLACEBO_NAME = "placebo_ramp"


def placebo_target(day: int) -> int:
    """Head the placebo arm runs on `day` -- `PLACEBO_RAMP` read with the
    benchmark's own step-table rule, so the two ramps differ in their numbers
    and in nothing else."""
    return fr._ramp(PLACEBO_RAMP, day)


def mechanism_reading(turns):
    """The two declared mechanism numbers for one side of one game.

    `turns` is `harness.farm_census.census_series`' `[(day, census), ...]`.
    `first_day_pasture` is ``None`` when the farm never built
    `PASTURE_TILES_FIRED` tiles at all -- "never" must not read as a day.
    """
    totals = aggregate(turns)
    return {
        "first_day_pasture": first_day_at_or_above(totals["pasture_series"],
                                                   PASTURE_TILES_FIRED),
        "turns_with_head_in_shed": totals["turns_with_head_in_shed"],
        "turns": totals["turns"],
        "max_pasture": totals["max_pasture"],
        "max_head_placed": totals["max_head_placed"],
    }


def mechanism_ok(reading):
    """Both declared limbs: the fifth pasture tile by `PASTURE_DAY_BAR`, and
    fewer than `SHED_TURNS_BAR` turns with head waiting in the shed."""
    day = reading["first_day_pasture"]
    return (day is not None and day <= PASTURE_DAY_BAR
            and reading["turns_with_head_in_shed"] < SHED_TURNS_BAR)


def format_mechanism(rows):
    """One line per side: whose numbers, and both declared limbs."""
    lines = [f"{'side':<16} {'1st day >=5 past':>17} {'shed turns':>11} "
             f"{'max pasture':>12} {'max head':>9}"]
    for label, r in rows:
        day = r["first_day_pasture"]
        lines.append(f"{label:<16} {('never' if day is None else day):>17} "
                     f"{r['turns_with_head_in_shed']:>4}/{r['turns']:<6} "
                     f"{r['max_pasture']:>12} {r['max_head_placed']:>9}")
    return "\n".join(lines)


def merge_rows(first, second):
    """One head-to-head row from the two halves the criterion is played in.

    The split exists so the contender's first four seeds can be read beside
    the placebo's without replaying them; it is only sound because the halves
    are the same pairing and the split index is even (`head_to_head_rate`
    alternates seats by list position).
    """
    if (first["name"], first["opponent"]) != (second["name"], second["opponent"]):
        raise ValueError(
            f"cannot merge {first['name']} vs {first['opponent']} with "
            f"{second['name']} vs {second['opponent']}: different pairings")
    return {"name": first["name"], "opponent": first["opponent"],
            "wins": first["wins"] + second["wins"],
            "ties": first["ties"] + second["ties"],
            "games": first["games"] + second["games"],
            "seeds": f"{first['seeds'].split('-')[0]}-{second['seeds'].split('-')[-1]}"}


# --- live games -------------------------------------------------------------

def _placebo_class():  # pragma: no cover
    """`rival_aware` with the raised ramp, built in-process and never
    registered -- a placebo must not be promotable or packageable."""
    from strategies import load
    return type("PlaceboRamp", (load(CHAMPION),),
                {"herd_target": lambda self, day: placebo_target(day)})


def _placebo_agents(name):  # pragma: no cover
    """`head_to_head_rate`'s `agents` hook, resolving the unregistered
    placebo by name and everything else through triage's own loader."""
    from harness.triage import _default_agents
    from kaggisim.strategy import make_agent
    placebo = _placebo_class()
    default_agents = None

    def agents(who):
        if who == name:
            return make_agent(placebo())
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


def run_controls(seed=CONTROL_SEED, placebo_seeds=PLACEBO_SEEDS):  # pragma: no cover
    """The three declared controls, in order."""
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")   # an instrument surfaces crashes
    from harness.farm_census import census_series
    from harness.tournament import play_rewards
    from harness.triage import head_to_head_rate
    from kaggisim.strategy import make_agent
    from strategies import load
    out = {}

    # 1. identity: the pasture rule off (back to the benchmark's own count)
    #    must be `rival_aware` to the value on a full seeded game.
    off = type("Off", (load(CONTENDER),),
               {"pasture_count": lambda self, day, animals: None})
    base = play_rewards(make_agent(load(CHAMPION)()), make_agent(load(CHAMPION)()), seed)
    got = play_rewards(make_agent(off()), make_agent(load(CHAMPION)()), seed)
    # Positive control: base[0] > 0 is the identity control's own precondition
    # -- if no money moved, "got == base" is a vacuous match, not evidence.
    precondition_ok = base[0] > 0
    out["identity"] = {"ok": got == base and precondition_ok, "base": base, "got": got,
                       "precondition_ok": precondition_ok}

    # 2. placebo: more head, pasture rule untouched. Recorded, not gated -- it
    #    is read beside the contender's own four seeds from the criterion run.
    row = head_to_head_rate(PLACEBO_NAME, CHAMPION, placebo_seeds,
                            agents=_placebo_agents(PLACEBO_NAME))
    out["placebo"] = {"ok": True, "recorded_not_gated": True, "row": row}

    # 3. mechanism fired, for the contender AND the champion it played.
    ours, theirs = census_series(make_agent(load(CONTENDER)()),
                                 make_agent(load(CHAMPION)()), seed)
    contender, champion = mechanism_reading(ours), mechanism_reading(theirs)
    out["mechanism"] = {"ok": mechanism_ok(contender),
                        "contender": contender, "champion": champion}
    return out


def run_criterion(seeds=SEEDS, split=len(PLACEBO_SEEDS)):  # pragma: no cover
    """The declared criterion. The champion row is played in two halves --
    `seeds[:split]` then `seeds[split:]` -- and merged, so the first four
    seeds are also available on their own for the placebo comparison without
    replaying them. `split` is even, so every seed keeps the seat it would
    have had in one 16-seed list."""
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")   # an instrument surfaces crashes
    from harness.triage import head_to_head_rate
    first = head_to_head_rate(CONTENDER, CHAMPION, seeds[:split])
    rest = head_to_head_rate(CONTENDER, CHAMPION, seeds[split:])
    champion_row = merge_rows(first, rest)
    anchor_rows = [head_to_head_rate(CONTENDER, a, seeds) for a in DEFAULT_ANCHORS]
    return champion_row, anchor_rows, first


def run_reference(seeds=SEEDS, external_seeds=PLACEBO_SEEDS):  # pragma: no cover
    """Recorded, never gated: the previous champion over the full seed set,
    and the external ceiling over four seeds."""
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")   # an instrument surfaces crashes
    from harness.triage import head_to_head_rate
    reference_row = head_to_head_rate(CONTENDER, REFERENCE, seeds)
    external_row = head_to_head_rate(CONTENDER, EXTERNAL, external_seeds,
                                     agents=_external_agents(EXTERNAL))
    return reference_row, external_row


def main(argv=None):  # pragma: no cover
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")   # an instrument surfaces crashes
    ap = argparse.ArgumentParser(description="#237 pasture ahead of the herd")
    ap.add_argument("--controls", action="store_true")
    ap.add_argument("--criterion", action="store_true")
    ap.add_argument("--reference", action="store_true",
                    help="vs dense_farm and the lonespear ceiling (recorded, not gated)")
    args = ap.parse_args(argv)

    if args.reference:
        reference_row, external_row = run_reference()
        print(format_rows([reference_row, external_row]))
        print(f"recorded, not gated: {CONTENDER} vs {REFERENCE} and vs the "
              f"{EXTERNAL} ceiling")
        return 0

    do_controls = args.controls or not args.criterion
    do_criterion = args.criterion or not args.controls

    if do_controls:
        ctl = run_controls()
        print(f"control identity: {'OK' if ctl['identity']['ok'] else 'FAIL -- RUN VOID'}"
              f"  {ctl['identity']}")
        print(f"control placebo (recorded, not gated):\n"
              f"{format_rows([ctl['placebo']['row']])}")
        print(f"control mechanism: "
              f"{'OK' if ctl['mechanism']['ok'] else 'FAIL -- RUN VOID'}  "
              f"(declared: first day pasture >= {PASTURE_TILES_FIRED} tiles must be "
              f"<= {PASTURE_DAY_BAR}, shed turns < {SHED_TURNS_BAR})")
        print(format_mechanism([(CONTENDER, ctl["mechanism"]["contender"]),
                                (CHAMPION, ctl["mechanism"]["champion"])]))
        if not all(r["ok"] for r in ctl.values()):
            return 2

    if do_criterion:
        champion_row, anchor_rows, first_row = run_criterion()
        print(format_rows([champion_row] + anchor_rows))
        print(f"{CONTENDER} vs {CHAMPION} on {first_row['seeds']} (the placebo's "
              f"seeds): {first_row['wins']}/{first_row['games']}")
        v = criterion(champion_row, anchor_rows, CHAMPION_BAR, ANCHOR_BAR)
        print(f"champion {v['champion_rate']:.1%} (bar {CHAMPION_BAR:.0%}); anchors below "
              f"{ANCHOR_BAR:.0%}: {v['failing'] or 'none'} -> "
              f"{'PROMOTE' if v['passed'] else 'REJECTED'}")
        return 0 if v["passed"] else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
