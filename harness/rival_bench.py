"""#219: does buying cows when the rival runs sheep beat the champion?

    python -m harness.rival_bench --controls      # the three spec controls, ~2 min
    python -m harness.rival_bench --criterion     # 16 seeds x 7 opponents, ~8 min
    python -m harness.rival_bench --ablation      # unconditional-COW ablation, recorded not gated
    python -m harness.rival_bench --timing        # cows-from-day-N timing arm, recorded not gated
    python -m harness.rival_bench                 # both, controls first

Declared before code (docs/superpowers/specs/2026-09-06-rival-aware-herd-design.md):
seeds 400-415, sides alternated by list position (`harness.triage.head_to_head_rate`),
PROMOTE only at >= 60% of 16 vs the champion AND >= 90% vs each DEFAULT_ANCHOR;
a tie is not a win. Controls run first and a failed control voids the run.
Exit codes: 0 PROMOTE, 1 REJECTED, 2 VOID. Runs under ROBRICULTURE_STRICT=1.
"""

from __future__ import annotations

import argparse
import os

from harness.evolve import DEFAULT_ANCHORS

CHAMPION = "dense_farm"
CONTENDER = "rival_aware"
SEEDS = tuple(range(400, 416))
CHAMPION_BAR = 0.60
ANCHOR_BAR = 0.90
CONTROL_SEED = 400
QUIET_RIVAL = "wheat_hands"        # places no SHEEP (it does buy cows)

#: The cows-from-day-N timing arm (#219, declared 2026-09-06): does a clock
#: with no rival reading reproduce rival_aware's edge, or does the rival
#: signal do something a clock cannot? Recorded, not gated.
TIMING_DAYS = (4, 6, 8, 10, 12)
TIMING_NAME = "cows_from_day"


def animal_buys(actions):
    """{kind: count} of BUY_ANIMAL orders across a list of action dicts."""
    counts = {}
    for action in actions:
        for order in action.get("market", []):
            if order and order[0] == "BUY_ANIMAL" and len(order) >= 2:
                counts[order[1]] = counts.get(order[1], 0) + 1
    return counts


def mechanism_fired(contender_counts, baseline_counts):
    """More cows AND fewer sheep than the baseline, strictly."""
    return (contender_counts.get("COW", 0) > baseline_counts.get("COW", 0)
            and contender_counts.get("SHEEP", 0) < baseline_counts.get("SHEEP", 0))


def _rate(row):
    games = row["games"]
    return row["wins"] / games if games else 0.0


def criterion(champion_row, anchor_rows, champion_bar=CHAMPION_BAR, anchor_bar=ANCHOR_BAR):
    """The declared verdict: both bars, ties never wins."""
    champion_rate = _rate(champion_row)
    anchor_rates = {r["opponent"]: _rate(r) for r in anchor_rows}
    failing = ([champion_row["opponent"]] if champion_rate < champion_bar else []) + \
              [n for n, rate in anchor_rates.items() if rate < anchor_bar]
    return {"passed": not failing, "champion_rate": champion_rate,
            "anchor_rates": anchor_rates, "failing": failing}


def ablation_verdict(contender_wins, ablation_wins, games):
    """Does the rival-reading part of the mechanism do any work?

    `games` is unused in the comparison itself (both arms share the same seed
    count) but kept in the signature so a caller cannot pass mismatched win
    counts from differently-sized runs without the mismatch being visible at
    the call site. A gap of >= 2 wins is "does work"; within 1 is noise at
    this sample size ("cannot tell"); the ablation matching or beating the
    contender is "does no work" -- the rival signal added nothing beyond
    the cheaper-animal-buys-more-head effect (item A) that the ablation still
    carries.
    """
    gap = contender_wins - ablation_wins
    if gap >= 2:
        return "rival signal does work"
    if gap <= 0:
        return "rival signal does no work"
    return "cannot tell"


def first_day_at_or_above(series, threshold):
    """The first `day` in `series` (a list of `(day, value)` per turn, in
    order) whose `value >= threshold`; `None` if it is never reached.

    First match wins even if a later turn's value drops back below the
    threshold -- this answers "when did it first show up", not "is it still
    showing now"."""
    for day, value in series:
        if value >= threshold:
            return day
    return None


