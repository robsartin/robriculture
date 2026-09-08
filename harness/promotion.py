"""Promotion harness — ADR-0007's strategy-experiment gate.

A strategy experiment is promoted only if its challenger is *actually better*
than the current champion. "Better" is not a green test; it's a statistical
claim: over a fixed set of seeded games, the challenger must both clear a
win-rate bar and beat a fair-coin null by a binomial test. This module provides
the reproducible measurement (`run_match`), the decision (`PromotionResult`),
and the tooling to designate a champion.

Designation is by **gate succession** (#241, ADR-0007 amendment 2026-09-07):
the champion is the most recent strategy to PROMOTE through the gate against
the incumbent, recorded by `succeed`. Pool share (`designate`, #76) is still
computed as a ranking, but it no longer writes `harness/champion.json` — once
every contender swept the anchors it ranked a gate-REJECTED contender above
one that beat the incumbent 16/16, and `save_champion` refuses that reversal.

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

from harness.evolve import opponent_record
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

    The per-opponent seed offset comes from that opponent's position in the
    *pool*, stable across every candidate — not from its position in any one
    candidate's filtered opponent list. This calls `opponent_record` directly
    rather than routing through `match_share`: `match_share` derives its seed
    offset from list index, so a pool member's self-exclusion shifts every
    opponent after it down one slot, and two candidates end up measured on
    different seeded games against the "same" opponent (#76). Keying off pool
    position instead means every candidate meets a given opponent at
    identical seeds, so shares are actually comparable across candidates.

    This does NOT equalize the *field*: a candidate that is itself in the
    pool plays N-1 opponents (itself excluded) while one outside the pool
    plays all N, so pool members never meet a peer of their own strength.
    That is pool-composition, not seeding, and is left to #78.
    """
    if not pool:
        raise ValueError("cannot rank against an empty pool")
    benchmarks = benchmarks or set()
    rows = []
    for name, agent in candidates.items():
        shares = []
        for oi, (opp_name, opp) in enumerate(pool.items()):
            if opp_name == name:
                continue
            shares.append(
                opponent_record(agent, opp, games, seed_base + oi * 100000,
                                rewards_fn)["share"]
            )
        if not shares:
            raise ValueError(
                f"candidate {name!r} has no opponents: it is the only entry in the pool, "
                f"and a candidate never plays itself"
            )
        rows.append({"name": name, "share": sum(shares) / len(shares),
                     "benchmark": name in benchmarks})
    rows.sort(key=lambda r: r["share"], reverse=True)
    return rows


POOL_SHARE = "pool_share"
GATE_SUCCESSION = "gate_succession"
#: How `harness/champion.json` is designated (#241; ADR-0007 amendment 2026-09-07).
CRITERION = GATE_SUCCESSION


def designate(candidates, pool, games=2, seed_base=0,
              rewards_fn=_play_rewards, benchmarks=None):
    """Rank by pool share and split the result into the champion's two roles.

    `gate_opponent` here is the ranking's outright leader, benchmarks included,
    so the ranking reports the most demanding bar it saw. The *recorded* gate
    opponent is by succession (#241) and is always ours: a pool-share body is
    informational and `save_champion` will not write it over a succession.

    `submit_default` is the leading non-benchmark. `scripts/submit.py` packages
    it with no arguments, so a vendored external agent must never land here:
    submitting a competitor's code is pointless and an ADR-0005 licensing and
    attribution problem. One field cannot answer both questions, which is why
    there are two.

    `benchmarks` omitted (None) resolves to the real registry via
    `harness.tournament.benchmark_names()`, not an empty set. Defaulting to
    "no benchmarks exist" would let a caller write a committed `champion.json`
    that stamps every row `"benchmark": false` and can hand `submit_default` a
    vendored competitor — silently, the same failure mode `_read_role` exists
    to forbid. Pass an explicit `benchmarks=set()` to opt out deliberately.
    """
    if benchmarks is None:
        from harness.tournament import benchmark_names
        benchmarks = benchmark_names()
    ranking = pool_share_rank(candidates, pool, games=games, seed_base=seed_base,
                              rewards_fn=rewards_fn, benchmarks=benchmarks)
    return {
        "criterion": POOL_SHARE,
        "gate_opponent": ranking[0]["name"],
        "submit_default": top_contender([r["name"] for r in ranking], benchmarks),
        "games": games,
        "pool": list(pool),
        "ranking": ranking,
    }


