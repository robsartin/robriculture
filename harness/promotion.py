"""Promotion harness — ADR-0007's strategy-experiment gate.

A strategy experiment is promoted only if its challenger is *actually better*
than the current champion. "Better" is not a green test; it's a statistical
claim: over a fixed set of seeded games, the challenger must both clear a
win-rate bar and beat a fair-coin null by a binomial test. This module provides
the reproducible measurement (`run_match`), the decision (`PromotionResult`),
and the tooling to designate a champion (`designate_champion`).

Ties are excluded from the win-rate and the binomial test (a paired-sign-test
convention): they carry no information about which agent is stronger, but the
tie-rate is reported alongside so a draw-heavy match is visible.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from math import comb


def binomial_p_value(wins: int, decisive: int) -> float:
    """One-sided exact binomial p-value: P(X >= wins | n=decisive, p=0.5).

    The chance a fair coin would give the challenger at least `wins` of
    `decisive` decisive games. Small p => the win-rate is hard to explain by
    luck. With no decisive games there is no evidence, so p = 1.0.
    """
    if decisive <= 0:
        return 1.0
    wins = max(0, min(wins, decisive))
    tail = sum(comb(decisive, k) for k in range(wins, decisive + 1))
    return tail / (2 ** decisive)


@dataclass(frozen=True)
class Record:
    """A challenger's tally against one opponent."""

    wins: int
    losses: int
    ties: int = 0

    @property
    def games(self) -> int:
        return self.wins + self.losses + self.ties

    @property
    def decisive(self) -> int:
        return self.wins + self.losses

    @property
    def win_rate(self) -> float:
        """Fraction of *decisive* games won; 0.5 when there are none."""
        return self.wins / self.decisive if self.decisive else 0.5

    @property
    def tie_rate(self) -> float:
        return self.ties / self.games if self.games else 0.0

    @property
    def p_value(self) -> float:
        return binomial_p_value(self.wins, self.decisive)


@dataclass(frozen=True)
class PromotionResult:
    """The verdict for a challenger vs a champion over a seeded match."""

    challenger: str
    champion: str
    record: Record
    bar: float = 0.55
    alpha: float = 0.05

    @property
    def win_rate(self) -> float:
        return self.record.win_rate

    @property
    def p_value(self) -> float:
        return self.record.p_value

    @property
    def passed(self) -> bool:
        """Promote iff the win-rate clears the bar AND it beats the coin-flip null."""
        return self.record.win_rate >= self.bar and self.record.p_value < self.alpha


# --- Game-running ---

import itertools
import os

from harness.evolve import match_share
from harness.tournament import build_agents, play
from harness.tournament import play_rewards as _play_rewards

#: Where the designated champion is recorded (a committed decision artifact).
CHAMPION_PATH = os.path.join(os.path.dirname(__file__), "champion.json")


def run_match(challenger_agent, champion_agent, games=200, seeds=None, play_fn=play):
    """Play a seeded match and tally it from the *challenger's* point of view.

    Sides alternate each game to cancel any first-player advantage; the raw
    result is negated on games where the challenger plays second. `seeds`
    overrides the default `range(games)` (and sets the game count).
    """
    if seeds is None:
        seeds = range(games)
    wins = losses = ties = 0
    for i, seed in enumerate(seeds):
        if i % 2 == 0:
            r = play_fn(challenger_agent, champion_agent, seed)
        else:
            r = -play_fn(champion_agent, challenger_agent, seed)
        if r > 0:
            wins += 1
        elif r < 0:
            losses += 1
        else:
            ties += 1
    return Record(wins, losses, ties)


