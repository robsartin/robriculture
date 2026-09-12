"""Does lean_feed's ladder seat split exist locally? (#272)

On the ladder lean_feed is 14/24 in seat 0 and 7/23 in seat 1 (Fisher
p = 0.051), confounded by who landed in which seat. Every bench alternates
seats and reports the sum, so a real effect would be invisible. Here each
seed is played twice per opponent, once in each seat, and the discordant
seeds -- won in one seat, lost in the other -- carry the answer through an
exact two-sided sign test.

    .venv/bin/python -m harness.seat_check
"""

from __future__ import annotations

import argparse
import math
import os

from harness.external_pool import EXTERNAL_ANCHORS

SUBJECT = "lean_feed"
OPPONENTS = tuple(EXTERNAL_ANCHORS) + ("field_rival", "third_herder")
SEEDS = tuple(range(1024, 1040))
ALPHA = 0.05
ABSENT_GAP = 2
#: The ladder split this check exists to test (#266 §6), printed beside the local one.
LADDER = {"seat0": (14, 24), "seat1": (7, 23), "p_fisher_one_sided": 0.051}


def outcome(ours, theirs) -> str:
    return "W" if ours > theirs else "L" if ours < theirs else "T"


def seat_table(results, opponents=OPPONENTS) -> list:
    """Per opponent: wins in each seat and the discordant seeds by direction."""
    table = []
    for opp in opponents:
        mine = [r for r in results if r["opponent"] == opp]
        by_seed: dict = {}
        for r in mine:
            by_seed.setdefault(r["seed"], {})[r["seat"]] = outcome(r["ours"], r["theirs"])
        seat0 = sum(o.get(0) == "W" for o in by_seed.values())
        seat1 = sum(o.get(1) == "W" for o in by_seed.values())
        f01 = sum(o.get(0) == "W" and o.get(1) == "L" for o in by_seed.values())
        f10 = sum(o.get(0) == "L" and o.get(1) == "W" for o in by_seed.values())
        table.append({"opponent": opp, "seat0_wins": seat0, "seat1_wins": seat1,
                      "games_per_seat": len(by_seed), "flips_0w_1l": f01, "flips_0l_1w": f10})
    return table


def sign_test(a: int, b: int) -> float:
    """Exact two-sided binomial test that `a` and `b` discordant counts come
    from p = 0.5: the probability of a split at least this lopsided."""
    n = a + b
    if n == 0:
        return 1.0
    k = min(a, b)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def pooled(table) -> dict:
    games = sum(r["games_per_seat"] for r in table)
    a = sum(r["flips_0w_1l"] for r in table)
    b = sum(r["flips_0l_1w"] for r in table)
    return {"seat0_rate": sum(r["seat0_wins"] for r in table) / games if games else 0.0,
            "seat1_rate": sum(r["seat1_wins"] for r in table) / games if games else 0.0,
            "discordant_0w_1l": a, "discordant_0l_1w": b, "p": sign_test(a, b)}


def verdict(p) -> str:
    """The declared reading: established (p < ALPHA), absent (discordant
    counts within ABSENT_GAP), else unresolved."""
    if p["p"] < ALPHA:
        return "established"
    if abs(p["discordant_0w_1l"] - p["discordant_0l_1w"]) <= ABSENT_GAP:
        return "absent"
    return "unresolved"


def format_table(table) -> str:
    lines = ["| opponent | seat 0 wins | seat 1 wins | flips 0W/1L | flips 0L/1W |", "|---|---|---|---|---|"]
    lines += [f"| {r['opponent']} | {r['seat0_wins']}/{r['games_per_seat']} | {r['seat1_wins']}/{r['games_per_seat']} "
              f"| {r['flips_0w_1l']} | {r['flips_0l_1w']} |" for r in table]
    return "\n".join(lines)


def format_pooled(p) -> str:
    return (f"pooled: seat 0 {p['seat0_rate']:.1%}, seat 1 {p['seat1_rate']:.1%}; discordant seeds "
            f"0W/1L {p['discordant_0w_1l']} vs 0L/1W {p['discordant_0l_1w']}; sign test p={p['p']:.4f} "
            f"-> {verdict(p)}  (ladder: seat 0 {LADDER['seat0'][0]}/{LADDER['seat0'][1]}, "
            f"seat 1 {LADDER['seat1'][0]}/{LADDER['seat1'][1]}, one-sided Fisher p={LADDER['p_fisher_one_sided']})")


def run(opponents=OPPONENTS, seeds=SEEDS, play=None, agents=None) -> list:
    """Every seed twice per opponent -- the subject in seat 0, then in seat 1 --
    with fresh agents for every game."""
    if play is None or agents is None:  # pragma: no cover
        from harness.rival_bench import _gate_agents
        from harness.tournament import play_rewards
        play = play or play_rewards
        agents = agents or _gate_agents()
    results = []
    for opp in opponents:
        for seed in seeds:
            ours, theirs = play(agents(SUBJECT), agents(opp), seed)
            results.append({"opponent": opp, "seed": seed, "seat": 0, "ours": ours, "theirs": theirs})
            theirs, ours = play(agents(opp), agents(SUBJECT), seed)
            results.append({"opponent": opp, "seed": seed, "seat": 1, "ours": ours, "theirs": theirs})
    return results


def main(argv=None):  # pragma: no cover
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    ap = argparse.ArgumentParser(description="seat check for lean_feed (#272)")
    ap.parse_args(argv)
    results = run()
    table = seat_table(results)
    print(format_table(table))
    print(format_pooled(pooled(table)))
    print("games (opponent, seed, seat, ours, theirs):")
    for r in results:
        print(f"  {r['opponent']} {r['seed']} {r['seat']} {r['ours']} {r['theirs']}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
