"""The offline triage tool (#172 Stage 2): rank whole strategies by seeded
self-play final money. Everything here runs against a fake `play` so the
arithmetic is pinned without a simulator; the one real game is at the end."""

from __future__ import annotations

from harness import triage


def _fake_play(table):
    """A `play` whose rewards are looked up by (agent name, seed)."""
    def play(agent_a, agent_b, seed):
        return table[(agent_a, seed)]
    return play


def _names(name):
    return name          # the fake agent IS its name


def test_the_declared_constants():
    assert triage.SEEDS == (0, 1, 2, 3)
    assert triage.BAR == 0.40
    assert triage.FLOOR == "lean"
    assert triage.MIN_MEMBERS == 5


def test_self_play_score_averages_both_seats_and_all_seeds():
    table = {("a", 0): (100.0, 300.0), ("a", 1): (50.0, 50.0)}
    got = triage.self_play_score("a", seeds=(0, 1), play=_fake_play(table), agents=_names)
    assert got["name"] == "a"
    assert got["per_seed"] == [200.0, 50.0]
    assert got["score"] == 125.0
    assert got["seconds"] >= 0.0


def test_self_play_hands_the_same_strategy_to_both_seats_with_the_seed():
    seen = []

    def play(agent_a, agent_b, seed):
        seen.append((agent_a, agent_b, seed))
        return (1.0, 1.0)

    triage.self_play_score("z", seeds=(7,), play=play, agents=lambda n: f"agent:{n}")
    assert seen == [("agent:z", "agent:z", 7)]


def test_rank_sorts_best_first_and_keeps_input_order_on_ties():
    table = {("low", 0): (1.0, 1.0), ("high", 0): (9.0, 9.0),
             ("tie1", 0): (5.0, 5.0), ("tie2", 0): (5.0, 5.0)}
    rows = triage.rank(["low", "tie1", "high", "tie2"], seeds=(0,),
                       play=_fake_play(table), agents=_names)
    assert [r["name"] for r in rows] == ["high", "tie1", "tie2", "low"]


def test_format_ranking_has_a_header_and_one_line_per_strategy_with_seeds():
    rows = [{"name": "high", "score": 9.0, "per_seed": [9.0, 9.0], "seconds": 0.5},
            {"name": "low", "score": 1.0, "per_seed": [1.5, 0.5], "seconds": 0.4}]
    text = triage.format_ranking(rows)
    lines = [ln for ln in text.splitlines() if ln.strip()]
    assert len(lines) == 3
    assert lines[1].startswith("1") and "high" in lines[1] and "9.0" in lines[1]
    assert "1.5" in lines[2] and "0.5" in lines[2]
