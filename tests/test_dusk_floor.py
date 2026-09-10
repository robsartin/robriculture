"""dusk_floor: herd_first with a turn-wide spend floor (#258).

#254's herd_first beat the champion 14/16 and lost the field because a zero
reserve fires the crew at dusk; #256 put dawn's wages and feed behind the herd's
own reserve and VOIDed on the same bar, because land and seed spend after the
herd under herd_first's order. This arm puts the same quantity -- priced at the
market and reserving only the shortfall -- behind a floor that land, seed and
the herd all respect, and changes nothing else.
"""

from __future__ import annotations

from kaggisim import economy
from strategies import dusk_floor as df
from strategies import field_rival as fr
from strategies.dawn_reserve import wage_bill
from strategies.herd_first import HerdFirstStrategy


def test_the_feed_shortfall_is_priced_at_the_market_and_only_for_what_the_shed_lacks():
    # 8 head keep 16 wheat; 10 in the shed leaves 6 to buy at the day's price.
    assert df.WHEAT_BASE == economy.MARKET_PARAMS["WHEAT"]["base"] == 25
    assert df.feed_shortfall_cost(8, {"WHEAT": 10}, {"WHEAT": 30}) == 180
    assert df.feed_shortfall_cost(8, {"WHEAT": 20}, {"WHEAT": 30}) == 0
    assert df.feed_shortfall_cost(8, {}, {}) == 16 * 25          # base price when the market is unread
    assert df.feed_shortfall_cost(0, {}, {"WHEAT": 25}) == fr.feed_buffer(0) * 25   # FEED_CARRY floor


def test_the_floor_is_tomorrows_wages_plus_todays_feed_shortfall():
    # Day 5 -> tomorrow's crew is 8 (54) + four head with an empty shed (8 x 25 = 200).
    s = df.DuskFloorStrategy()
    assert s.spend_floor(5, 4, {}, {"WHEAT": 25}) == 254
    assert s.spend_floor(7, 8, {"WHEAT": 16}, {"WHEAT": 40}) == 143       # shed full: wages only
    assert s.spend_floor() == wage_bill(s.hire_target(0)) + 8 * 25           # the bare call answers


def test_it_is_a_registered_contender_that_inherits_herd_firsts_order_and_knobs():
    from strategies import REGISTRY, load
    assert "dusk_floor" in REGISTRY and load("dusk_floor") is df.DuskFloorStrategy
    assert issubclass(df.DuskFloorStrategy, HerdFirstStrategy)
    s, base = df.DuskFloorStrategy(), HerdFirstStrategy()
    assert s.buy_order() == base.buy_order() == ("hires", "herd", "land", "seed")
    assert s.capital_reserve(5, 4) == base.capital_reserve(5, 4) == 0      # the herd's own reserve stays 0
    for day in (0, 6, 8, 15):
        assert s.hire_target(day) == base.hire_target(day) and s.herd_target(day) == base.herd_target(day)
    assert s.layout() == base.layout() and s.CAPS == base.CAPS
    assert base.spend_floor(5, 4, {}, {}) is None                          # herd_first has no floor