def round_robin_rank(agents, games=20, play_fn=play):
    """Round-robin among `agents` (a {label: agent} map); rank by win-rate.

    Returns a list of `(label, win_rate, wins, played)` ordered best first.
    """
    labels = list(agents)
    wins = {n: 0 for n in labels}
    played = {n: 0 for n in labels}
    for a, b in itertools.combinations(labels, 2):
        for g in range(games):
            r = play_fn(agents[a], agents[b], g) if g % 2 == 0 else -play_fn(agents[b], agents[a], g)
            played[a] += 1
            played[b] += 1
            if r > 0:
                wins[a] += 1
            elif r < 0:
                wins[b] += 1
    ranking = [
        (n, wins[n] / played[n] if played[n] else 0.0, wins[n], played[n])
        for n in labels
    ]
    ranking.sort(key=lambda row: row[1], reverse=True)
    return ranking


def pool_share_rank(candidates, pool, games=2, seed_base=0,
                    rewards_fn=_play_rewards, benchmarks=None):
    """Rank `candidates` by mean score share against `pool`, best first.

    Share (`me / (me + opp)`, from #70) instead of win-rate, because win/loss
    throws away margin: `market_farmer` won 160/160 head-to-head on margins of
    ~3%, which crowned it champion while it ranked last on the ladder. Share
    puts it within 0.0015 of two other agents — which is the truth.

    A candidate is never its own opponent: a self-match scores 0.5 by
    construction and would pull every share toward the mean.
    """
    if not pool:
        raise ValueError("cannot rank against an empty pool")
    benchmarks = benchmarks or set()
    rows = []
    for name, agent in candidates.items():
        opponents = [a for opp_name, a in pool.items() if opp_name != name]
        if not opponents:
            raise ValueError(
                f"candidate {name!r} has no opponents: it is the only entry in the pool, "
                f"and a candidate never plays itself"
            )
        rows.append({
            "name": name,
            "share": match_share(agent, opponents, games, seed_base, rewards_fn),
            "benchmark": name in benchmarks,
        })
    rows.sort(key=lambda r: r["share"], reverse=True)
    return rows


CRITERION = "pool_share"


def designate(candidates, pool, games=2, seed_base=0,
              rewards_fn=_play_rewards, benchmarks=None):
    """Rank by pool share and split the result into the champion's two roles.

    `gate_opponent` is the outright leader — benchmarks included, because the
    gate wants the most demanding representative bar available.

    `submit_default` is the leading non-benchmark. `scripts/submit.py` packages
    it with no arguments, so a vendored external agent must never land here:
    submitting a competitor's code is pointless and an ADR-0005 licensing and
    attribution problem. One field cannot answer both questions, which is why
    there are two.
    """
    benchmarks = benchmarks or set()
    ranking = pool_share_rank(candidates, pool, games=games, seed_base=seed_base,
                              rewards_fn=rewards_fn, benchmarks=benchmarks)
    return {
        "criterion": CRITERION,
        "gate_opponent": ranking[0]["name"],
        "submit_default": top_contender([r["name"] for r in ranking], benchmarks),
        "games": games,
        "pool": list(pool),
        "ranking": ranking,
    }


def top_contender(names, benchmarks):
    """The first name that is not a benchmark opponent.

    Takes best-first *names*. `pool_share_rank` emits dicts, and unpacking those
    as `(label, *rest)` tuples would silently iterate their keys instead of
    raising — so the row shape is names, and callers project explicitly.

    Benchmarks are vendored external agents: they make excellent gate opponents
    but must never be a submit default (ADR-0005 licensing). Raises ValueError
    if every name is a benchmark.
    """
    for name in names:
        if name not in benchmarks:
            return name
    raise ValueError("no non-benchmark contender in ranking")


def designate_champion(names, games=20, play_fn=play, build=build_agents, benchmarks=None):
    """Run a round-robin among `names` and return the strongest *non-benchmark* label.

    `build` maps names to agents (built-ins like "starter"/"random" pass through
    as strings); it is injectable so the ranking logic can be tested without
    running real games. `benchmarks` (a set of names) are opponents but never
    champion candidates.
    """
    benchmarks = benchmarks or set()
    ranking = round_robin_rank(build(names), games=games, play_fn=play_fn)
    return top_contender([row[0] for row in ranking], benchmarks)