def designation_inputs(registry_names, anchor_names, include_external=False, build=build_agents,
                       benchmarks=None, external_loader=None):
    """What `--designate` ranks and against whom (#152).

    Candidates are the registry; the pool is the anchors. With
    `include_external` the pinned gate externals (`external_pool.EXTERNAL_ANCHORS`,
    loaded by `external_anchor_agents`, which refuses an unverified pool) join
    both -- and the benchmark set, so one can lead the ranking as
    `gate_opponent` but never land as `submit_default` (ADR-0005).
    """
    if benchmarks is None:
        from harness.tournament import benchmark_names
        benchmarks = benchmark_names()
    candidates = build(list(registry_names))
    pool = build(list(anchor_names))
    benchmarks = set(benchmarks)
    if include_external:
        if external_loader is None:
            from harness.external_pool import external_anchor_agents as external_loader
        externals = external_loader()
        candidates.update(externals)
        pool.update(externals)
        benchmarks |= set(externals)
    return candidates, pool, benchmarks


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


def succeed(challenger, incumbent, *, issue, pr, record, date, bar=None, benchmarks=None):
    """The designation body for a challenger that PROMOTED against the incumbent.

    Both roles go to the challenger: it beat the gate opponent, so it is the
    new bar, and it is ours, so it is what `scripts/submit.py` packages. A
    benchmark (vendored competitor) is refused outright — it can never be a
    submit default (ADR-0005), and it cannot PROMOTE through our gate anyway.

    `record` is the champion row of the gate run: `wins`, `ties`, `games` and
    the `seeds` it was played on. The body is the gate's verdict restated, so
    a record below the champion bar (`harness.rival_bench.CHAMPION_BAR`, ties
    counted as not-wins) raises rather than designating. The one-sided binomial
    p on the decisive games is recorded alongside so the artifact carries its
    own evidence.
    """
    if bar is None:
        from harness.rival_bench import CHAMPION_BAR
        bar = CHAMPION_BAR
    if benchmarks is None:
        from harness.tournament import benchmark_names
        benchmarks = benchmark_names()
    if challenger in benchmarks:
        raise ValueError(f"{challenger!r} is a benchmark: it can be a gate opponent, never a champion")
    wins, games = record["wins"], record["games"]
    rate = wins / games
    if rate < bar:
        raise ValueError(
            f"{challenger!r} vs {incumbent!r}: {wins}/{games} = {rate:.1%} is below the "
            f"gate bar {bar:.0%} (ties are not wins) — succession restates a PROMOTE, "
            f"it cannot manufacture one"
        )
    decisive = games - record.get("ties", 0)
    return {
        "criterion": GATE_SUCCESSION,
        "gate_opponent": challenger,
        "submit_default": challenger,
        "succession": {
            "predecessor": incumbent,
            "issue": issue,
            "pr": pr,
            "date": date,
            "record": dict(record, p=binomial_p_value(wins, decisive)),
        },
    }


def designation_criterion(path=CHAMPION_PATH):
    """The `criterion` recorded in the artifact, or None if there is no artifact."""
    if not os.path.exists(path):
        return None
    with open(path) as fh:
        return json.load(fh).get("criterion")


