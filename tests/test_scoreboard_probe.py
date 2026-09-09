"""The scoreboard trigger control (#197, Stage 1): the declared constants and the
pure parts -- behind-by-X at the close of day D, the per-game reading off two
census series, and the fire / precision / harm / recall table those readings
tabulate to. The 96 live games are `run`'s and are not exercised here.
"""

from __future__ import annotations

import pytest

from harness import scoreboard_probe as sp
from harness.external_pool import EXTERNAL_ANCHORS


def test_the_declared_constants():
    assert sp.CHAMPION == "third_herder"
    assert sp.SEEDS == tuple(range(864, 880))
    assert sp.DAYS == (12, 15, 18, 21) and sp.MARGINS == (10, 20, 30)
    assert sp.FIRE_BAR == 0.25 and sp.HARM_BAR == 0.20
    assert sp.OPPONENTS == ("third_herder",) + tuple(EXTERNAL_ANCHORS)
    assert sp.RECORD.endswith("harness/scoreboard/trigger_readings.json")


def test_the_seeds_are_spent_not_fresh():
    # Stage 1 is a control on games already paid for: 864-879 are #244's seeds.
    assert set(sp.SEEDS) <= set(range(800, 896))


def test_behind_is_strict_at_the_margin():
    # ours < theirs * (1 - X/100): exactly at the line is NOT behind.
    assert sp.behind(699, 1000, 30) is True
    assert sp.behind(700, 1000, 30) is False
    assert sp.behind(799, 1000, 20) is True
    assert sp.behind(1000, 1000, 10) is False


def _census(money, strawberry=0, head=0):
    return {"money": float(money), "planted": {"STRAWBERRY": strawberry} if strawberry else {},
            "head_placed": head}


def _turns(moneys, strawberry=0, head=0):
    # Two turns a day; the second is the closing board, and it carries the day's money.
    turns = []
    for day, money in enumerate(moneys):
        turns.append((day, _census(money - 1, strawberry, head)))
        turns.append((day, _census(money, strawberry, head)))
    return turns


def test_census_on_day_takes_the_closing_board_and_raises_on_a_missing_day():
    turns = _turns([100, 200, 300])
    assert sp.census_on_day(turns, 1)["money"] == 200
    with pytest.raises(ValueError, match="day 7"):
        sp.census_on_day(turns, 7)


def test_game_reading_records_both_sides_at_each_day_and_the_final_result():
    ours = _turns([1000] * 22, strawberry=22, head=11)
    theirs = _turns([1500] * 21 + [900], strawberry=24, head=14)
    r = sp.game_reading(ours, theirs, "lonespear", 864, days=(12, 21))
    assert r["opponent"] == "lonespear" and r["seed"] == 864
    assert r["at"]["12"] == {"ours": 1000.0, "theirs": 1500.0, "strawberry_gap": 2, "head_gap": 3}
    assert r["final_ours"] == 1000.0 and r["final_theirs"] == 900.0
    assert r["result"] == "win"
    assert sp.game_reading(theirs, ours, "x", 1, days=(12,))["result"] == "loss"
    assert sp.game_reading(ours, ours, "x", 1, days=(12,))["result"] == "tie"


def _reading(opponent, ours_at_15, theirs_at_15, result):
    final = {"win": (2, 1), "loss": (1, 2), "tie": (1, 1)}[result]
    return {"opponent": opponent, "seed": 0,
            "at": {"15": {"ours": ours_at_15, "theirs": theirs_at_15, "strawberry_gap": 0, "head_gap": 0}},
            "final_ours": float(final[0]), "final_theirs": float(final[1]), "result": result}


def _four():
    # Behind by 30% and lost; behind by 30% and won; ahead and lost; ahead and won.
    return [_reading("x", 700, 1000, "loss"), _reading("x", 700, 1000, "win"),
            _reading("x", 1200, 1000, "loss"), _reading("x", 1200, 1000, "win")]


def test_tabulate_counts_fire_precision_harm_and_recall_per_opponent_and_pooled():
    table = sp.tabulate(_four(), days=(15,), margins=(20,))
    row = table[(15, 20)]["x"]
    assert row == {"games": 4, "fired": 2, "wins": 2, "losses": 2,
                   "fire_rate": 0.5, "precision": 0.5, "harm": 0.5, "recall": 0.5}
    assert table[(15, 20)]["pooled"] == row


