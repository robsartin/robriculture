"""Per-day cash flow of one side of one game (#260).

`episode_analysis.decompose` prices every order against the state it was
chosen from and reports season totals; this is the same accounting per day,
built on the same helpers so the two cannot drift. The positive control is
that the days sum to the season.
"""

from __future__ import annotations

from harness import cashflow as cf
from harness import episode_analysis as ea


def _step(money, action, prices=None, shed=None, day=0, hour=0):
    """One player's slot in a step -- the shape `env.steps` and a replay share."""
    return {
        "action": action,
        "observation": {
            "day": day, "hour": hour, "player": 0,
            "farms": [{"money": money, "tiles": [], "hands": [], "unlocked_quadrants": ["NW"]}],
            "market": {"prices": prices or {}, "inventory": {}},
            "private": {"shed": shed or {}, "seeds": {}, "inventories": []},
        },
    }


def _two_days():
    # An action at index t is paired with the observation at t-1 (the state it
    # was chosen from); the observation at t is the state that action produced,
    # and the sim stamps the state after a day's LAST turn with the next day.
    # Day 0 (turns paired with day-0 states): hire once (1), sell 2 melon at
    # 250 (500), buy 3 melon seed (240); the last turn of day 0 sells 1 wheat
    # (25) and its resulting state is stamped day 1 with money 3,284 -- that is
    # day 0's closing board. Day 1: hire twice (1 + 1 -- the ladder resets) and
    # sell 4 wheat at 25 (100); closes at 3,382.
    pass_ = ["PASS"]
    def act(market): return {"farmer": pass_, "hands": [], "market": market}
    return [
        [_step(3000, act([]), prices={"MELON": 250}, shed={"MELON": 2}, day=0, hour=0)],
        [_step(2999, act([["HIRE"]]), prices={"MELON": 250}, shed={"MELON": 2}, day=0, hour=1)],
        [_step(3259, act([["SELL", "MELON", 2], ["BUY_SEED", "MELON", 3]]),
               prices={"WHEAT": 25}, shed={"WHEAT": 1}, day=0, hour=2)],
        [_step(3284, act([["SELL", "WHEAT", 1]]), prices={"WHEAT": 25}, shed={"WHEAT": 4}, day=1, hour=0)],
        [_step(3282, act([["HIRE"], ["HIRE"]]), prices={"WHEAT": 25}, shed={"WHEAT": 4}, day=1, hour=1)],
        [_step(3382, act([["SELL", "WHEAT", 4]]), day=1, hour=2)],
    ]


def test_the_daily_table_splits_spend_revenue_and_closing_money_by_day():
    """Each order goes to the day of the state it was chosen from, and each
    day's close is the state its last turn produced -- even though the sim
    stamps that state with the next day. The wheat sold on day 0's last turn
    is day-0 revenue and moves day-0's close, not day-1's."""
    table = cf.daily_cashflow(_two_days(), player=0)
    assert sorted(table) == [0, 1]
    assert table[0]["spend"] == {"hire": 1, "land": 0, "seed": 240, "animal": 0, "product": 0}
    assert table[0]["revenue"] == {"MELON": 500, "WHEAT": 25}
    assert table[0]["close"] == 3284
    assert table[1]["spend"]["hire"] == 2          # 1 + 1, not 2 + 3: the ladder resets nightly
    assert table[1]["revenue"] == {"WHEAT": 100}
    assert table[1]["close"] == 3382


def test_each_days_close_moves_by_that_days_revenue_minus_spend():
    """The per-day residual: close(D) - close(D-1) - (revenue - spend). Zero
    here because every price is exact; on a live game it is decompose's
    estimation error, day by day -- the control that catches a day boundary
    keyed to the wrong side."""
    table = cf.daily_cashflow(_two_days(), player=0)
    assert cf.daily_residuals(table, start_money=3000) == {0: 0, 1: 0}


def test_the_days_sum_to_the_season_decomposition():
    """The positive control: summed over every day, the table must equal
    `decompose`'s spend and revenue on the same steps, or the daily view has
    drifted from the season view."""
    steps = _two_days()
    totals = cf.season_totals(cf.daily_cashflow(steps, player=0))
    season = ea.decompose(steps, player=0)
    assert totals["spend"] == season["spend"]
    assert totals["revenue"] == season["revenue"]


def test_format_prints_one_line_per_requested_day_then_cumulative_and_season():
    """The table renders as fixed-width columns: one line per requested day
    (absent days print `-`), then `cumulative` over those days and `season`
    over every day in the table; the table also carries a residual column."""
    table = cf.daily_cashflow(_two_days(), player=0)
    text = cf.format_cashflow(table, days=range(0, 3), start_money=3000)
    lines = text.splitlines()
    assert lines[0].startswith("day")
    assert "residual" in lines[0]
    assert lines[1].startswith("  0") and "3284" in lines[1] and "240" in lines[1] and "500" in lines[1]
    assert lines[2].startswith("  1") and "3382" in lines[2]
    assert lines[3].startswith("  2") and "-" in lines[3]          # absent day: absent, not zero
    assert lines[4].startswith("cumulative") and lines[5].startswith("season")
    assert "500" in lines[4] and "125" in lines[4]                  # melon and wheat revenue over days 0-2
