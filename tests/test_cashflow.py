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
    # was chosen from), so prices and shed live on the PRIOR step. Day 0: from
    # 3,000, sell 2 melon at 250 (500) and buy 3 melon seed (240) -> closes at
    # 3,260. Day 1: hire twice (1 + 1 -- the ladder resets nightly) and sell
    # 4 wheat at 25 -> closes at 3,358.
    empty = {"farmer": ["PASS"], "hands": [], "market": []}
    sell_buy = {"farmer": ["PASS"], "hands": [],
                "market": [["SELL", "MELON", 2], ["BUY_SEED", "MELON", 3]]}
    hires = {"farmer": ["PASS"], "hands": [], "market": [["HIRE"], ["HIRE"]]}
    sell_wheat = {"farmer": ["PASS"], "hands": [], "market": [["SELL", "WHEAT", 4]]}
    return [
        [_step(3000, empty, prices={"MELON": 250}, shed={"MELON": 2}, day=0, hour=0)],
        [_step(3260, sell_buy, prices={"MELON": 250}, day=0, hour=1)],
        [_step(3260, empty, day=0, hour=2)],
        [_step(3260, empty, prices={"WHEAT": 25}, shed={"WHEAT": 4}, day=1, hour=0)],
        [_step(3258, hires, prices={"WHEAT": 25}, shed={"WHEAT": 4}, day=1, hour=1)],
        [_step(3358, sell_wheat, day=1, hour=2)],
    ]


def test_the_daily_table_splits_spend_revenue_and_closing_money_by_day():
    table = cf.daily_cashflow(_two_days(), player=0)
    assert sorted(table) == [0, 1]
    assert table[0]["spend"] == {"hire": 0, "land": 0, "seed": 240, "animal": 0, "product": 0}
    assert table[0]["revenue"] == {"MELON": 500}
    assert table[0]["close"] == 3260
    assert table[1]["spend"]["hire"] == 2          # 1 + 1: the ladder resets at the new day
    assert table[1]["revenue"] == {"WHEAT": 100}
    assert table[1]["close"] == 3358


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
    table = cf.daily_cashflow(_two_days(), player=0)
    text = cf.format_cashflow(table, days=range(0, 3))
    lines = text.splitlines()
    assert lines[0].startswith("day")
    assert lines[1].startswith("  0") and "3260" in lines[1] and "240" in lines[1] and "500" in lines[1]
    assert lines[2].startswith("  1") and "3358" in lines[2]
    assert lines[3].startswith("  2") and "-" in lines[3]          # absent day: absent, not zero
    assert lines[4].startswith("cumulative") and lines[5].startswith("season")
    assert "500" in lines[4] and "100" in lines[4]                  # melon and wheat revenue over days 0-2
