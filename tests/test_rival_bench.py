"""The #219 experiment's counting and verdict logic, pinned before any number."""

from __future__ import annotations

from harness import rival_bench as rb


def test_the_declared_constants():
    assert rb.CHAMPION == "dense_farm" and rb.CONTENDER == "rival_aware"
    assert rb.SEEDS == tuple(range(400, 416))
    assert rb.CHAMPION_BAR == 0.60 and rb.ANCHOR_BAR == 0.90


def test_animal_buys_counts_kinds_across_turns():
    actions = [{"market": [["BUY_ANIMAL", "COW", 1], ["SELL", "WOOL", 3]]},
               {"market": [["BUY_ANIMAL", "SHEEP", 1], ["BUY_ANIMAL", "COW", 1]]},
               {"market": []}]
    assert rb.animal_buys(actions) == {"COW": 2, "SHEEP": 1}


def test_mechanism_fired_needs_more_cows_and_fewer_sheep():
    assert rb.mechanism_fired({"COW": 6, "SHEEP": 2}, {"COW": 3, "SHEEP": 5}) is True
    assert rb.mechanism_fired({"COW": 6, "SHEEP": 5}, {"COW": 3, "SHEEP": 5}) is False
    assert rb.mechanism_fired({"COW": 3, "SHEEP": 2}, {"COW": 3, "SHEEP": 5}) is False


def _row(name, wins, games=16):
    return {"name": "rival_aware", "opponent": name, "wins": wins, "ties": 0, "games": games,
            "seeds": "400-415"}


def test_rate_is_zero_on_zero_games_rather_than_dividing_by_it():
    # Whole-branch review minor: a row with games=0 (never expected from a real
    # run, but format_rows/criterion should not blow up on one) must not raise.
    assert rb._rate({"wins": 0, "games": 0}) == 0.0
    assert rb._rate({"wins": 3, "games": 6}) == 0.5


def test_criterion_passes_only_at_both_bars():
    anchors = [_row(n, 15) for n in ("meta_bot", "ranch_hands", "market_farmer",
                                     "ranch_adaptive", "wheat_hands", "field_rival")]
    ok = rb.criterion(_row("dense_farm", 10), anchors)           # 62.5% and 93.75%
    assert ok["passed"] is True and ok["failing"] == []
    champ_short = rb.criterion(_row("dense_farm", 9), anchors)   # 56.25% < 60%
    assert champ_short["passed"] is False and champ_short["failing"] == ["dense_farm"]
    anchors[0] = _row("meta_bot", 14)                            # 87.5% < 90%
    anchor_short = rb.criterion(_row("dense_farm", 10), anchors)
    assert anchor_short["passed"] is False and anchor_short["failing"] == ["meta_bot"]


def test_criterion_counts_a_tie_as_not_a_win():
    tied = dict(_row("dense_farm", 9), ties=7)
    assert rb.criterion(tied, [_row("meta_bot", 16)])["champion_rate"] == 9 / 16


def test_ablation_verdict_reads_the_gap_between_contender_and_ablation():
    # #219 whole-branch review, recommendation 1: an unconditional-COW ablation
    # isolates whether the rival-reading part of the mechanism does anything,
    # separate from the "cheaper animal buys more head" effect item A records.
    assert rb.ablation_verdict(15, 10, 16) == "rival signal does work"    # gap 5 >= 2
    assert rb.ablation_verdict(15, 13, 16) == "rival signal does work"    # gap 2 >= 2
    assert rb.ablation_verdict(15, 14, 16) == "cannot tell"               # gap 1
    assert rb.ablation_verdict(15, 15, 16) == "rival signal does no work"  # gap 0
    assert rb.ablation_verdict(10, 15, 16) == "rival signal does no work"  # ablation ahead


def test_format_rows_one_line_per_opponent_with_rate():
    text = rb.format_rows([_row("dense_farm", 10), _row("meta_bot", 15)])
    lines = [ln for ln in text.splitlines() if ln.strip()]
    assert len(lines) == 3 and "dense_farm" in lines[1] and "10/16" in lines[1]


# --- the cows-from-day-N timing arm (#219, recorded not gated) --------------

def test_the_timing_constants():
    assert rb.TIMING_DAYS == (4, 6, 8, 10, 12)
    assert rb.TIMING_NAME == "cows_from_day"
    assert rb.ABLATION_CHAMPION_WINS == 11


def test_first_day_at_or_above_returns_first_qualifying_day():
    series = [(4, 0), (6, 1), (8, 2), (10, 2)]
    assert rb.first_day_at_or_above(series, 2) == 8


def test_first_day_at_or_above_is_none_when_never_reached():
    series = [(4, 0), (6, 1)]
    assert rb.first_day_at_or_above(series, 2) is None


def test_first_day_at_or_above_reports_first_day_even_after_a_later_drop():
    # A series that reaches the threshold and then falls back below it must
    # still report the FIRST day it qualified, not the last.
    series = [(4, 0), (6, 2), (8, 1), (10, 3)]
    assert rb.first_day_at_or_above(series, 2) == 6


def _timing_row(day, wins, games=16):
    return {"name": rb.TIMING_NAME, "opponent": "dense_farm", "wins": wins,
            "ties": 0, "games": games, "seeds": "400-415", "day": day}


def test_format_timing_has_one_line_per_day_plus_two_reference_lines():
    rows = [_timing_row(4, 8), _timing_row(6, 10), _timing_row(8, 12),
            _timing_row(10, 9), _timing_row(12, 7)]
    text = rb.format_timing(rows, 15, 11)
    assert "8/16" in text
    assert "rival_aware 15/16" in text
    assert "unconditional cows 11/16" in text


def test_timing_reading_says_timing_explains_the_gap_when_a_clock_matches_contender():
    rows = [_timing_row(8, 14)]  # >= contender_wins(15) - 1
    assert rb.timing_reading(rows, 15, 11) == \
        "a clock reproduces the contender: timing explains the gap"


def test_timing_reading_says_rival_signal_does_something_a_clock_cannot_when_no_clock_beats_ablation():
    rows = [_timing_row(n, 11) for n in rb.TIMING_DAYS]  # all == ablation_wins(11)
    assert rb.timing_reading(rows, 15, 11) == \
        "no clock gets past unconditional cows: the rival signal does something a clock cannot"


def test_timing_reading_reports_partial_with_best_clock_when_neither_bound_hits():
    rows = [_timing_row(4, 12), _timing_row(6, 13)]  # neither >=14 nor all <=12
    assert rb.timing_reading(rows, 15, 11) == "partial: the best clock is N=6 at 13/16"
