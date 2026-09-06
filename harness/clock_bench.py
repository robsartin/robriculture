"""#225: does the day-8 clock beat the champion `rival_aware`?

    python -m harness.clock_bench --controls      # the two spec controls
    python -m harness.clock_bench --criterion     # 16 seeds x 7 opponents
    python -m harness.clock_bench --reference     # vs dense_farm, recorded not gated
    python -m harness.clock_bench --milk          # realised milk price vs meta_bot
    python -m harness.clock_bench                 # controls then criterion

Declared before the criterion ran (issue #225, comment of 2026-09-06):
seeds 600-615 -- fresh; 100-115, 200-215, 300-331, 400-415 and 500-515 are
spent -- sides alternated by list position (`harness.triage.head_to_head_rate`),
PROMOTE only at >= 60% of 16 vs the champion AND >= 90% vs each DEFAULT_ANCHOR;
a tie is not a win. Controls run first and a failed control voids the run.
Exit codes: 0 PROMOTE, 1 REJECTED, 2 VOID. Runs under ROBRICULTURE_STRICT=1.

The counting and verdict logic is `harness.rival_bench`'s, imported rather
than re-implemented: `animal_buys`, `mechanism_fired`, `criterion`,
`format_rows` and the live `action_stream`. Only the constants and the
milk/wool realisation table are new here -- `rival_bench` hard-codes its own
CONTENDER/CHAMPION, so this module carries #225's.
"""

from __future__ import annotations

import argparse
import os

from harness.evolve import DEFAULT_ANCHORS
from harness.rival_bench import (  # noqa: F401  -- re-exported on purpose
    action_stream,
    animal_buys,
    criterion,
    format_rows,
    mechanism_fired,
)

CONTENDER = "cows_from_day_8"
CHAMPION = "rival_aware"

#: Recorded, never gated: the previous champion, so the clock's rate against
#: it can be read beside #219's 15/16 for `rival_aware`.
REFERENCE = "dense_farm"

#: Fresh. 100-115 and 200-215 (#202), 300-331 (#211), 400-415 (#219) and
#: 500-515 (#222) are spent; re-using a range re-uses a measurement.
SEEDS = tuple(range(600, 616))
CHAMPION_BAR = 0.60
ANCHOR_BAR = 0.90
CONTROL_SEED = 600

#: The milk realisation arm (recorded, not gated). `meta_bot` is the one anchor
#: that runs a big herd of its own (9 cows, 4 sheep), so it is the only place
#: the declared risk -- our milk not holding up when the rival is also selling
#: milk -- can show. WOOL is measured beside it for contrast.
MILK_RIVAL = "meta_bot"
MILK_SEEDS = (600, 601)
ITEMS = ("MILK", "WOOL")


def realisation_rows(analysis, agent, seed, items=ITEMS):
    """One row per item from a `episode_analysis.price_realisation` result.

    An item the season never sold still gets a row, at zero: an absent row
    would read as "not measured" where the honest reading is "sold none".
    """
    summaries = analysis.get("items") or {}
    rows = []
    for item in items:
        s = summaries.get(item) or {}
        rows.append({"agent": agent, "seed": seed, "item": item,
                     "units": s.get("units", 0), "base": s.get("base", 0),
                     "mean_price": s.get("mean_price", 0.0),
                     "pct_of_base": s.get("pct_of_base", 0.0),
                     "late_pct_of_base": s.get("late_pct_of_base", 0.0)})
    return rows


def format_realisation(rows):
    """Header, then one line per row: who, which seed, item, units, realised."""
    lines = [f"{'agent':<16} {'seed':>4} {'item':<5} {'units':>6} {'base':>5} "
             f"{'mean':>8} {'%base':>7} {'late%':>7}"]
    for r in rows:
        lines.append(f"{r['agent']:<16} {r['seed']:>4} {r['item']:<5} {r['units']:>6} "
                     f"{r['base']:>5} {r['mean_price']:>8.1f} {r['pct_of_base']:>7.1%} "
                     f"{r['late_pct_of_base']:>7.1%}")
    return "\n".join(lines)


# --- live games -------------------------------------------------------------