def save_champion(path, body):
    """Write the designation artifact (a `designate()` body) as JSON."""
    with open(path, "w") as fh:
        json.dump(body, fh, indent=2)
        fh.write("\n")


def _read_role(path, field):
    """Read one role from the artifact, failing loudly on the old single-field format."""
    with open(path) as fh:
        data = json.load(fh)
    if field not in data:
        raise ValueError(
            f"{path!r} has no {field!r} — it predates the two-role split (#76). "
            f"re-designate with: python -m harness.promotion --designate"
        )
    return data[field]


def gate_opponent(path=CHAMPION_PATH):
    """The opponent an ADR-0007 promotion test measures against. May be a benchmark."""
    return _read_role(path, "gate_opponent")


def submit_default(path=CHAMPION_PATH):
    """The strategy `scripts/submit.py` packages by default. Never a benchmark."""
    return _read_role(path, "submit_default")


def promotion_test(
    challenger_name,
    champion_name=None,
    games=200,
    bar=0.55,
    alpha=0.05,
    play_fn=play,
    build=build_agents,
):
    """Run the ADR-0007 promotion test: challenger vs champion over seeded games."""
    if champion_name is None:
        champion_name = gate_opponent()
    agents = build([challenger_name, champion_name])
    record = run_match(
        agents[challenger_name], agents[champion_name], games=games, play_fn=play_fn
    )
    return PromotionResult(challenger_name, champion_name, record, bar=bar, alpha=alpha)


# --- CLI: thin glue over the tested functions above ---

def main(argv=None):  # pragma: no cover
    import argparse
    import sys

    from strategies import REGISTRY

    ap = argparse.ArgumentParser(description="robriculture promotion test / champion designation")
    ap.add_argument("challenger", nargs="?", help="strategy name to test (omit with --designate)")
    ap.add_argument("--champion", help="opponent name (default: the recorded champion)")
    ap.add_argument("--games", type=int, default=200, help="seeded games (default 200)")
    ap.add_argument("--bar", type=float, default=0.55, help="win-rate bar (default 0.55)")
    ap.add_argument("--alpha", type=float, default=0.05, help="significance level (default 0.05)")
    ap.add_argument("--designate", action="store_true",
                    help="rank all strategies by pool share against the fixed anchors and record both roles (gate_opponent, submit_default)")
    ap.add_argument("names", nargs="*", help="agents to rank (for --designate; default: all + built-ins)")
    args = ap.parse_args(argv)

    if args.designate:
        from harness.evolve import DEFAULT_ANCHORS
        from harness.tournament import benchmark_names
        from strategies import REGISTRY

        bench = benchmark_names()
        pool = build_agents(list(DEFAULT_ANCHORS))
        candidates = build_agents(list(REGISTRY))
        body = designate(candidates, pool, games=args.games, benchmarks=bench)
        save_champion(CHAMPION_PATH, body)
        for row in body["ranking"]:
            mark = " (benchmark)" if row["benchmark"] else ""
            print(f"  {row['name']:16s} share={row['share']:.4f}{mark}")
        print(f"\ngate_opponent:  {body['gate_opponent']}")
        print(f"submit_default: {body['submit_default']}")
        return 0

    if not args.challenger:
        ap.error("provide a challenger name, or use --designate")
    res = promotion_test(args.challenger, args.champion, games=args.games,
                         bar=args.bar, alpha=args.alpha)
    r = res.record
    print(f"{res.challenger} vs {res.champion} ({r.games} seeded games)")
    print(f"  wins {r.wins}  losses {r.losses}  ties {r.ties}")
    print(f"  win-rate {r.win_rate:.1%} (decisive {r.decisive})  tie-rate {r.tie_rate:.1%}")
    print(f"  binomial p={r.p_value:.4g}  bar={res.bar:.0%}  alpha={res.alpha}")
    print(f"  => {'PROMOTE' if res.passed else 'REJECT'}")
    return 0 if res.passed else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
