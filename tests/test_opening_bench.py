"""The #207 bench: pick the book, control it, then measure it.

Every pure helper the experiment's verdict is computed from is pinned here.
The declared criteria themselves are asserted against the numbers #207 states,
so the bar cannot drift once the results exist (ADR-0007).
"""

from __future__ import annotations

import pytest

from harness import opening_bench as ob

BAND = {"episode": "e", "seat": 1, "final_money": 74332.0,
        "revenue": {"MILK": 50.0, "MELON": 50.0}}


def _row(episode, final_money, revenue):
    return {"episode": episode, "seat": 1, "final_money": final_money,
            "revenue": revenue}


# --- the cohort and the book ---

def test_livestock_share_counts_milk_wool_egg_and_fertilizer():
    """#157's livestock+fertilizer line: fertilizer is the free byproduct and
    counts, which is 17% of the winning field's revenue on its own."""
    revenue = {"MILK": 10.0, "WOOL": 10.0, "EGG": 10.0, "FERTILIZER": 10.0,
               "MELON": 60.0}
    assert ob.livestock_share(revenue) == pytest.approx(0.40)


def test_livestock_share_is_zero_when_nothing_was_sold():
    """A farm with no revenue is not a 0/0 crash and not a 100% rancher."""
    assert ob.livestock_share({}) == 0.0


def test_in_cohort_accepts_the_forty_to_sixty_percent_band():
    """#207 names the 40-60% livestock-share cohort; findings.md reports it
    as n=13, 13/13 against us, median final 74,332."""
    assert ob.in_cohort(BAND) is True


def test_in_cohort_rejects_a_share_below_the_band():
    """0-20% and 20-40% are different buckets with different records."""
    assert ob.in_cohort(_row("e", 74332.0, {"MILK": 30.0, "MELON": 70.0})) is False


def test_in_cohort_rejects_a_share_at_or_above_sixty_percent():
    """The band is half-open, so 60% belongs to the 60-100% bucket."""
    assert ob.in_cohort(_row("e", 74332.0, {"MILK": 60.0, "MELON": 40.0})) is False


def test_in_cohort_rejects_a_farm_that_never_grew_its_starting_money():
    """findings.md's buckets are over the 62 opponents that finished above the
    3,000 they started with; a farm that did not is not a winner to copy."""
    assert ob.in_cohort(_row("e", 3000.0, {"MILK": 50.0, "MELON": 50.0})) is False


def test_select_book_takes_the_cohort_member_with_the_most_final_money():
    """The declared rule, so the choice cannot be made after the numbers."""
    rows = [_row("a", 50000.0, {"MILK": 50.0, "MELON": 50.0}),
            _row("b", 90000.0, {"MILK": 50.0, "MELON": 50.0}),
            _row("c", 10.0, {"MILK": 50.0, "MELON": 50.0})]
    assert ob.select_book(rows)["episode"] == "b"


def test_select_book_ignores_rows_outside_the_cohort_however_rich_they_are():
    """A 90% -livestock farm may well be richer; it is not this cohort."""
    rows = [_row("a", 50000.0, {"MILK": 50.0, "MELON": 50.0}),
            _row("rich", 500000.0, {"MILK": 90.0, "MELON": 10.0})]
    assert ob.select_book(rows)["episode"] == "a"


def test_select_book_breaks_a_tie_on_episode_name_ascending():
    """Two equal finals must not select by dict iteration order."""
    rows = [_row("z", 50000.0, {"MILK": 50.0, "MELON": 50.0}),
            _row("a", 50000.0, {"MILK": 50.0, "MELON": 50.0})]
    assert ob.select_book(rows)["episode"] == "a"


def test_select_book_raises_when_the_cohort_is_empty():
    """#207 is BLOCKED, not re-specified, if the cohort has no member."""
    with pytest.raises(ValueError, match="cohort"):
        ob.select_book([_row("a", 3000.0, {"MELON": 100.0})])


# --- the positive control ---

