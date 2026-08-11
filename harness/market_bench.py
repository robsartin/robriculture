"""Honest market benchmark — grade a strategy on what the ladder rewards.

The ladder is a shared-market 1v1: what wins is *out-earning the opponent in the
same game*, not solo money, and not out-earning our own melon lineage. This
benchmark therefore scores a candidate against a **diverse adversary panel**,
each member of which stresses a different market:

  * ``melon_flooder`` — `wide_hands`, a 10-tile melon crew that dumps melon early
    and crashes the shared, zero-replenishment melon market (the classic denial
    play against a melon-dependent agent).
  * ``wheat_farmer``   — `wheat_hands`, contests the bottomless wheat spine.
  * ``carrot_starter`` — the built-in ``starter`` carrot loop.
  * ``ranch_hands``    — our own champion (melon + livestock), the incumbent bar.
  * ``random``         — the built-in noise agent (sanity floor).

For the candidate it reports, over `--games` seeded games with sides alternated
to cancel first-player advantage:

  * mean final money (absolute earning power), and
  * head-to-head win-rate + mean money-margin vs EACH adversary.

The bar to clear: beat ``ranch_hands`` in absolute mean money AND win the
head-to-head vs each adversary, especially the melon-flooder.

Usage:
    python -m harness.market_bench market_farmer --games 24
"""

from __future__ import annotations

import argparse
import os
import statistics
import sys

os.environ.setdefault("ROBRICULTURE_STRICT", "1")

from kaggle_environments import make

from kaggisim.strategy import make_agent
from strategies import REGISTRY, load

#: The diverse adversary panel: label -> strategy/built-in name.
ADVERSARIES = {
    "melon_flooder": "wide_hands",
    "wheat_farmer": "wheat_hands",
    "carrot_starter": "starter",
    "ranch_hands": "ranch_hands",
    "random": "random",
}

_BUILTINS = ("starter", "random", "pass")


def _agent(name):
    return make_agent(load(name)()) if name not in _BUILTINS else name


def play_money(a_name, b_name, seed):  # pragma: no cover
    """Play one seeded game; return (money_a, money_b) as floats."""
    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
    env.run([_agent(a_name), _agent(b_name)])
    ra, rb = (s.reward for s in env.steps[-1])
    return (ra or 0.0), (rb or 0.0)


def head_to_head(candidate, opponent, games):  # pragma: no cover
    """Seeded match with alternating sides. Returns a stats dict.

    Sides alternate each game so any first-player edge cancels; margins are the
    candidate's money minus the opponent's, always from the candidate's view.
    """
    wins = losses = ties = 0
    margins = []
    cand_money = []
    for i in range(games):
        seed = i
        if i % 2 == 0:
            mc, mo = play_money(candidate, opponent, seed)
        else:
            mo, mc = play_money(opponent, candidate, seed)
        margins.append(mc - mo)
        cand_money.append(mc)
        if mc > mo:
            wins += 1
        elif mc < mo:
            losses += 1
        else:
            ties += 1
    decisive = wins + losses
    return {
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "win_rate": (wins / decisive) if decisive else 0.5,
        "mean_margin": statistics.mean(margins) if margins else 0.0,
        "mean_money": statistics.mean(cand_money) if cand_money else 0.0,
    }


def benchmark(candidate, games=24, adversaries=None):  # pragma: no cover
    """Run the candidate against every adversary; return {label: stats}."""
    adversaries = adversaries or ADVERSARIES
    return {
        label: head_to_head(candidate, name, games)
        for label, name in adversaries.items()
    }


def format_report(candidate, results):
    lines = [f"=== market benchmark: {candidate} ({sum(1 for _ in results)} adversaries) ==="]
    all_money = []
    for label, s in results.items():
        all_money.append(s["mean_money"])
        lines.append(
            f"  vs {label:16s}  win {s['win_rate']:5.1%} "
            f"({s['wins']}-{s['losses']}-{s['ties']})  "
            f"margin {s['mean_margin']:+8.0f}  "
            f"cand_money {s['mean_money']:8.0f}"
        )
    lines.append(f"  overall mean final money: {statistics.mean(all_money):.0f}")
    return "\n".join(lines)


def main(argv=None):  # pragma: no cover
    ap = argparse.ArgumentParser(description="honest shared-market benchmark")
    ap.add_argument("candidate", help="strategy name to grade")
    ap.add_argument("--games", type=int, default=24, help="games per adversary (default 24)")
    args = ap.parse_args(argv)

    if args.candidate not in REGISTRY:
        ap.error(f"unknown strategy {args.candidate!r}; known: {sorted(REGISTRY)}")

    results = benchmark(args.candidate, games=args.games)
    print(format_report(args.candidate, results))
    return 0


if __name__ == "__main__":
    sys.exit(main())
