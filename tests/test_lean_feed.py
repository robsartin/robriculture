"""lean_feed: herd_first with feed sized to the herd (#262).

#260 measured the schedule contenders' cash flow: every one ends day 0 at 15,
395-664 of it on feed -- three herders filling eight-wheat pockets plus a
sixteen-wheat buffer for four head that eat four a day -- and days 1-5 the
herd's income goes on refilling them. This arm carries one day's feed per
trip and keeps one feeding in the shed, and changes nothing else.
"""

from __future__ import annotations

from strategies import field_rival as fr
from strategies import lean_feed as lf
from strategies.herd_first import HerdFirstStrategy


def test_the_carry_is_one_days_feed_for_the_herders_own_tiles():
    # Head split across herders, rounded up; never zero.
    assert lf.carry_for(0, 2) == 1 and lf.carry_for(1, 3) == 1
    assert lf.carry_for(4, 2) == 2 and lf.carry_for(4, 3) == 2
    assert lf.carry_for(13, 3) == 5 and lf.carry_for(14, 3) == 5
    assert lf.carry_for(14, 2) == 7 < fr.FEED_CARRY


def test_the_stock_is_one_feeding_never_zero():
    assert lf.stock_for(0) == 1 and lf.stock_for(4) == 4 and lf.stock_for(13) == 13
    assert lf.stock_for(4) < fr.feed_buffer(4) == 8          # the frozen buffer is max(8, 2 x head)


def test_the_hooks_answer_with_the_declared_numbers_and_the_bare_call_answers():
    s = lf.LeanFeedStrategy()
    assert s.feed_carry(4, 3) == 2 and s.feed_stock(4) == 4
    assert s.feed_carry() == lf.carry_for(0, len(fr.LIVESTOCK_WORKERS)) == 1
    assert s.feed_stock() == 1


def test_it_is_a_registered_contender_that_inherits_herd_first_and_nothing_else_moves():
    from strategies import REGISTRY, load
    assert "lean_feed" in REGISTRY and load("lean_feed") is lf.LeanFeedStrategy
    assert issubclass(lf.LeanFeedStrategy, HerdFirstStrategy)
    s, base = lf.LeanFeedStrategy(), HerdFirstStrategy()
    assert s.buy_order() == base.buy_order() == ("hires", "herd", "land", "seed")
    assert s.capital_reserve(5, 4) == base.capital_reserve(5, 4) == 0
    assert s.spend_floor(5, 4, {}, {}) is None and base.spend_floor(5, 4, {}, {}) is None
    for day in (0, 6, 8, 15):
        assert s.hire_target(day) == base.hire_target(day) and s.herd_target(day) == base.herd_target(day)
    assert s.layout() == base.layout() and s.CAPS == base.CAPS
    assert base.feed_carry(4, 3) is None and base.feed_stock(4) is None   # herd_first keeps the frozen feed