def format_timing(rows, contender_wins, ablation_wins):
    """One line per day-N row, then the two recorded reference rates."""
    lines = [f"{'N':>4} {'wins':>7} {'rate':>7}"]
    for r in rows:
        games = r["games"]
        rate = (r["wins"] / games) if games else 0.0
        lines.append(f"{r['day']:>4} {r['wins']:>3}/{games:<3} {rate:>7.1%}")
    lines.append(f"rival_aware {contender_wins}/16")
    lines.append(f"unconditional cows {ablation_wins}/16")
    return "\n".join(lines)


def timing_reading(rows, contender_wins, ablation_wins):
    """The declared reading rule for the timing arm:

    - some day-N row within 1 win of the contender -> a clock reproduces it,
      timing explains the gap;
    - every day-N row within 1 win of the ablation (at or below it) -> no
      clock gets past unconditional cows, the rival signal does something a
      clock cannot;
    - otherwise -> partial, name the best clock.
    """
    if any(r["wins"] >= contender_wins - 1 for r in rows):
        return "a clock reproduces the contender: timing explains the gap"
    if all(r["wins"] <= ablation_wins + 1 for r in rows):
        return ("no clock gets past unconditional cows: the rival signal "
                "does something a clock cannot")
    best = max(rows, key=lambda r: r["wins"])
    return f"partial: the best clock is N={best['day']} at {best['wins']}/{best['games']}"


def format_rows(rows):
    lines = [f"{'opponent':<16} {'wins':>7} {'ties':>4} {'rate':>6}"]
    for r in rows:
        lines.append(f"{r['opponent']:<16} {r['wins']:>3}/{r['games']:<3} {r.get('ties', 0):>4} "
                     f"{_rate(r):>6.1%}")
    return "\n".join(lines)


# --- live games -------------------------------------------------------------

def action_stream(strategy_name, opponent_name, seed, episode_steps=720):  # pragma: no cover
    """Our per-turn actions in seat 0 against `opponent_name`, plus the rival's
    placed-animal counts at the end (the precondition for control 2)."""
    from kaggle_environments import make
    from kaggisim.strategy import make_agent
    from strategies import load
    env = make("kaggriculture", configuration={"episodeSteps": episode_steps, "seed": seed})
    env.reset(2)
    ours = make_agent(load(strategy_name)())
    theirs = make_agent(load(opponent_name)())
    actions = []
    for _ in range(episode_steps - 1):
        act0 = ours(env.state[0].observation)
        actions.append(act0)
        env.step([act0, theirs(env.state[1].observation)])
    rival = env.state[1].observation["farms"][1]["tiles"]
    placed = {}
    for row in rival:
        for t in row:
            if isinstance(t, dict) and t.get("animal"):
                placed[t["animal"]] = placed.get(t["animal"], 0) + 1
    return actions, placed


def run_controls(seed=CONTROL_SEED):  # pragma: no cover
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")   # an instrument surfaces crashes
    from harness.tournament import play_rewards
    from kaggisim.strategy import make_agent
    from strategies import load
    out = {}
    # 1. identity with the threshold off
    off = type("Off", (load(CONTENDER),), {"THRESHOLD": 10 ** 9})
    base = play_rewards(make_agent(load(CHAMPION)()), make_agent(load(CHAMPION)()), seed)
    got = play_rewards(make_agent(off()), make_agent(load(CHAMPION)()), seed)
    # Positive control: base[0] > 0 is the identity control's own precondition
    # -- if no money moved, "got == base" is a vacuous match, not evidence.
    precondition_ok = base[0] > 0
    out["identity"] = {"ok": got == base and precondition_ok, "base": base, "got": got,
                       "precondition_ok": precondition_ok}
    # 2. mechanism fires against the champion (which runs sheep when rich)
    c_actions, rival_placed = action_stream(CONTENDER, CHAMPION, seed)
    b_actions, _ = action_stream(CHAMPION, CHAMPION, seed)
    c_counts, b_counts = animal_buys(c_actions), animal_buys(b_actions)
    out["mechanism"] = {"ok": rival_placed.get("SHEEP", 0) >= 2 and mechanism_fired(c_counts, b_counts),
                        "rival_sheep_placed": rival_placed.get("SHEEP", 0),
                        "contender": c_counts, "baseline": b_counts}
    # 3. quiet against a rival with no sheep: identical action stream
    q_actions, q_placed = action_stream(CONTENDER, QUIET_RIVAL, seed)
    qb_actions, _ = action_stream(CHAMPION, QUIET_RIVAL, seed)
    out["quiet"] = {"ok": q_placed.get("SHEEP", 0) == 0 and q_actions == qb_actions,
                    "rival_sheep_placed": q_placed.get("SHEEP", 0)}
    return out


