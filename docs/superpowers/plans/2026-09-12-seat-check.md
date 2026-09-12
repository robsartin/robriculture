# seat_check (#272) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `harness/seat_check.py`: play `lean_feed` against seven opponents on 16 fresh seeds in BOTH seats, and report the per-opponent seat split, the pooled split, a two-sided sign test on the discordant seeds, and the declared verdict — exactly as the declaration on issue #272.

**Architecture:** Pure functions over a list of game results (`{"opponent", "seed", "seat", "ours", "theirs"}`) plus one `# pragma: no cover` runner using `harness.rival_bench._gate_agents()` (registry + external names, fresh per game) and `harness.tournament.play_rewards`.

**Tech Stack:** Python 3.12 stdlib, `.venv/bin/python`, pytest.

## Global Constraints
- Pure TDD: the failing test first, RUN it and observe the failure, then the code; the report quotes the red.
- `.venv/bin/python` only; every command blocking; do NOT run the full suite (the controller does) — only the targeted tests.
- Never edit an existing file. Stage by explicit path; never `git add -A`; never stage `.venv`, `external_agents`, `replays/`.
- Declared values verbatim: `SUBJECT = "lean_feed"`, `OPPONENTS = tuple(EXTERNAL_ANCHORS) + ("field_rival", "third_herder")` (seven names, externals first in pool order), `SEEDS = tuple(range(1024, 1040))`, `ALPHA = 0.05`, `ABSENT_GAP = 2`; the sign test is exact two-sided binomial with p = 0.5 on the discordant pairs; a tie in either seat makes the seed non-discordant.

---

### Task 1: The tool

**Files:**
- Create: `harness/seat_check.py`
- Test: `tests/test_seat_check.py`

**Interfaces:**
- Consumes: `harness.external_pool.EXTERNAL_ANCHORS`; `harness.rival_bench._gate_agents()` → `agents(name)` callable; `harness.tournament.play_rewards(agent_a, agent_b, seed) -> (reward_a, reward_b)`.
- Produces: `outcome(ours, theirs) -> "W"|"L"|"T"`, `seat_table(results) -> list[dict]` (one per opponent, in `OPPONENTS` order: `opponent, seat0_wins, seat1_wins, games_per_seat, flips_0w_1l, flips_0l_1w`), `pooled(table) -> dict` (`seat0_rate, seat1_rate, discordant_0w_1l, discordant_0l_1w, p`), `sign_test(a, b) -> float`, `verdict(pooled) -> str` in `{"established", "absent", "unresolved"}`, `format_table`, `format_pooled`, `run(opponents, seeds, play=None, agents=None) -> list`, `main`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_seat_check.py
"""The seat check's declared constants and pure parts (#272)."""

from __future__ import annotations

from harness import seat_check as sc
from harness.external_pool import EXTERNAL_ANCHORS


def test_the_declared_constants():
    assert sc.SUBJECT == "lean_feed"
    assert sc.OPPONENTS == tuple(EXTERNAL_ANCHORS) + ("field_rival", "third_herder") and len(sc.OPPONENTS) == 7
    assert sc.SEEDS == tuple(range(1024, 1040)) and sc.ALPHA == 0.05 and sc.ABSENT_GAP == 2


def test_the_seeds_are_fresh_against_every_range_already_spent():
    spent = set(range(100, 116)) | set(range(200, 216)) | set(range(300, 332)) \
        | set(range(400, 416)) | set(range(500, 516)) | set(range(600, 616)) \
        | set(range(700, 704)) | set(range(800, 960)) | set(range(960, 1024))
    assert not spent & set(sc.SEEDS)


def _g(opp, seed, seat, ours, theirs):
    return {"opponent": opp, "seed": seed, "seat": seat, "ours": ours, "theirs": theirs}


def test_outcome():
    assert sc.outcome(3, 2) == "W" and sc.outcome(2, 3) == "L" and sc.outcome(2, 2) == "T"


def test_seat_table_counts_wins_per_seat_and_flips_by_direction():
    results = [
        _g("a", 1, 0, 10, 5), _g("a", 1, 1, 4, 9),     # seed 1: win seat 0, lose seat 1 -> flip 0w_1l
        _g("a", 2, 0, 1, 9), _g("a", 2, 1, 9, 1),      # seed 2: lose seat 0, win seat 1 -> flip 0l_1w
        _g("a", 3, 0, 9, 1), _g("a", 3, 1, 9, 1),      # both wins: no flip
        _g("a", 4, 0, 5, 5), _g("a", 4, 1, 1, 9),      # tie in seat 0: not discordant
        _g("b", 1, 0, 9, 1), _g("b", 1, 1, 1, 9),
    ]
    table = sc.seat_table(results, opponents=("a", "b"))
    assert table[0] == {"opponent": "a", "seat0_wins": 2, "seat1_wins": 2, "games_per_seat": 4,
                        "flips_0w_1l": 1, "flips_0l_1w": 1}
    assert table[1] == {"opponent": "b", "seat0_wins": 1, "seat1_wins": 0, "games_per_seat": 1,
                        "flips_0w_1l": 1, "flips_0l_1w": 0}