def test_tabulate_reports_none_where_a_rate_has_no_denominator_and_zero_harm_with_no_wins():
    # Nothing fired -> precision None. No losses -> recall None. No wins -> harm 0.0
    # (there is nothing for the trigger to harm), not None.
    table = sp.tabulate([_reading("x", 1200, 1000, "win")], days=(15,), margins=(20,))
    assert table[(15, 20)]["x"]["precision"] is None and table[(15, 20)]["x"]["recall"] is None
    table = sp.tabulate([_reading("x", 700, 1000, "loss")], days=(15,), margins=(20,))
    assert table[(15, 20)]["x"]["harm"] == 0.0 and table[(15, 20)]["x"]["precision"] == 1.0


def test_actionable_needs_the_fire_bar_and_the_harm_bar_together():
    ok = {"games": 16, "fired": 4, "fire_rate": 0.25, "precision": 1.0, "harm": 0.20, "recall": 1.0}
    assert sp.actionable(ok) is True
    assert sp.actionable(dict(ok, fire_rate=0.24)) is False
    assert sp.actionable(dict(ok, harm=0.21)) is False
    assert sp.actionable(dict(ok, harm=0.0)) is True


def test_format_table_prints_a_block_per_cell_with_the_pooled_line_and_the_marker():
    text = sp.format_table(sp.tabulate(_four(), days=(15,), margins=(20,)))
    assert "day 15" in text and "20%" in text
    lines = text.splitlines()
    assert any(l.startswith("x") for l in lines) and any(l.startswith("pooled") for l in lines)
    starred_readings = [_reading("x", 700, 1000, "loss")] * 3 + [_reading("x", 1200, 1000, "win")]
    starred = sp.format_table(sp.tabulate(starred_readings, days=(15,), margins=(20,)))
    assert "*" in starred and "*" not in text        # fire 75% harm 0, informative; fire 50% harm 50% is not


def test_seat_series_puts_the_champion_first_from_either_seat():
    """Even seeds seat the champion at 0, odd seeds at 1; the seam returns
    (ours, theirs) with ours always the champion. This is the branch a wrong
    swap would invert into a self-consistent, entirely wrong table."""
    s0, s1 = [(0, {"money": 1.0})], [(0, {"money": 2.0})]
    assert sp.champion_seat(864) == 0 and sp.champion_seat(865) == 1
    assert sp.seat_series(864, s0, s1) == (s0, s1)
    assert sp.seat_series(865, s0, s1) == (s1, s0)


def test_game_reading_records_the_seat_and_the_seat_control_wants_both():
    """Positive control for the seating: a run over an even and an odd seed must
    show both seats in the record, or the alternation never happened."""
    ours = _turns([1000] * 22)
    theirs = _turns([900] * 22)
    r = sp.game_reading(ours, theirs, "x", 865, days=(12,))
    assert r["seat"] == 1
    readings = [sp.game_reading(ours, theirs, "x", s, days=(12,)) for s in (864, 865)]
    assert sp.seats_alternated(readings) is True
    assert sp.seats_alternated(readings[:1]) is False


def test_rows_carry_win_and_loss_counts():
    row = sp.tabulate(_four(), days=(15,), margins=(20,))[(15, 20)]["x"]
    assert row["wins"] == 2 and row["losses"] == 2


def test_the_star_needs_both_outcomes_in_the_row():
    """Against an opponent we never beat, harm is 0 by construction and every cell
    would be starred; a trigger is only informative where it could have fired on
    a win. `actionable` is the declared bar; `informative` is the extra gate the
    star uses, and the pooled row across six opponents always has both outcomes."""
    all_losses = [_reading("x", 700, 1000, "loss")] * 4
    row = sp.tabulate(all_losses, days=(15,), margins=(20,))[(15, 20)]["x"]
    assert sp.actionable(row) is True and sp.informative(row) is False
    assert "*" not in sp.format_table(sp.tabulate(all_losses, days=(15,), margins=(20,)))
    mixed = all_losses + [_reading("x", 1200, 1000, "win")]
    assert "*" in sp.format_table(sp.tabulate(mixed, days=(15,), margins=(20,)))


def test_format_asymmetry_prints_the_median_gaps_per_opponent_and_day():
    readings = [dict(_reading("x", 1, 1, "win"), at={"15": {"ours": 1, "theirs": 1, "strawberry_gap": g, "head_gap": h}})
                for g, h in ((2, 3), (4, 1), (6, 5))]
    text = sp.format_asymmetry(readings, days=(15,))
    assert "x" in text and "4" in text and "3" in text   # medians: strawberry 4, head 3