def run_controls(seed=CONTROL_SEED):  # pragma: no cover
    """The two #225 controls. There is no quiet control: this contender does
    not read the rival, so there is no rival state that keeps it quiet."""
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")   # an instrument surfaces crashes
    from harness.tournament import play_rewards
    from kaggisim.strategy import make_agent
    from strategies import load
    out = {}
    # 1. identity with the switch day past the season
    off = type("Off", (load(CONTENDER),), {"DAY": 10 ** 9})
    base = play_rewards(make_agent(load(REFERENCE)()), make_agent(load(REFERENCE)()), seed)
    got = play_rewards(make_agent(off()), make_agent(load(REFERENCE)()), seed)
    # Positive control: base[0] > 0 is the identity control's own precondition
    # -- if no money moved, "got == base" is a vacuous match, not evidence.
    precondition_ok = base[0] > 0
    out["identity"] = {"ok": got == base and precondition_ok, "base": base, "got": got,
                       "precondition_ok": precondition_ok}
    # 2. mechanism fires against the champion: more cows, fewer sheep than
    #    `dense_farm` buys in the same matchup.
    c_actions, _ = action_stream(CONTENDER, CHAMPION, seed)
    b_actions, _ = action_stream(REFERENCE, CHAMPION, seed)
    c_counts, b_counts = animal_buys(c_actions), animal_buys(b_actions)
    out["mechanism"] = {"ok": mechanism_fired(c_counts, b_counts),
                        "contender": c_counts, "baseline": b_counts}
    return out


def run_criterion(seeds=SEEDS):  # pragma: no cover
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")   # an instrument surfaces crashes
    from harness.triage import head_to_head_rate
    champion_row = head_to_head_rate(CONTENDER, CHAMPION, seeds)
    anchor_rows = [head_to_head_rate(CONTENDER, a, seeds) for a in DEFAULT_ANCHORS]
    return champion_row, anchor_rows


def run_reference(seeds=SEEDS):  # pragma: no cover
    """The clock against the previous champion. Recorded, never gated."""
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")   # an instrument surfaces crashes
    from harness.triage import head_to_head_rate
    return head_to_head_rate(CONTENDER, REFERENCE, seeds)


def run_milk(agents=(CONTENDER, CHAMPION), seeds=MILK_SEEDS,
             rival=MILK_RIVAL, episode_steps=720):  # pragma: no cover
    """Realised MILK and WOOL prices for each agent in seat 0 against a
    cow-heavy rival. Recorded, not gated -- the declared risk on #225 is that
    milk stops paying when the rival is also on it, and this is where it shows.
    """
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")   # an instrument surfaces crashes
    from kaggle_environments import make
    from kaggisim.strategy import make_agent
    from harness.episode_analysis import price_realisation
    from strategies import load

    rows = []
    for agent in agents:
        for seed in seeds:
            env = make("kaggriculture", configuration={"episodeSteps": episode_steps,
                                                       "seed": seed})
            env.run([make_agent(load(agent)()), make_agent(load(rival)())])
            rows.extend(realisation_rows(price_realisation(env.steps, 0), agent, seed))
    return rows


def main(argv=None):  # pragma: no cover
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")   # an instrument surfaces crashes
    ap = argparse.ArgumentParser(description="#225 cows-from-day-8 clock: controls and criterion")
    ap.add_argument("--controls", action="store_true")
    ap.add_argument("--criterion", action="store_true")
    ap.add_argument("--reference", action="store_true",
                    help=f"vs {REFERENCE} on the same seeds (recorded, not gated)")
    ap.add_argument("--milk", action="store_true",
                    help=f"realised milk price vs {MILK_RIVAL} (recorded, not gated)")
    args = ap.parse_args(argv)
    if args.reference:
        print(format_rows([run_reference()]))
        print(f"reference (recorded, not gated): {CONTENDER} vs {REFERENCE}")
        return 0
    if args.milk:
        print(format_realisation(run_milk()))
        print(f"milk realisation (recorded, not gated): seat 0 vs {MILK_RIVAL}, "
              f"seeds {list(MILK_SEEDS)}")
        return 0
    do_controls = args.controls or not args.criterion
    do_criterion = args.criterion or not args.controls

    if do_controls:
        ctl = run_controls()
        for name, r in ctl.items():
            print(f"control {name}: {'OK' if r['ok'] else 'FAIL -- RUN VOID'}  {r}")
        if not all(r["ok"] for r in ctl.values()):
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
