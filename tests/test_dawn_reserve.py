"""dawn_reserve: herd_first with the cash floor set to tomorrow's wages plus the
herd's feed (#256).

#254's herd_first beat the champion 14/16 and lost the field: the sim clears the
hands every night and re-hires at dawn, and a zero reserve let the herd block
spend every coin before dawn -- 2-5 hands, no feed wheat, head placed 9 -> 3.
This arm keeps back exactly what dawn will need and changes nothing else.
"""

from __future__ import annotations

from strategies import dawn_reserve as dr
from strategies import field_rival as fr
from strategies import hired_hands as hh
from strategies.herd_first import HerdFirstStrategy


def test_the_wage_bill_is_the_benchmarks_own_ladder_summed():
    # 1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144: the sim's fib(hires_today) per hire.
    assert [dr.wage_bill(n) for n in (0, 1, 5, 8, 10, 12)] == [0, 1, 12, 54, 143, 376]
    assert dr.wage_bill(10) == sum(hh.hand_wage(k) for k in range(1, 11))


def test_the_feed_cost_is_the_feed_buffer_at_the_price_the_feed_block_budgets_with():
    # feed_buffer keeps 2 wheat per head (floor 8); the feed block divides its
    # budget by CROPS["WHEAT"]["seed"], so the floor is priced the same way.
    assert [dr.feed_cost(n) for n in (0, 4, 8, 13)] == [80, 80, 160, 260]
    assert dr.feed_cost(13) == fr.feed_buffer(13) * fr.CROPS["WHEAT"]["seed"]


def test_the_reserve_is_tomorrows_wages_plus_todays_feed():
    # Day 5 -> tomorrow's crew is 8 (54) + four head (80); day 7 -> 10 (143) + eight head (160).
    s = dr.DawnReserveStrategy()
    assert s.capital_reserve(5, 4) == 134
    assert s.capital_reserve(7, 8) == 303
    assert s.capital_reserve(29, 13) == dr.wage_bill(s.hire_target(30)) + 260


def test_it_is_a_registered_contender_that_inherits_herd_firsts_order_and_knobs():
    from strategies import REGISTRY, load
    assert "dawn_reserve" in REGISTRY and load("dawn_reserve") is dr.DawnReserveStrategy
    assert issubclass(dr.DawnReserveStrategy, HerdFirstStrategy)
    s, base = dr.DawnReserveStrategy(), HerdFirstStrategy()
    assert s.buy_order() == base.buy_order() == ("hires", "herd", "land", "seed")
    for day in (0, 6, 8, 15):
        assert s.hire_target(day) == base.hire_target(day)
        assert s.herd_target(day) == base.herd_target(day)
    assert s.layout() == base.layout() and s.CAPS == base.CAPS
    assert base.capital_reserve(5, 4) == 0          # herd_first keeps the zero it was rejected on