def run_criterion(seeds=SEEDS):  # pragma: no cover
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")   # an instrument surfaces crashes
    from harness.triage import head_to_head_rate
    champion_row = head_to_head_rate(CONTENDER, CHAMPION, seeds)
    anchor_rows = [head_to_head_rate(CONTENDER, a, seeds) for a in DEFAULT_ANCHORS]
    return champion_row, anchor_rows


#: The rival-reading contender's recorded rate against the champion (#219
#: PROMOTE run, issue comment) -- cited here, not re-measured, so the
#: ablation's printed line can compare against it without re-running the
#: (already-run, not-to-be-re-run) criterion.
CONTENDER_CHAMPION_WINS = 15

#: Ablation name, used only as the key `agents()` recognises below -- never
#: registered in strategies/, so it cannot be promoted or submitted by accident.
ABLATION_NAME = "always_cow"

#: The unconditional-COW ablation's recorded rate against the champion (#219
#: ablation addendum, issue comment, 2026-09-06) -- cited here, not
#: re-measured, so the timing arm's printed line can compare against it
#: without re-running the (already-run, not-to-be-re-run) ablation.
ABLATION_CHAMPION_WINS = 11


def run_ablation(seeds=SEEDS):  # pragma: no cover
    """Recommendation 1: an unconditional-COW ablation of the contender.

    `AlwaysCow` is `rival_aware` with `herd_preference` forced to always
    return "COW" -- it carries every other decision (crop caps, ramps, the
    cheaper-animal-buys-more-head effect from item A) but never reads
    `rival_sheep`. If it does about as well as the contender against the
    champion, the rival-reading part of the mechanism is doing no work; the
    win is coming from buying cows unconditionally. Built in-process and
    never registered, so it cannot be promoted or packaged by accident.
    """
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")   # an instrument surfaces crashes
    from harness.triage import head_to_head_rate
    from kaggisim.strategy import make_agent
    from strategies import load

    AlwaysCow = type("AlwaysCow", (load(CONTENDER),),
                     {"herd_preference": lambda self, obs: "COW"})
    default_agents = None  # triage's own default, resolved lazily per call

    def agents(name):
        if name == ABLATION_NAME:
            return make_agent(AlwaysCow())
        nonlocal default_agents
        if default_agents is None:
            from harness.triage import _default_agents
            default_agents = _default_agents()
        return default_agents(name)

    return head_to_head_rate(ABLATION_NAME, CHAMPION, seeds, agents=agents)


def first_fire_days(seeds=SEEDS, episode_steps=720):  # pragma: no cover
    """The day rival_aware's rule first fires (rival sheep >= SHEEP_THRESHOLD)
    in each seeded game against the champion -- when the signal shows up,
    not whether it wins. Drives the game step by step like `action_stream`,
    but records the rival-sheep series for seat 0's observation each turn
    instead of the action stream. Seat alternation is not needed here."""
    from kaggle_environments import make
    from kaggisim.strategy import make_agent
    from strategies import field_rival as fr
    from strategies import load
    from strategies.rival_aware import SHEEP_THRESHOLD

    results = {}
    for seed in seeds:
        env = make("kaggriculture", configuration={"episodeSteps": episode_steps, "seed": seed})
        env.reset(2)
        ours = make_agent(load(CONTENDER)())
        theirs = make_agent(load(CHAMPION)())
        series = []
        for _ in range(episode_steps - 1):
            obs0 = env.state[0].observation
            series.append((obs0.get("day", 0), fr.rival_sheep(obs0)))
            act0 = ours(obs0)
            act1 = theirs(env.state[1].observation)
            env.step([act0, act1])
        results[seed] = first_day_at_or_above(series, SHEEP_THRESHOLD)
    return results


