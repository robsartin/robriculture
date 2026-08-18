"""Tests for the flip-rate harness (#77).

ADR-0007's promotion gate treats 200 seeded games as ~200 independent trials.
This module measures whether that is true: for a given pairing, how many
*distinct* outcomes occur across seeds? If a pairing's outcome never flips,
the 200 games are perfectly correlated and the effective sample size is 1, not
200 — the binomial p-value it feeds is not measuring what it appears to. These
tests cover the pure aggregation with an injected `play_fn`, the same pattern
`tests/test_promotion.py` uses, so they need no real (slow) games.
"""

from __future__ import annotations

import pytest

from harness import flip_rate
from harness.flip_rate import PairingFlips, measure_flip_rate, measure_pairing


# --- measure_pairing: play every seed, return the raw outcome sequence ---

def test_measure_pairing_returns_one_outcome_per_seed():
    """Each seed contributes exactly one outcome, in seed order."""
    def fake_play(a, b, seed):
        return 1 if seed % 2 == 0 else -1

    outcomes = measure_pairing("A", "B", seeds=[0, 1, 2, 3], play_fn=fake_play)
    assert outcomes == (1, -1, 1, -1)


def test_measure_pairing_passes_agents_and_seed_through():
    """The injected play_fn sees the exact (agent_a, agent_b, seed) triple."""
    calls = []

    def fake_play(a, b, seed):
        calls.append((a, b, seed))
        return 0

    measure_pairing("CHAL", "CHAMP", seeds=[5, 6], play_fn=fake_play)
    assert calls == [("CHAL", "CHAMP", 5), ("CHAL", "CHAMP", 6)]


# --- PairingFlips: distinct-outcome counting ---

def test_distinct_outcomes_is_one_when_every_seed_agrees():
    """A pairing that never flips has exactly one distinct outcome."""
    pf = PairingFlips(a="market_farmer", b="ranch_hands", outcomes=(1, 1, 1, 1))
    assert pf.distinct_outcomes == 1
    assert pf.flipped is False


def test_distinct_outcomes_counts_wins_losses_and_ties_separately():
    """Win, loss, and tie are three distinct outcome values."""
    pf = PairingFlips(a="a", b="b", outcomes=(1, -1, 0))
    assert pf.distinct_outcomes == 3
    assert pf.flipped is True


def test_flipped_is_true_when_any_two_seeds_disagree():
    """A single disagreement among many identical seeds still counts as a flip."""
    pf = PairingFlips(a="a", b="b", outcomes=(1, 1, 1, -1, 1))
    assert pf.flipped is True


# --- measure_flip_rate: every unordered pairing among the given agents ---

def test_measure_flip_rate_covers_every_unordered_pair():
    """Three agents yield exactly the three unordered pairings, no repeats or self-pairs."""
    def fake_play(a, b, seed):
        return 1

    results = measure_flip_rate({"A": "A", "B": "B", "C": "C"}, seeds=[0], play_fn=fake_play)
    pairs = {frozenset((r.a, r.b)) for r in results}
    assert pairs == {frozenset(("A", "B")), frozenset(("A", "C")), frozenset(("B", "C"))}
    assert len(results) == 3


def test_measure_flip_rate_records_outcomes_per_pairing():
    """Each PairingFlips carries the outcome sequence for its own pairing."""
    strength = {"A": 3, "B": 1}

    def fake_play(a, b, seed):
        return (strength[a] > strength[b]) - (strength[a] < strength[b])

    results = measure_flip_rate({"A": "A", "B": "B"}, seeds=[0, 1, 2], play_fn=fake_play)
    assert len(results) == 1
    assert results[0].outcomes == (1, 1, 1)
    assert results[0].flipped is False


# --- summarize: aggregate flip rate across pairings ---

def test_summarize_reports_fraction_of_pairings_that_flipped():
    """Half the pairings flipping yields a summary flip rate of 0.5."""
    results = [
        PairingFlips(a="A", b="B", outcomes=(1, 1, 1)),
        PairingFlips(a="A", b="C", outcomes=(1, -1, 1)),
    ]
    summary = flip_rate.summarize(results)
    assert summary.pairings == 2
    assert summary.flipped_pairings == 1
    assert summary.flip_rate == pytest.approx(0.5)


def test_summarize_is_zero_with_no_flips():
    """All-agreeing pairings summarize to a zero flip rate."""
    results = [
        PairingFlips(a="A", b="B", outcomes=(1, 1)),
        PairingFlips(a="A", b="C", outcomes=(-1, -1)),
    ]
    summary = flip_rate.summarize(results)
    assert summary.flip_rate == 0.0


def test_summarize_raises_on_no_pairings():
    """No pairings means no measurement; a silent 0.0 would read as 'never flips'."""
    with pytest.raises(ValueError, match="pairing"):
        flip_rate.summarize([])