def save_champion(path, body):
    """Write a designation body as JSON.

    A gate-succession artifact is never overwritten by a pool-share body: the
    pool-share writers (`--designate`, `harness.rounds`) still run as rankings,
    and letting one of them silently revert the criterion is exactly the
    "fix undone invisibly" failure #76 was itself a fix for.
    """
    existing = designation_criterion(path)
    if existing == GATE_SUCCESSION and body.get("criterion") != GATE_SUCCESSION:
        raise ValueError(
            f"{path!r} is designated by {GATE_SUCCESSION!r} (#241); a "
            f"{body.get('criterion')!r} body would silently revert it. Read the ranking, "
            f"and record a succession with: python -m harness.promotion --succeed <challenger> ..."
        )
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
            f"re-designate with: python -m harness.promotion --designate --games 2"
        )
    return data[field]


def gate_opponent(path=CHAMPION_PATH):
    """The opponent an ADR-0007 promotion test measures against: the last challenger
    to PROMOTE (#241), so ours, never an external -- the field enters through the
    gate's paired external limb (#152)."""
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
                    help="rank all strategies by pool share against the fixed anchors (informational since #241; written only if the artifact is not a gate succession)")
    ap.add_argument("--include-external", action="store_true",
                    help="--designate: rank with the pinned gate externals (external_pool.EXTERNAL_ANCHORS) in the pool and the candidates (#152)")
    ap.add_argument("--succeed", metavar="CHALLENGER",
                    help="record CHALLENGER as champion after it PROMOTED against the recorded gate_opponent (#241)")
    ap.add_argument("--issue", type=int, help="--succeed: the experiment issue")
    ap.add_argument("--pr", type=int, help="--succeed: the PR that carried it")
    ap.add_argument("--wins", type=int, help="--succeed: champion-row wins")
    ap.add_argument("--ties", type=int, default=0, help="--succeed: champion-row ties (default 0)")
    ap.add_argument("--seeds", help="--succeed: the seed range played, e.g. 816-831")
    ap.add_argument("--date", help="--succeed: the PROMOTE date, YYYY-MM-DD")
    ap.add_argument("names", nargs="*", help="agents to rank (for --designate; default: all + built-ins)")
    args = ap.parse_args(argv)

    if args.designate:
        from harness.evolve import DEFAULT_ANCHORS
        from strategies import REGISTRY

        candidates, pool, bench = designation_inputs(
            list(REGISTRY), list(DEFAULT_ANCHORS), include_external=args.include_external)
        body = designate(candidates, pool, games=args.games, benchmarks=bench)
        for row in body["ranking"]:
            mark = " (benchmark)" if row["benchmark"] else ""
            print(f"  {row['name']:16s} share={row['share']:.4f}{mark}")
        if designation_criterion(CHAMPION_PATH) == GATE_SUCCESSION:
            print(f"\nranking only: {CHAMPION_PATH} is designated by gate succession (#241); "
                  f"pool share leads with {body['gate_opponent']}, not written")
            return 0
        save_champion(CHAMPION_PATH, body)
        print(f"\ngate_opponent:  {body['gate_opponent']}")
        print(f"submit_default: {body['submit_default']}")
        return 0

    if args.succeed:
        missing = [k for k in ("issue", "pr", "wins", "seeds", "date") if getattr(args, k) is None]
        if missing:
            ap.error(f"--succeed needs --{' --'.join(missing)}")
        incumbent = gate_opponent()
        record = {"wins": args.wins, "ties": args.ties, "games": args.games, "seeds": args.seeds}
        body = succeed(args.succeed, incumbent, issue=args.issue, pr=args.pr,
                       record=record, date=args.date)
        save_champion(CHAMPION_PATH, body)
        r = body["succession"]["record"]
        print(f"{args.succeed} succeeds {incumbent}: {r['wins']}/{r['games']} on seeds {r['seeds']}, "
              f"p={r['p']:.3g} (#{args.issue}, PR #{args.pr}, {args.date})")
        print(f"gate_opponent:  {body['gate_opponent']}")
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