def run_timing_arm(days=TIMING_DAYS, seeds=SEEDS):  # pragma: no cover
    """The cows-from-day-N ablation: a `dense_farm`-shaped variant whose
    `herd_preference` returns COW from day N on -- never reading the rival --
    played against the champion on the same seeds as the contender and the
    unconditional-COW ablation. Answers whether a plain clock reproduces
    rival_aware's edge, i.e. whether the win is *timing* rather than the
    rival-reading itself. Built in-process per N and never registered, so it
    cannot be promoted or packaged by accident."""
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")   # an instrument surfaces crashes
    from harness.triage import _default_agents, head_to_head_rate
    from kaggisim.strategy import make_agent
    from strategies import load

    def make_agents(day_cow_cls, day_name):
        default_agents = None

        def agents(name):
            if name == day_name:
                return make_agent(day_cow_cls())
            nonlocal default_agents
            if default_agents is None:
                default_agents = _default_agents()
            return default_agents(name)
        return agents

    rows = []
    for n in days:
        # `_n=n` binds the loop variable at definition time -- without it
        # every DayNCow's herd_preference would close over the same final
        # `n` and every arm would fire on the same day.
        DayNCow = type(f"CowsFromDay{n}", (load(CONTENDER),),
                       {"herd_preference": lambda self, obs, _n=n:
                        "COW" if int(obs.get("day", 0)) >= _n else None})
        name = f"{TIMING_NAME}_{n}"
        row = head_to_head_rate(name, CHAMPION, seeds, agents=make_agents(DayNCow, name))
        row["day"] = n
        rows.append(row)
    return rows


def main(argv=None):  # pragma: no cover
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")   # an instrument surfaces crashes
    ap = argparse.ArgumentParser(description="#219 rival-aware herd: controls and criterion")
    ap.add_argument("--controls", action="store_true")
    ap.add_argument("--criterion", action="store_true")
    ap.add_argument("--ablation", action="store_true",
                    help="unconditional-COW ablation vs the champion (recorded, not gated)")
    ap.add_argument("--timing", action="store_true",
                    help="cows-from-day-N timing arm vs the champion (recorded, not gated)")
    args = ap.parse_args(argv)
    if args.timing:
        import statistics
        fire_days = first_fire_days()
        print("first-fire day per seed (rival_aware vs dense_farm, rival sheep >= threshold):")
        for seed, day in fire_days.items():
            print(f"  {seed}: {day if day is not None else 'never'}")
        finite = [d for d in fire_days.values() if d is not None]
        median = statistics.median(finite) if finite else None
        print(f"median first-fire day: {median if median is not None else 'n/a'}")
        rows = run_timing_arm()
        print(format_timing(rows, CONTENDER_CHAMPION_WINS, ABLATION_CHAMPION_WINS))
        print(timing_reading(rows, CONTENDER_CHAMPION_WINS, ABLATION_CHAMPION_WINS))
        return 0
    if args.ablation:
        row = run_ablation()
        print(format_rows([row]))
        verdict = ablation_verdict(CONTENDER_CHAMPION_WINS, row["wins"], row["games"])
        print(f"ablation (recorded, not gated): unconditional COW vs {CHAMPION} = "
              f"{row['wins']}/{row['games']}; the rival-reading contender was "
              f"{CONTENDER_CHAMPION_WINS}/{row['games']} — if these match, the rival "
              f"signal does no work")
        print(f"ablation_verdict: {verdict}")
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
        v = criterion(champion_row, anchor_rows)
        print(f"champion {v['champion_rate']:.1%} (bar {CHAMPION_BAR:.0%}); anchors below {ANCHOR_BAR:.0%}: "
              f"{v['failing'] or 'none'} -> {'PROMOTE' if v['passed'] else 'REJECTED'}")
        return 0 if v["passed"] else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
