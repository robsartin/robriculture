"""Tests for round history + windowed champion selection (#12).

The champion is chosen from win-rate over the current + recent rounds, not a
single snapshot, so a lucky round doesn't crown a weak agent and recent (better)
agents are weighted appropriately. Aggregation is tested with synthetic rounds —
no real games.
"""

from __future__ import annotations

import json

import pytest

from harness import rounds
from harness.rounds import (
    append_round,
    load_rounds,
    run_and_record,
    run_round,
)


def _round(results):
    """results: {name: (wins, played)} -> a round dict."""
    return {"games": 1, "results": {n: {"wins": w, "played": p} for n, (w, p) in results.items()}}


# --- persistence ---

def test_append_assigns_incrementing_round_ids(tmp_path):
    path = tmp_path / "rounds.json"
    r1 = append_round(path, _round({"A": (1, 1)}))
    r2 = append_round(path, _round({"A": (1, 1)}))
    assert r1["round"] == 1 and r2["round"] == 2
    assert len(load_rounds(path)) == 2


def test_load_rounds_missing_file_is_empty(tmp_path):
    assert load_rounds(tmp_path / "nope.json") == []


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


def test_run_and_record_appends_history_and_writes_champion(tmp_path, monkeypatch):
    """run_and_record appends the round and writes the designated gate_opponent.

    Designation itself is `promotion.designate`'s job (covered in
    tests/test_promotion.py); here we only verify run_and_record wires the round
    history and the artifact write together, so the designation is stubbed.
    """
    import json

    from harness import rounds

    monkeypatch.setattr(rounds.promotion, "designate", lambda candidates, pool, **kw: {
        "criterion": "pool_share", "gate_opponent": "A",
        "submit_default": "A", "games": 2, "pool": [], "ranking": []})

    rounds_path = tmp_path / "rounds.json"
    champ_path = tmp_path / "champion.json"
    strength = {"A": 2, "B": 1}
    champ, body = run_and_record(
        ["A", "B"],
        games=2,
        rounds_path=str(rounds_path),
        champion_path=str(champ_path),
        play_fn=lambda a, b, seed: (strength[a] > strength[b]) - (strength[a] < strength[b]),
        build=lambda names: {n: n for n in names},
    )
    assert champ == "A"
    assert rounds_path.exists() and champ_path.exists()
    assert json.load(open(champ_path))["gate_opponent"] == "A"
    assert body["gate_opponent"] == "A"


def test_run_and_record_forwards_rewards_fn_and_pool_to_designate(tmp_path, monkeypatch):
    """The optional rewards_fn/pool kwargs reach promotion.designate unchanged."""
    from harness import rounds

    seen = {}

    def fake_designate(candidates, pool, **kw):
        seen["pool"] = pool
        seen["kw"] = kw
        return {"criterion": "pool_share", "gate_opponent": "A",
                "submit_default": "A", "games": 2, "pool": [], "ranking": []}

    monkeypatch.setattr(rounds.promotion, "designate", fake_designate)
    stub_rewards = lambda a, b, seed=None: (1.0, 0.0)

    run_and_record(
        ["A", "B"],
        games=2,
        rounds_path=str(tmp_path / "rounds.json"),
        champion_path=str(tmp_path / "champion.json"),
        play_fn=lambda a, b, seed: 0,
        build=lambda names: {n: n for n in names},
        rewards_fn=stub_rewards,
        pool=["A"],
    )
    assert seen["pool"] == {"A": "A"}
    assert seen["kw"]["rewards_fn"] is stub_rewards


def test_run_and_record_designates_by_pool_share_not_round_wins(tmp_path, monkeypatch):
    """The regression guard for #76's revert trap.

    rounds.py used to re-designate from windowed round win-rate. If it ever did
    again, a routine `python -m harness.rounds` would silently overwrite the
    share-based champion and re-crown market_farmer — a fix undone invisibly.
    """
    calls = {}

    def fake_designate(candidates, pool, **kw):
        calls["used"] = True
        return {"criterion": "pool_share", "gate_opponent": "meta_bot",
                "submit_default": "ranch_hands", "games": kw.get("games", 2),
                "pool": list(pool), "ranking": []}

    monkeypatch.setattr(rounds.promotion, "designate", fake_designate)

    champ, body = rounds.run_and_record(
        ["ranch_hands", "meta_bot"], games=2,
        rounds_path=str(tmp_path / "rounds.json"),
        champion_path=str(tmp_path / "champion.json"),
        play_fn=lambda a, b, seed=None: 1 if a == "ranch_hands" else -1,
        build=lambda names: {n: n for n in names},
        benchmarks={"meta_bot"},
    )
    assert calls.get("used") is True
    assert champ == "meta_bot"
    assert body["submit_default"] == "ranch_hands"


def test_run_and_record_still_appends_round_history(tmp_path, monkeypatch):
    """Designation changed; the round history record did not."""
    monkeypatch.setattr(rounds.promotion, "designate", lambda candidates, pool, **kw: {
        "criterion": "pool_share", "gate_opponent": "a", "submit_default": "a",
        "games": 2, "pool": [], "ranking": []})

    rounds_path = tmp_path / "rounds.json"
    rounds.run_and_record(
        ["a", "b"], games=2, rounds_path=str(rounds_path),
        champion_path=str(tmp_path / "champion.json"),
        play_fn=lambda x, y, seed=None: 1, build=lambda names: {n: n for n in names},
    )
    history = json.loads(rounds_path.read_text())
    assert len(history) == 1 and "results" in history[0]