def test_control_passes_only_when_the_right_book_matches_and_the_shifted_one_misses():
    """A control that cannot fail proves nothing: the off-by-one arm must miss."""
    assert ob.control_verdict(0.0, 0.9, recorded=5000.0) is True


def test_control_fails_when_the_replayed_opening_misses_its_own_day_three_money():
    """#207 alternative 3: recorded actions insufficient to re-drive the sim."""
    assert ob.control_verdict(0.5, 0.9, recorded=5000.0) is False


def test_control_fails_when_the_off_by_one_arm_also_reconstructs_the_money():
    """Then the probe does not discriminate and the run is void, not a pass."""
    assert ob.control_verdict(0.0, 0.0, recorded=5000.0) is False


def test_control_fails_when_day_three_money_is_still_the_starting_cash():
    """3,000 vs 3,000 is a match that any agent alive would produce."""
    assert ob.control_verdict(0.0, 0.9, recorded=3000.0) is False


def test_the_control_tolerance_is_the_declared_seven_point_three_percent():
    """#157's median residual, declared by #204 and reused by #207 verbatim."""
    assert ob.RESIDUAL_TOLERANCE == 0.073


# --- the day-16 necessary condition ---

def test_day16_row_passes_when_all_three_declared_bars_are_met():
    """#207: animals >= 8, livestock revenue >= 30%, planted >= 30."""
    assert ob.day16_passed({"animals": 8, "livestock_share": 0.30,
                            "planted": 30}) is True


@pytest.mark.parametrize("field,value", [("animals", 7),
                                         ("livestock_share", 0.29),
                                         ("planted", 29)])
def test_day16_row_fails_when_any_single_bar_is_missed(field, value):
    """All three, not two of three -- that is what separates #207 from #196."""
    row = {"animals": 8, "livestock_share": 0.30, "planted": 30}
    row[field] = value
    assert ob.day16_passed(row) is False


def test_day16_condition_needs_every_seed_not_just_the_median():
    """The declared stricter reading of "over 6 fresh seeds"."""
    good = {"animals": 8, "livestock_share": 0.5, "planted": 40}
    bad = dict(good, animals=0)
    assert ob.day16_verdict([good, good, bad]) is False
    assert ob.day16_verdict([good, good, good]) is True


def test_day16_is_probed_at_the_start_of_day_sixteen():
    """Same clock as the opening: 24 turns to a day, days 0-indexed."""
    from kaggisim import economy
    assert ob.DAY16_STEP == 16 * economy.CONFIG_DEFAULTS["turnsPerDay"] == 384


# --- the pass criterion ---

def test_our_seat_alternates_so_neither_side_is_measured_twice():
    """#207 declares "sides alternated" over the 16 seeds."""
    assert [ob.our_seat(i) for i in range(4)] == [0, 1, 0, 1]


def test_a_tie_is_not_a_win():
    """Declared stricter reading of "beats" / "holds"."""
    assert ob.won({"ours": 100.0, "theirs": 100.0}) is False
    assert ob.won({"ours": 101.0, "theirs": 100.0}) is True


def test_win_rate_is_wins_over_every_game_played():
    """Ties sit in the denominator, which is what makes them count as losses."""
    rows = [{"ours": 2.0, "theirs": 1.0}, {"ours": 1.0, "theirs": 1.0},
            {"ours": 0.0, "theirs": 1.0}, {"ours": 2.0, "theirs": 1.0}]
    assert ob.win_rate(rows) == pytest.approx(0.5)


def test_the_declared_bars_are_the_ones_the_issue_states():
    """60% of 16 against the champion, 90% of 16 against every anchor."""
    assert ob.CHAMPION_BAR == 0.60
    assert ob.ANCHOR_BAR == 0.90
    assert len(ob.CRITERION_SEEDS) == 16


def test_the_champion_is_the_gate_opponent_recorded_in_champion_json():
    """ADR-0007 measures an experiment against `gate_opponent`, not the
    submit default -- and it is pinned to the copy committed on this branch."""
    assert ob.CHAMPION == "meta_bot"


