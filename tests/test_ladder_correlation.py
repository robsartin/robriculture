"""Tests for the local-vs-ladder correlation tool (#80).

ADR-0008 pivoted the project on the claim that self-play is a broken fitness
signal and that we need a local signal that actually correlates with the
ladder — a claim never measured. These tests cover the Spearman implementation
against hand-computed cases (including a tie), the ladder-score bookkeeping
(median + noise-band pairs), and the two local-signal wrappers with injected
fakes so most of this file needs no real (slow) games.
"""

from __future__ import annotations

import pytest

from harness import ladder_correlation as lc


# --- _average_ranks: 1-based ranks, ties averaged ---

def test_average_ranks_assigns_plain_ranks_when_no_ties():
    """No ties: ranks are just the sort positions, 1-based."""
    assert lc._average_ranks([30, 10, 20]) == [3, 1, 2]


def test_average_ranks_averages_the_tied_block():
    """Two values tied for 2nd/3rd place both get rank 2.5."""
    assert lc._average_ranks([1, 2, 2, 4]) == [1, 2.5, 2.5, 4]


# --- spearman: rank correlation, ties averaged, stdlib only ---

def test_spearman_is_one_when_perfectly_correlated():
    """Identical orderings correlate perfectly."""
    assert lc.spearman([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1.0)


def test_spearman_is_minus_one_when_perfectly_anticorrelated():
    """Reversed orderings correlate perfectly negatively."""
    assert lc.spearman([1, 2, 3, 4], [40, 30, 20, 10]) == pytest.approx(-1.0)


def test_spearman_matches_hand_computation_when_there_is_a_tie():
    """x has a tied pair (ranks 2.5/2.5); the result must match the by-hand
    rank-correlation computation, not the tie-free shortcut formula.

    x = [1, 2, 2, 4] -> ranks [1, 2.5, 2.5, 4], mean 2.5
    y = [1, 3, 2, 4] -> ranks [1, 3, 2, 4],     mean 2.5
    cov = (-1.5)(-1.5) + (0)(0.5) + (0)(-0.5) + (1.5)(1.5) = 4.5
    var_x = 1.5^2 + 0 + 0 + 1.5^2 = 4.5
    var_y = 1.5^2 + 0.5^2 + 0.5^2 + 1.5^2 = 5.0
    rho = 4.5 / sqrt(4.5 * 5.0) = 4.5 / sqrt(22.5) = 0.9486832980505138
    """
    rho = lc.spearman([1, 2, 2, 4], [1, 3, 2, 4])
    assert rho == pytest.approx(0.9486832980505138)


def test_spearman_is_none_when_fewer_than_two_points():
    """A single point (or none) can't define an ordering; don't fabricate a number."""
    assert lc.spearman([1], [1]) is None
    assert lc.spearman([], []) is None


def test_spearman_is_none_when_one_series_has_no_variance():
    """Every value tied means every rank tied: the denominator is zero."""
    assert lc.spearman([5, 5, 5], [1, 2, 3]) is None


def test_spearman_raises_when_lengths_differ():
    """Mismatched series is a caller bug, not a silently-truncated answer."""
    with pytest.raises(ValueError, match="length"):
        lc.spearman([1, 2, 3], [1, 2])


# --- ladder score bookkeeping: hardcoded, not fetched (ADR-0005) ---

def test_median_ladder_score_uses_the_median_of_all_recorded_submissions():
    """ranch_hands has five submissions spanning the noise band; the median
    (515.4) is what the tool must use, not the mean or the latest value."""
    assert lc.median_ladder_score("ranch_hands") == pytest.approx(515.4)


def test_ladder_medians_covers_every_recorded_agent():
    """Every agent in LADDER_SCORES gets a median, and nothing else."""
    medians = lc.ladder_medians()
    assert set(medians) == set(lc.LADDER_SCORES)
    assert medians["ranch_adaptive"] == pytest.approx(520.6)


def test_ladder_scores_are_reproducible_across_calls():
    """ADR-0005: hardcoded data, so re-running yields the identical table."""
    assert lc.ladder_medians() == lc.ladder_medians()


# --- pairs_beyond_noise_band: which agent pairs the ladder can distinguish ---

def test_pairs_beyond_noise_band_flags_gaps_over_the_band():
    """A gap strictly greater than the band is real signal, not noise."""
    medians = {"a": 0.0, "b": 5.0, "c": 20.0}
    pairs = lc.pairs_beyond_noise_band(medians, band=10.0)
    labels = {frozenset((a, b)) for a, b, _gap in pairs}
    assert labels == {frozenset(("a", "c")), frozenset(("b", "c"))}


def test_pairs_beyond_noise_band_excludes_gaps_within_the_band():
    """A gap smaller than the band could be explained by the band alone."""
    medians = {"a": 0.0, "b": 5.0}
    assert lc.pairs_beyond_noise_band(medians, band=10.0) == []


def test_pairs_beyond_noise_band_uses_the_adr_0007_band_by_default():
    """The default band is ADR-0007's refreshed 98.4-point spread (#80)."""
    assert lc.NOISE_BAND == pytest.approx(98.4)


# --- head_to_head_win_rates: reuses promotion.round_robin_rank ---

def _strength_play(strength):
    """Fake play_fn: higher strength always wins (from tests/test_promotion.py)."""
    def play(a, b, seed):
        return (strength[a] > strength[b]) - (strength[a] < strength[b])
    return play


def test_head_to_head_win_rates_reuses_round_robin_rank():
    """The head-to-head signal is exactly promotion.round_robin_rank's win-rate,
    restricted to the named agents — not a reimplementation."""
    rates = lc.head_to_head_win_rates(
        ["A", "B", "C"],
        games=2,
        play_fn=_strength_play({"A": 3, "B": 2, "C": 1}),
        build=lambda names: {n: n for n in names},
    )
    assert rates["A"] > rates["B"] > rates["C"]
    assert rates["A"] == pytest.approx(1.0)
    assert rates["C"] == pytest.approx(0.0)


# --- pool_share_scores: reuses promotion.pool_share_rank ---

def _named(tag):
    """A stub agent carrying a tag the stub rewards_fn can key off."""
    def agent(obs):
        return {"farmer": ["PASS"], "hands": [], "market": []}
    agent.tag = tag
    return agent


def _stub_rewards(a, b, seed=None):
    """Reward equals the agent's tag length — longer tag scores higher."""
    return (float(len(getattr(a, "tag", ""))), float(len(getattr(b, "tag", ""))))


def test_pool_share_scores_reuses_pool_share_rank():
    """The pool-share signal is exactly promotion.pool_share_rank's share."""
    shares = lc.pool_share_scores(
        ["aaa", "a"],
        anchor_names=["aa"],
        games=2,
        rewards_fn=_stub_rewards,
        build=lambda names: {n: _named(n) for n in names},
    )
    assert shares["aaa"] > shares["a"]


def test_pool_share_scores_excludes_a_candidate_that_is_also_an_anchor():
    """Several ladder-scored agents (ranch_hands, market_farmer, ranch_adaptive)
    are themselves DEFAULT_ANCHORS members; pool_share_rank's self-exclusion
    must still hold when reached through this wrapper."""
    seen = []

    def recording_rewards(a, b, seed=None):
        seen.append((getattr(a, "tag", ""), getattr(b, "tag", "")))
        return (100.0, 100.0)

    lc.pool_share_scores(
        ["x"],
        anchor_names=["x", "y"],
        games=2,
        rewards_fn=recording_rewards,
        build=lambda names: {n: _named(n) for n in names},
    )
    assert all({a, b} != {"x"} for a, b in seen)


# --- build_report: assembles the table + both correlations ---

def test_build_report_computes_both_correlations_from_injected_signals():
    """No real games: both local-signal maps are supplied directly."""
    medians = {"a": 10.0, "b": 20.0, "c": 30.0}
    h2h = {"a": 0.1, "b": 0.5, "c": 0.9}
    share = {"a": 0.9, "b": 0.5, "c": 0.1}
    report = lc.build_report(names=["a", "b", "c"], head_to_head=h2h,
                             pool_share=share, medians=medians, noise_band=5.0)
    assert report.n == 3
    assert report.head_to_head_rho == pytest.approx(1.0)
    assert report.pool_share_rho == pytest.approx(-1.0)


def test_build_report_flags_pairs_beyond_the_supplied_noise_band():
    """The report's beyond_band list comes from the same medians as the table."""
    medians = {"a": 0.0, "b": 5.0, "c": 20.0}
    h2h = {"a": 0.1, "b": 0.5, "c": 0.9}
    share = {"a": 0.1, "b": 0.5, "c": 0.9}
    report = lc.build_report(names=["a", "b", "c"], head_to_head=h2h,
                             pool_share=share, medians=medians, noise_band=10.0)
    labels = {frozenset((a, b)) for a, b, _gap in report.beyond_band}
    assert labels == {frozenset(("a", "c")), frozenset(("b", "c"))}


def test_build_report_rows_carry_the_submission_count():
    """Each row records how many ladder submissions its median came from, so
    the printed table can show n per agent alongside the aggregate n."""
    medians = {"ranch_hands": 515.4}
    h2h = {"ranch_hands": 0.5}
    share = {"ranch_hands": 0.5}
    report = lc.build_report(names=["ranch_hands"], head_to_head=h2h,
                             pool_share=share, medians=medians)
    assert report.rows[0]["n_submissions"] == 5


def test_build_report_defaults_to_every_recorded_agent():
    """Omitting `names`/`medians` falls back to the full real LADDER_SCORES table."""
    names = list(lc.LADDER_SCORES)
    h2h = {n: 0.5 for n in names}
    share = {n: 0.5 for n in names}
    report = lc.build_report(head_to_head=h2h, pool_share=share)
    assert report.n == len(lc.LADDER_SCORES)
    assert {r["name"] for r in report.rows} == set(lc.LADDER_SCORES)


# --- _fmt_rho: the CLI's one non-trivial formatting decision ---

def test_fmt_rho_formats_a_number_when_present():
    """A real coefficient prints to 4 decimal places."""
    assert lc._fmt_rho(0.5) == "0.5000"


def test_fmt_rho_reports_undefined_when_none():
    """None must never be printed as a bare number — that would look like a
    real (zero) correlation instead of 'we couldn't compute one'."""
    assert lc._fmt_rho(None) == "undefined (no rank variance)"


# --- integration smoke: real games wire the two signals together (slow-ish) ---

def test_local_signals_run_real_games_end_to_end():
    """Two real registered strategies, one real anchor, minimal games — proves
    the wiring (build_agents, opponent_record, round_robin_rank, pool_share_rank)
    actually plays, not just that the fakes behave (see test_promotion.py's
    equivalent `test_promotion_test_runs_real_games`)."""
    names = ["market_farmer", "ranch_hands"]
    h2h = lc.head_to_head_win_rates(names, games=1)
    share = lc.pool_share_scores(names, anchor_names=["wheat_hands"], games=1)
    assert set(h2h) == set(names)
    assert set(share) == set(names)
    for rate in h2h.values():
        assert 0.0 <= rate <= 1.0
    for s in share.values():
        assert 0.0 <= s <= 1.0
