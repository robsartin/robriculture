"""Round history + windowed champion selection (#12).

`harness/promotion.py` designates a champion from a *single* round-robin. As our
strategies evolve, one snapshot is noisy and ignores recency — a round we ran
today (with better agents) should count more than a stale one. This module keeps
an append-only history of rounds and picks the champion by aggregated win-rate
over the current + recent `window` rounds (default 3), optionally recency-weighted.

A round is:  {"round": int, "games": int, "results": {name: {"wins", "played"}}}
Round ids are integer and increasing (no wall-clock — keeps the history
reproducible). The history lives in `harness/rounds.json`; the derived champion
in `harness/champion.json`.
"""

from __future__ import annotations

import json
import os

from harness.promotion import CHAMPION_PATH, round_robin_rank, save_champion, top_contender
from harness.tournament import BUILTINS, build_agents, play

#: Default recent-round window for champion selection (see #12; confirmed N=3).
DEFAULT_WINDOW = 3

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


def windowed_ranking(rounds, window=DEFAULT_WINDOW, decay=None):
    """Rank agents by win-rate aggregated over the last `window` rounds.

    `decay` (0 < decay <= 1) weights older rounds down: the most recent round has
    weight 1, the one before it `decay`, then `decay**2`, ... Default (None) is
    equal weight. Returns `(name, win_rate, wtd_wins, wtd_played)` best first.
    """
    recent = rounds[-window:] if window else list(rounds)
    n = len(recent)
    agg: dict[str, list[float]] = {}
    for idx, rnd in enumerate(recent):
        age = n - 1 - idx  # 0 == most recent
        weight = (decay ** age) if decay is not None else 1.0
        for name, res in rnd["results"].items():
            slot = agg.setdefault(name, [0.0, 0.0])
            slot[0] += weight * res["wins"]
            slot[1] += weight * res["played"]
    ranking = [
        (name, (w / p if p else 0.0), w, p) for name, (w, p) in agg.items()
    ]
    ranking.sort(key=lambda row: row[1], reverse=True)
    return ranking


def designate_from_history(path=ROUNDS_PATH, window=DEFAULT_WINDOW, decay=None, benchmarks=None):
    """The champion implied by the recent-round window.

    `benchmarks` (a set of names) shape the ranking as opponents but are never
    returned as champion (see `harness.promotion.top_contender`).
    """
    ranking = windowed_ranking(load_rounds(path), window=window, decay=decay)
    return top_contender([row[0] for row in ranking], benchmarks or set())


def run_round(names, games=20, play_fn=play, build=build_agents):
    """Play one round-robin and return it as a round record (wins/played per agent)."""
    ranking = round_robin_rank(build(names), games=games, play_fn=play_fn)
    return {
        "games": games,
        "results": {name: {"wins": w, "played": p} for (name, _wr, w, p) in ranking},
    }


def run_and_record(names, games=20, window=DEFAULT_WINDOW, decay=None,
                   rounds_path=ROUNDS_PATH, champion_path=CHAMPION_PATH,
                   play_fn=play, build=build_agents, benchmarks=None):
    """Play a round, append it to history, re-designate the champion from the window.

    `benchmarks` (a set of names) are opponents in the round but never champion.
    """
    benchmarks = benchmarks or set()
    rnd = run_round(names, games=games, play_fn=play_fn, build=build)
    append_round(rounds_path, rnd)
    ranking = windowed_ranking(load_rounds(rounds_path), window=window, decay=decay)
    champion = top_contender([row[0] for row in ranking], benchmarks)
    save_champion(champion_path, champion, games, ranking)
    return champion, ranking


def main(argv=None):  # pragma: no cover
    import argparse

    from harness.tournament import benchmark_names
    from strategies import REGISTRY

    ap = argparse.ArgumentParser(description="run a round and update the champion (windowed)")
    ap.add_argument("names", nargs="*", help="agents (default: all strategies + built-ins)")
    ap.add_argument("--games", type=int, default=20, help="games per pairing (default 20)")
    ap.add_argument("--window", type=int, default=DEFAULT_WINDOW, help=f"recent-round window (default {DEFAULT_WINDOW})")
    ap.add_argument("--decay", type=float, default=None, help="optional recency decay in (0,1]")
    args = ap.parse_args(argv)
    names = args.names or (list(REGISTRY) + list(BUILTINS))
    print(f"Running a round over {names} ({args.games} games/pairing)...")
    champion, ranking = run_and_record(
        names, games=args.games, window=args.window, decay=args.decay,
        benchmarks=benchmark_names(),
    )
    for name, wr, w, p in ranking:
        print(f"  {name:16s} {wr:6.1%}  ({w:g}/{p:g})")
    print(f"\nChampion (window={args.window}): {champion}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    import sys

    sys.exit(main())