def test_sign_test_is_exact_two_sided_binomial():
    assert sc.sign_test(0, 0) == 1.0
    assert abs(sc.sign_test(5, 0) - 2 * 0.5 ** 5) < 1e-12          # 0.0625
    assert abs(sc.sign_test(8, 0) - 2 * 0.5 ** 8) < 1e-12          # 0.0078125
    assert abs(sc.sign_test(3, 3) - 1.0) < 1e-12
    assert abs(sc.sign_test(6, 2) - sc.sign_test(2, 6)) < 1e-12
    # 7 vs 1: P(X<=1)+P(X>=7) for n=8 = 2*(1+8)/256
    assert abs(sc.sign_test(7, 1) - 2 * 9 / 256) < 1e-12


def test_pooled_rates_and_verdict():
    table = [{"opponent": "a", "seat0_wins": 12, "seat1_wins": 4, "games_per_seat": 16, "flips_0w_1l": 9, "flips_0l_1w": 1},
             {"opponent": "b", "seat0_wins": 8, "seat1_wins": 8, "games_per_seat": 16, "flips_0w_1l": 2, "flips_0l_1w": 2}]
    p = sc.pooled(table)
    assert p["seat0_rate"] == 20 / 32 and p["seat1_rate"] == 12 / 32
    assert (p["discordant_0w_1l"], p["discordant_0l_1w"]) == (11, 3)
    assert abs(p["p"] - sc.sign_test(11, 3)) < 1e-12
    assert sc.verdict({"discordant_0w_1l": 11, "discordant_0l_1w": 3, "p": sc.sign_test(11, 3)}) == "established"
    assert sc.verdict({"discordant_0w_1l": 3, "discordant_0l_1w": 2, "p": 1.0}) == "absent"
    assert sc.verdict({"discordant_0w_1l": 6, "discordant_0l_1w": 2, "p": sc.sign_test(6, 2)}) == "unresolved"
    assert sc.verdict({"discordant_0w_1l": 0, "discordant_0l_1w": 0, "p": 1.0}) == "absent"


def test_run_plays_every_seed_in_both_seats_with_fresh_agents():
    calls = []
    built = []

    def agents(name):
        built.append(name)
        return name

    def play(a, b, seed):
        calls.append((a, b, seed))
        return (10, 5) if a == "lean_feed" else (5, 10)   # the subject always wins

    results = sc.run(opponents=("x", "y"), seeds=(1, 2), play=play, agents=agents)
    assert calls == [("lean_feed", "x", 1), ("x", "lean_feed", 1), ("lean_feed", "x", 2), ("x", "lean_feed", 2),
                     ("lean_feed", "y", 1), ("y", "lean_feed", 1), ("lean_feed", "y", 2), ("y", "lean_feed", 2)]
    assert results[1] == {"opponent": "x", "seed": 1, "seat": 1, "ours": 10, "theirs": 5}
    assert built.count("lean_feed") == 8 and built.count("x") == 4


def test_formatters():
    table = [{"opponent": "a", "seat0_wins": 12, "seat1_wins": 4, "games_per_seat": 16, "flips_0w_1l": 9, "flips_0l_1w": 1}]
    out = sc.format_table(table)
    assert "| a | 12/16 | 4/16 | 9 | 1 |" in out
    pooled = sc.pooled(table)
    assert "established" in sc.format_pooled(pooled) and "p=" in sc.format_pooled(pooled)
```

- [ ] **Step 2: Run the tests and observe them fail**

Run: `.venv/bin/python -m pytest tests/test_seat_check.py -q`
Expected: collection error (`harness.seat_check` does not exist). Quote it.

- [ ] **Step 3: Write `harness/seat_check.py`**

```python
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
```

- [ ] **Step 4: Run the tests and observe them pass**

Run: `.venv/bin/python -m pytest tests/test_seat_check.py -q`
Expected: all PASS. If `test_run_plays_every_seed_in_both_seats_with_fresh_agents` fails on the `built` counts, check that `agents` is called once per side per game (four per seed per opponent for the subject: two games × one call each... — the test expects 8 subject builds over 2 opponents × 2 seeds × 2 games; and 4 for "x": 2 seeds × 2 games).

- [ ] **Step 5: Commit**

```bash
git add harness/seat_check.py tests/test_seat_check.py
git commit -m "feat(#272): seat_check — lean_feed in both seats on fresh seeds, sign test on the discordant seeds

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```
