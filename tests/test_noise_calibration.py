"""Tests for the seed-only noise calibration harness (#103).

#99/#102 found that at the harness default `--games 2`, a *fixed* genome's
score wanders by stdev 0.0019 (spread 0.0073) just from evolve()'s per-
generation seed rotation (`seed + gen*7919`) — a size comparable to the
stdev 0.0071 that sigma-0.05 offspring actually differ from their parent by.
That means selection is largely sorting seed luck, not genotype quality.

#103 asks: at what `--games` count does seed-only noise sit *materially
below* the offspring spread, so ranking has something real to act on? This
module measures the same seed-only-noise quantity as the #99 scratch
measurement, but swept across several `--games` counts, and adds a way to
estimate how much a 12-generation run's `best` (a running maximum) drifts
upward from noise alone -- so a run's real gain can be judged against that
baseline instead of eyeballed.

Pure aggregation is exercised here against a stub fitness_fn/rng (the same
seam `tests/test_mutation_correlation.py` uses), so these tests need no real
(slow) games.
"""

from __future__ import annotations

import random

import pytest

from harness import noise_calibration as nc
from harness.noise_calibration import NoiseResult


# --- seed_bases: the exact seed rotation evolve() uses ---

def test_seed_bases_matches_evolves_per_generation_rotation():
    """evolve() scores generation `gen` at `seed + gen*7919`; seed_bases must
    reproduce that exact formula so the noise measured is the noise evolve()
    actually experiences, not an approximation of it."""
    assert nc.seed_bases(seed=1, n=4) == [1, 1 + 7919, 1 + 2 * 7919, 1 + 3 * 7919]


def test_seed_bases_length_matches_n():
    """Requesting n seed bases yields exactly n of them."""
    assert len(nc.seed_bases(seed=0, n=10)) == 10


# --- measure_noise: score one fixed genome at each seed base, at one games count ---

def test_measure_noise_calls_fitness_fn_once_per_seed_base():
    """One score per seed base, in order, at the requested games count."""
    calls = []

    def fake_fitness(games, seed_base):
        calls.append((games, seed_base))
        return 0.5

    result = nc.measure_noise(games=4, seed_bases=[1, 100, 200], fitness_fn=fake_fitness)
    assert calls == [(4, 1), (4, 100), (4, 200)]
    assert isinstance(result, NoiseResult)
    assert result.games == 4
    assert result.scores == (0.5, 0.5, 0.5)


# --- NoiseResult: summarize a fixed genome's scores across seed bases ---

def test_noise_result_spread_is_max_minus_min():
    """Spread is the noise-driven peak-to-trough range #99 originally reported."""
    r = NoiseResult(games=2, scores=(0.37, 0.38, 0.36))
    assert r.spread == pytest.approx(0.02)


def test_noise_result_stdev_matches_sample_stdev_of_ten_scores():
    """Uses sample stdev (statistics.stdev, ddof=1) to match the #99/#102
    scratch measurement's reported numbers exactly, for reproducibility."""
    r = NoiseResult(games=2, scores=(0.3782, 0.3728, 0.3732, 0.3742, 0.3739,
                                     0.3755, 0.3741, 0.3728, 0.3709, 0.3745))
    assert r.stdev == pytest.approx(0.0019, abs=0.0001)
    assert r.spread == pytest.approx(0.0073, abs=0.0001)


def test_noise_result_stdev_is_zero_with_fewer_than_two_scores():
    """A single score has no spread to measure -- 0.0, not a crash."""
    r = NoiseResult(games=2, scores=(0.4,))
    assert r.stdev == 0.0
    assert r.spread == 0.0


def test_noise_result_stdev_is_zero_with_no_scores():
    """Zero scores measured means no evidence of noise -- 0.0, not a crash."""
    r = NoiseResult(games=2, scores=())
    assert r.stdev == 0.0
    assert r.spread == 0.0
    assert r.mean == 0.0


# --- measure_noise_by_games: sweep the same seed bases across several games counts ---

def test_measure_noise_by_games_returns_one_result_per_games_count_in_order():
    """Sweeping [2, 4, 8] yields three NoiseResults, in the order requested,
    each carrying the requested games count."""
    def fake_fitness(games, seed_base):
        return 1.0 / games  # deterministic stand-in, decreasing with games

    results = nc.measure_noise_by_games(games_counts=[2, 4, 8], seed_bases=[1, 2, 3],
                                        fitness_fn=fake_fitness)
    assert [r.games for r in results] == [2, 4, 8]
    assert all(len(r.scores) == 3 for r in results)


def test_measure_noise_by_games_uses_the_same_seed_bases_at_every_games_count():
    """Each games count is measured at the identical seed bases, so the sweep
    isolates the effect of --games rather than confounding it with different
    seed draws."""
    seen = []

    def recording_fitness(games, seed_base):
        seen.append((games, seed_base))
        return 0.5

    nc.measure_noise_by_games(games_counts=[2, 4], seed_bases=[10, 20], fitness_fn=recording_fitness)
    assert seen == [(2, 10), (2, 20), (4, 10), (4, 20)]


# --- bootstrap_max_drift: expected upward drift of a running max under pure noise ---

def test_bootstrap_max_drift_is_zero_for_constant_samples():
    """No variance at all -> the max of any number of draws never exceeds the
    mean -> zero expected drift."""
    drift = nc.bootstrap_max_drift(samples=[0.5, 0.5, 0.5], n_draws=12, trials=100,
                                   rng=random.Random(1))
    assert drift == pytest.approx(0.0)


def test_bootstrap_max_drift_is_positive_for_varying_samples():
    """With real spread, the max of several noisy draws typically lands above
    the mean -- that upward bias is exactly what a 12-generation best-so-far
    series accumulates from noise alone, with nothing to do with learning."""
    samples = [0.30, 0.35, 0.40, 0.45, 0.50]
    drift = nc.bootstrap_max_drift(samples=samples, n_draws=12, trials=2000,
                                   rng=random.Random(2))
    assert drift > 0.0


def test_bootstrap_max_drift_grows_with_more_draws():
    """Taking the max over more generations gives noise more chances to peak
    -- expected drift should increase (or at least not shrink) with n_draws."""
    samples = [0.30, 0.35, 0.40, 0.45, 0.50]
    drift_small = nc.bootstrap_max_drift(samples=samples, n_draws=2, trials=4000,
                                         rng=random.Random(3))
    drift_large = nc.bootstrap_max_drift(samples=samples, n_draws=12, trials=4000,
                                         rng=random.Random(3))
    assert drift_large >= drift_small


def test_bootstrap_max_drift_is_deterministic_given_a_seeded_rng():
    """Same rng seed, same samples => identical drift estimate (ADR-0005)."""
    samples = [0.30, 0.35, 0.40, 0.45, 0.50]
    a = nc.bootstrap_max_drift(samples=samples, n_draws=12, trials=500, rng=random.Random(5))
    b = nc.bootstrap_max_drift(samples=samples, n_draws=12, trials=500, rng=random.Random(5))
    assert a == b


def test_bootstrap_max_drift_is_zero_with_no_samples():
    """No noise samples measured means no basis for a drift estimate -- 0.0,
    not a crash."""
    assert nc.bootstrap_max_drift(samples=[], n_draws=12, trials=100, rng=random.Random(1)) == 0.0