def test_the_anchors_are_the_frozen_comparability_pool():
    """`harness.evolve.DEFAULT_ANCHORS`, so #207 is comparable with #196/#202."""
    from harness.evolve import DEFAULT_ANCHORS
    assert ob.ANCHORS == tuple(DEFAULT_ANCHORS)


def test_criterion_passes_only_when_the_champion_and_every_anchor_clear_their_bar():
    """Both clauses, and every anchor -- this is the one that failed #193."""
    rates = {a: 1.0 for a in ob.ANCHORS}
    assert ob.criterion_passed(0.625, rates) is True
    assert ob.criterion_passed(0.5625, rates) is False
    assert ob.criterion_passed(0.625, dict(rates, wheat_hands=0.875)) is False


def test_criterion_fails_when_an_anchor_was_never_measured():
    """A missing anchor must not read as a pass by absence."""
    rates = {a: 1.0 for a in ob.ANCHORS if a != "field_rival"}
    assert ob.criterion_passed(1.0, rates) is False


# --- reading a game ---

def test_money_at_reads_the_named_players_cash_at_that_state_index():
    """The control's probe. Reading the wrong seat books the opponent's day 3."""
    steps = [[{"observation": {"player": 0,
                               "farms": [{"money": 1.0}, {"money": 2.0}]}},
              {"observation": {}}]]
    assert ob.money_at(steps, 0, 1) == 2.0


def test_money_at_reports_none_past_the_end_of_a_short_episode():
    """A crashed game has no day 3; that is a miss, not a zero."""
    assert ob.money_at([], 0, 0) is None


def test_farm_shape_counts_plant_tiles_and_animal_tiles_separately():
    """planted and animals are two of #207's three day-16 bars."""
    tiles = [[{"kind": "PLANT"}, {"kind": "PASTURE", "animal": "COW"}],
             [{"kind": "WEED"}, None]]
    steps = [[{"observation": {"player": 0, "farms": [{"tiles": tiles}]}}]]
    assert ob.farm_shape(steps, 0, 0) == {"planted": 1, "animals": 1}


# --- the board fingerprint: salvage, NOT this experiment's declared control ---

def _board(tiles):
    return [[{"observation": {"player": 0, "farms": [{"tiles": tiles}]}}]]


def test_board_fingerprint_is_equal_for_two_identical_boards():
    """It has to be stable before it can be discriminating."""
    tiles = [[{"kind": "PLANT", "crop": "MELON"}, {"kind": "PASTURE", "animal": "COW"}]]
    assert (ob.board_fingerprint(_board(tiles), 0, 0)
            == ob.board_fingerprint(_board([list(tiles[0])]), 0, 0))


def test_board_fingerprint_separates_two_boards_holding_the_same_cash():
    """The #207 control's actual defect: day-3 money is a many-to-one residue.
    An off-by-24 book landed on the source's exact 158 with four animals where
    the source had five, so cash alone cannot fingerprint a day-3 state."""
    five = [[{"kind": "PASTURE", "animal": "COW"}] * 5]
    four = [[{"kind": "PASTURE", "animal": "COW"}] * 4 + [None]]
    assert ob.board_fingerprint(_board(five), 0, 0) != ob.board_fingerprint(_board(four), 0, 0)


def test_board_fingerprint_ignores_the_locked_tiles_of_unbought_quadrants():
    """A real replay's board is 75 `"LOCKED"` strings and 25 dicts; a string
    tile must not crash the probe or count as a feature."""
    assert (ob.board_fingerprint(_board([["LOCKED", {"kind": "PLANT"}]]), 0, 0)
            == ob.board_fingerprint(_board([[None, {"kind": "PLANT"}]]), 0, 0))


def test_board_fingerprint_is_empty_past_the_end_of_a_short_episode():
    """A crashed game has no day-3 board; that is empty, not a raise."""
    assert ob.board_fingerprint([], 0, 0) == ()
