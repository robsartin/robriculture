"""The verdict logic for #172 Stage 1, pinned before the numbers exist: the
grid, the per-state rho, undefined states excluded not scored, and the bar."""

from __future__ import annotations

from harness.objective_check import BAR, GRID, format_table, score_state, verdict


def test_the_grid_is_the_declared_eleven_with_the_control_first():
    assert GRID == (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)
    assert BAR == 0.40


def test_score_state_ranks_and_names_the_bests():
    predicted = {0.0: 100.0, 0.5: 300.0, 1.0: 200.0}
    truth = {0.0: 10.0, 0.5: 30.0, 1.0: 20.0}
    got = score_state(predicted, truth)
    assert got["rho"] == 1.0
    assert got["predicted_best"] == 0.5 and got["true_best"] == 0.5
    assert got["n"] == 3


def test_score_state_is_undefined_when_truth_has_no_rank_variance():
    predicted = {0.0: 1.0, 0.5: 2.0, 1.0: 3.0}
    truth = {0.0: 7.0, 0.5: 7.0, 1.0: 7.0}
    assert score_state(predicted, truth)["rho"] is None


def test_verdict_passes_at_the_bar_and_fails_just_under_it():
    assert verdict([0.4, 0.4, 0.4])["passed"] is True
    assert verdict([0.39, 0.39, 0.39])["passed"] is False


def test_verdict_uses_the_median_and_excludes_undefined_states():
    got = verdict([None, 0.9, 0.1, 0.5])
    assert got["median"] == 0.5
    assert got["defined"] == 3 and got["undefined"] == 1
    assert got["passed"] is True


def test_verdict_with_nothing_defined_fails_and_says_so():
    got = verdict([None, None])
    assert got["passed"] is False and got["median"] is None and got["defined"] == 0


def test_format_table_has_one_line_per_state_and_prints_undefined():
    rows = [
        {"seed": 0, "day": 3, "n": 11, "rho": 0.5, "predicted_best": 0.2, "true_best": 0.3,
         "seconds_per_rollout": 0.71},
        {"seed": 0, "day": 5, "n": 11, "rho": None, "predicted_best": 0.0, "true_best": 0.0,
         "seconds_per_rollout": 0.60},
    ]
    text = format_table(rows)
    lines = [ln for ln in text.splitlines() if ln.strip()]
    assert len(lines) == 3                      # header + 2 rows
    assert "undefined" in lines[2]
    assert "0.50" in lines[1] and "0.71" in lines[1]
