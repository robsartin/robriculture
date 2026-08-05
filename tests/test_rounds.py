"""Tests for round history + windowed champion selection (#12).

The champion is chosen from win-rate over the current + recent rounds, not a
single snapshot, so a lucky round doesn't crown a weak agent and recent (better)
agents are weighted appropriately. Aggregation is tested with synthetic rounds —
no real games.
"""

from __future__ import annotations

import pytest

from harness.rounds import (
    append_round,
    designate_from_history,
    load_rounds,
    run_and_record,
    run_round,
    windowed_ranking,
)


def _round(results):
    """results: {name: (wins, played)} -> a round dict."""
    return {"games": 1, "results": {n: {"wins": w, "played": p} for n, (w, p) in results.items()}}


# --- windowed_ranking ---

def test_windowed_ranking_uses_only_the_last_n_rounds():
    rounds = [
        _round({"A": (10, 10), "B": (0, 10)}),   # oldest — A dominates
        _round({"A": (0, 10), "B": (10, 10)}),
        _round({"A": (0, 10), "B": (10, 10)}),
        _round({"A": (0, 10), "B": (10, 10)}),    # newest
    ]
    ranking = windowed_ranking(rounds, window=3)
    # Last 3 rounds: A won 0/30, B won 30/30 -> B first.
    names = [n for n, *_ in ranking]
    assert names[0] == "B"
    b = next(r for r in ranking if r[0] == "B")
    assert b[1] == pytest.approx(1.0)


def test_windowed_ranking_aggregates_wins_over_the_window():
    rounds = [
        _round({"A": (6, 10), "B": (4, 10)}),
        _round({"A": (5, 10), "B": (5, 10)}),
    ]
    ranking = dict((n, wr) for n, wr, *_ in windowed_ranking(rounds, window=2))
    assert ranking["A"] == pytest.approx(11 / 20)
    assert ranking["B"] == pytest.approx(9 / 20)


def test_recency_decay_favors_the_newer_round():
    rounds = [
        _round({"A": (10, 10), "B": (0, 10)}),   # old: A great
        _round({"A": (0, 10), "B": (10, 10)}),   # new: B great
    ]
    # Equal weight -> tie at 0.5 each. With decay, the newer round dominates -> B.
    ranking = windowed_ranking(rounds, window=2, decay=0.5)
    assert ranking[0][0] == "B"


def test_window_larger_than_history_uses_all_rounds():
    rounds = [_round({"A": (7, 10), "B": (3, 10)})]
    ranking = windowed_ranking(rounds, window=5)
    assert ranking[0][0] == "A"


# --- persistence ---

def test_append_assigns_incrementing_round_ids(tmp_path):
    path = tmp_path / "rounds.json"
    r1 = append_round(path, _round({"A": (1, 1)}))
    r2 = append_round(path, _round({"A": (1, 1)}))
    assert r1["round"] == 1 and r2["round"] == 2
    assert len(load_rounds(path)) == 2


def test_load_rounds_missing_file_is_empty(tmp_path):
    assert load_rounds(tmp_path / "nope.json") == []


def test_designate_from_history_picks_the_window_leader(tmp_path):
    path = tmp_path / "rounds.json"
    append_round(path, _round({"A": (9, 10), "B": (1, 10)}))
    assert designate_from_history(path, window=3) == "A"


# --- run_round (fake play, no real games) ---

def test_run_round_records_wins_and_played():
    strength = {"A": 2, "B": 1}
    rnd = run_round(
        ["A", "B"],
        games=4,
        play_fn=lambda a, b, seed: (strength[a] > strength[b]) - (strength[a] < strength[b]),
        build=lambda names: {n: n for n in names},
    )
    assert rnd["results"]["A"]["wins"] == 4
    assert rnd["results"]["A"]["played"] == 4
    assert rnd["results"]["B"]["wins"] == 0


def test_run_and_record_appends_history_and_writes_champion(tmp_path):
    import json

    rounds_path = tmp_path / "rounds.json"
    champ_path = tmp_path / "champion.json"
    strength = {"A": 2, "B": 1}
    champ, ranking = run_and_record(
        ["A", "B"],
        games=2,
        rounds_path=str(rounds_path),
        champion_path=str(champ_path),
        play_fn=lambda a, b, seed: (strength[a] > strength[b]) - (strength[a] < strength[b]),
        build=lambda names: {n: n for n in names},
    )
    assert champ == "A"
    assert rounds_path.exists() and champ_path.exists()
    assert json.load(open(champ_path))["champion"] == "A"
    assert ranking[0][0] == "A"
