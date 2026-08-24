"""Multi-seed experiment evaluation (#71)."""
from __future__ import annotations

from harness import multi_seed as ms


def _row(seed=0, share=0.4, plants_peak=20, land_purchases=(("NE", 12, 5000),)):
    # share=0.4 is deliberately above PROMOTION_BAR (0.3760) so tests that
    # don't mention share still isolate the land/plants clause they name.
    return {"seed": seed, "share": share, "plants_peak": plants_peak,
            "land_purchases": list(land_purchases), "animals_peak": 0,
            "hands_peak": 9, "reward": 25000.0}


def test_seed_verdict_true_when_land_bought_and_enough_tiles_planted():
    assert ms.seed_verdict(_row()) is True


def test_seed_verdict_false_when_no_land_was_bought():
    # #113's outcome: the genome farmed fine but never expanded.
    assert ms.seed_verdict(_row(land_purchases=())) is False


def test_seed_verdict_false_when_planted_tiles_stay_under_the_bar():
    # 11 is the ceiling every agent we own already hits, so it proves nothing.
    assert ms.seed_verdict(_row(plants_peak=11)) is False


def test_seed_verdict_true_exactly_at_the_bar():
    assert ms.seed_verdict(_row(plants_peak=ms.MIN_PLANTS_PEAK)) is True


def test_seed_verdict_false_when_share_stays_below_promotion_bar():
    # This is the exact case the branch's own smoke run produced: land
    # bought, plants_peak well past MIN_PLANTS_PEAK (21 and 62 tiles), but
    # share (0.1850 and 0.3134) below PROMOTION_BAR (0.3760). The old
    # two-clause verdict would have called both of those seeds a success;
    # planting broadly is not the same as scoring well.
    assert ms.seed_verdict(_row(share=0.10)) is False


def test_summarize_seeds_reports_the_success_rate():
    rows = [_row(seed=0), _row(seed=1, land_purchases=()), _row(seed=2)]
    got = ms.summarize_seeds(rows)
    assert got["n"] == 3
    assert got["n_supported"] == 2
    assert got["rate"] == 2 / 3


def test_summarize_seeds_reports_share_spread():
    rows = [_row(seed=0, share=0.30), _row(seed=1, share=0.50)]
    got = ms.summarize_seeds(rows)
    assert got["share_mean"] == 0.40
    assert got["share_max"] == 0.50
    assert got["share_min"] == 0.30


def test_summarize_seeds_reports_the_best_planted_count():
    rows = [_row(seed=0, plants_peak=12), _row(seed=1, plants_peak=31)]
    assert ms.summarize_seeds(rows)["plants_peak_max"] == 31


def test_summarize_seeds_handles_no_rows():
    # A run where every seed crashed must report emptiness, not divide by zero.
    got = ms.summarize_seeds([])
    assert got["n"] == 0 and got["rate"] == 0.0
