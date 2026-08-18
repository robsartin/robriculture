"""A benchmark opponent shapes the ranking but is never chosen as champion."""

from __future__ import annotations

import json

import pytest

from harness import promotion


def test_top_contender_skips_a_leading_benchmark():
    assert promotion.top_contender(["meta_bot", "ranch_hands"], {"meta_bot"}) == "ranch_hands"


def test_top_contender_returns_the_leader_when_no_benchmark_leads():
    assert promotion.top_contender(["ranch_hands", "meta_bot"], {"meta_bot"}) == "ranch_hands"


def test_top_contender_raises_when_every_label_is_a_benchmark():
    with pytest.raises(ValueError):
        promotion.top_contender(["meta_bot"], {"meta_bot"})


def test_designate_champion_never_returns_a_benchmark():
    # A stub round-robin where the benchmark wins outright; the champion must be
    # the strongest non-benchmark instead.
    def fake_play(a, b, seed=None):
        return 1 if a == "meta_bot" else (1 if a == "ranch_hands" else -1)

    def fake_build(names):
        return {n: n for n in names}

    champ = promotion.designate_champion(
        ["meta_bot", "ranch_hands", "wide_hands"],
        games=2, play_fn=fake_play, build=fake_build, benchmarks={"meta_bot"},
    )
    assert champ != "meta_bot"


def test_run_and_record_writes_a_non_benchmark_submit_default(tmp_path, monkeypatch):
    """A benchmark may be the gate opponent; it must never be the submit default."""
    from harness import rounds

    monkeypatch.setattr(rounds.promotion, "designate", lambda candidates, pool, **kw: {
        "criterion": "pool_share", "gate_opponent": "meta_bot",
        "submit_default": "ranch_hands", "games": 2, "pool": [], "ranking": []})

    champ_path = tmp_path / "champion.json"
    rounds.run_and_record(
        ["meta_bot", "ranch_hands"], games=2,
        rounds_path=str(tmp_path / "rounds.json"), champion_path=str(champ_path),
        play_fn=lambda a, b, seed=None: 1, build=lambda names: {n: n for n in names},
        benchmarks={"meta_bot"},
    )
    saved = json.loads(champ_path.read_text())
    assert saved["gate_opponent"] == "meta_bot"
    assert saved["submit_default"] != "meta_bot"
