"""Local tournament harness — our unlimited exploration ground.

Runs a round-robin among our strategies (and the built-in "pass"/"random"/
"starter" bots) over many seeds and reports win-rates. This is our primary
fitness signal, so we don't burn real ladder submissions to compare ideas
(ADR-0003). A full 720-turn game runs in ~2s, so thousands of games are cheap.

Usage:
    python -m harness.tournament                     # all strategies vs built-ins
    python -m harness.tournament lean greedy         # just these
    python -m harness.tournament --games 50          # seeds per pairing

Run from the repo root (so `kaggisim` and `strategies` are importable), with the
venv active.
"""

from __future__ import annotations

import argparse
import itertools
import sys

from kaggle_environments import make

from kaggisim.strategy import make_agent
from strategies import REGISTRY, load

BUILTINS = ("starter", "random")


def build_agents(names):
    """Map names to (label, agent_callable). Built-in names pass through as strings."""
    agents = {}
    for n in names:
        if n in REGISTRY:
            agents[n] = make_agent(load(n)())
        else:
            agents[n] = n  # built-in: kaggle_environments resolves the string
    return agents


def play(agent_a, agent_b, seed=None):
    """Play one game. Return 1 if A wins, -1 if B wins, 0 tie."""
    config = {"episodeSteps": 720}
    if seed is not None:
        config["seed"] = seed
    env = make("kaggriculture", configuration=config)
    env.run([agent_a, agent_b])
    ra, rb = (s.reward for s in env.steps[-1])
    ra = ra or 0
    rb = rb or 0
    return (ra > rb) - (ra < rb)


def round_robin(names, games=20):
    agents = build_agents(names)
    labels = list(agents)
    wins = {n: 0 for n in labels}
    played = {n: 0 for n in labels}

    for a, b in itertools.combinations(labels, 2):
        for g in range(games):
            # Alternate sides to cancel any first-player advantage.
            if g % 2 == 0:
                r = play(agents[a], agents[b], seed=g)
            else:
                r = -play(agents[b], agents[a], seed=g)
            played[a] += 1
            played[b] += 1
            if r > 0:
                wins[a] += 1
            elif r < 0:
                wins[b] += 1
        print(f"  {a} vs {b}: done ({games} games)")

    print("\n=== Win rates ===")
    ranking = sorted(labels, key=lambda n: wins[n] / max(played[n], 1), reverse=True)
    for n in ranking:
        rate = wins[n] / max(played[n], 1)
        print(f"  {n:16s} {rate:5.1%}  ({wins[n]}/{played[n]})")
    return wins, played


def main(argv=None):
    ap = argparse.ArgumentParser(description="robriculture local tournament")
    ap.add_argument("strategies", nargs="*", help="strategy names (default: all + built-ins)")
    ap.add_argument("--games", type=int, default=20, help="games per pairing (default 20)")
    args = ap.parse_args(argv)

    names = args.strategies or (list(REGISTRY) + list(BUILTINS))
    print(f"Tournament: {names}  ({args.games} games/pairing)\n")
    round_robin(names, games=args.games)
    return 0


if __name__ == "__main__":
    sys.exit(main())
