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
    assert sc.verdict({"discordant_0w_1l": 12, "discordant_0l_1w": 3, "p": sc.sign_test(12, 3)}) == "established"
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
