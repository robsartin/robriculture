"""Round history + champion designation (#12, rerouted by #76).

Designation is by pool share (`harness/promotion.designate`), not round history —
`harness/promotion.py` designates a champion from a single round-robin against a
fixed anchor pool. This module keeps an append-only history of rounds as a
committed record; `run_and_record` plays a round, appends it to that history,
and then re-designates by delegating to `promotion.designate`. The history is no
longer read for designation.

A round is:  {"round": int, "games": int, "results": {name: {"wins", "played"}}}
Round ids are integer and increasing (no wall-clock — keeps the history
reproducible). The history lives in `harness/rounds.json`; the derived champion
in `harness/champion.json`.
"""

from __future__ import annotations

import json
import os

from harness import promotion
from harness.promotion import CHAMPION_PATH, round_robin_rank, save_champion
from harness.tournament import BUILTINS, build_agents, play

#: Append-only round history (a committed decision trail).
ROUNDS_PATH = os.path.join(os.path.dirname(__file__), "rounds.json")


def load_rounds(path=ROUNDS_PATH):
    if not os.path.exists(path):
        return []
    with open(path) as fh:
        return json.load(fh)


def append_round(path, round_result):
    """Append a round, stamping it with the next sequential round id."""
    rounds = load_rounds(path)
    rnd = dict(round_result)
    rnd["round"] = len(rounds) + 1
    rounds.append(rnd)
    with open(path, "w") as fh:
        json.dump(rounds, fh, indent=2)
        fh.write("\n")
    return rnd


def run_round(names, games=20, play_fn=play, build=build_agents):
    """Play one round-robin and return it as a round record (wins/played per agent)."""
    ranking = round_robin_rank(build(names), games=games, play_fn=play_fn)
    return {
        "games": games,
        "results": {name: {"wins": w, "played": p} for (name, _wr, w, p) in ranking},
    }


def run_and_record(names, games=20, rounds_path=ROUNDS_PATH,
                   champion_path=CHAMPION_PATH, play_fn=play, rewards_fn=None,
                   build=build_agents, benchmarks=None, pool=None):
    """Play a round, append it to history, and re-designate by pool share.

    Designation delegates to `promotion.designate` rather than ranking the round
    itself. If this routine kept designating from round win-rate, one ordinary run
    would silently overwrite the share-based champion and re-crown market_farmer
    (#76) — a fix undone invisibly is worse than no fix.
    """
    benchmarks = benchmarks or set()
    rnd = run_round(names, games=games, play_fn=play_fn, build=build)
    append_round(rounds_path, rnd)

    agents = build(names)
    pool_agents = build(list(pool)) if pool is not None else agents
    kw = {"games": games, "benchmarks": benchmarks}
    if rewards_fn is not None:
        kw["rewards_fn"] = rewards_fn
    body = promotion.designate(agents, pool_agents, **kw)
    save_champion(champion_path, body)
    return body["gate_opponent"], body


def main(argv=None):  # pragma: no cover
    import argparse

    from harness.tournament import benchmark_names
    from strategies import REGISTRY

    ap = argparse.ArgumentParser(description="run a round and re-designate the champion (pool share)")
    ap.add_argument("names", nargs="*", help="agents (default: all strategies + built-ins)")
    ap.add_argument("--games", type=int, default=20, help="games per pairing (default 20)")
    args = ap.parse_args(argv)
    names = args.names or (list(REGISTRY) + list(BUILTINS))
    print(f"Running a round over {names} ({args.games} games/pairing)...")

    from harness.evolve import DEFAULT_ANCHORS

    champion, body = run_and_record(
        names, games=args.games, benchmarks=benchmark_names(),
        pool=list(DEFAULT_ANCHORS),
    )
    for row in body["ranking"]:
        mark = " (benchmark)" if row["benchmark"] else ""
        print(f"  {row['name']:16s} share={row['share']:.4f}{mark}")
    print(f"\ngate_opponent:  {body['gate_opponent']}")
    print(f"submit_default: {body['submit_default']}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    import sys

    sys.exit(main())
