"""The one knob #172 Stage 1 turns: never sell a unit below `min_frac` of its
base price; hold the rest. 0.0 must be the champion unchanged (positive
control), and the wrapper must touch nothing but SELL quantities."""

from __future__ import annotations

from kaggisim.economy import MARKET_PARAMS
from kaggisim.strategy import Strategy
from strategies.sell_discipline import SellDiscipline, cap_sells

I0 = MARKET_PARAMS["STRAWBERRY"]["I0"]


def test_min_frac_zero_is_the_identity():
    orders = [["SELL", "STRAWBERRY", 40], ["HIRE"], ["SELL", "WOOL", 12]]
    inv = {"STRAWBERRY": I0 + 500, "WOOL": I0 + 500}
    assert cap_sells(orders, inv, 0.0) == orders


def test_min_frac_one_sells_nothing_into_a_glutted_market():
    orders = [["SELL", "STRAWBERRY", 40]]
    inv = {"STRAWBERRY": I0 + 50}          # above the anchor: every unit clears below base
    assert cap_sells(orders, inv, 1.0) == []


def test_a_partial_cap_keeps_the_units_that_still_clear_the_floor():
    orders = [["SELL", "STRAWBERRY", 400]]
    inv = {"STRAWBERRY": I0}                # at the anchor: price = base, then falls
    got = cap_sells(orders, inv, 0.5)
    assert len(got) == 1 and got[0][:2] == ["SELL", "STRAWBERRY"]
    assert 0 < got[0][2] < 400


def test_non_sell_orders_and_positions_are_untouched():
    orders = [["BUY_SEED", "WHEAT", 5], ["SELL", "STRAWBERRY", 40], ["HIRE"], ["BUY_LAND", "SE"]]
    inv = {"STRAWBERRY": I0 + 50}
    got = cap_sells(orders, inv, 1.0)
    assert got == [["BUY_SEED", "WHEAT", 5], ["HIRE"], ["BUY_LAND", "SE"]]


def test_two_sells_of_one_item_in_a_turn_share_the_cap():
    # The second order sees the inventory the first one will have pushed up.
    orders = [["SELL", "STRAWBERRY", 400], ["SELL", "STRAWBERRY", 400]]
    inv = {"STRAWBERRY": I0}
    alone = cap_sells(orders[:1], inv, 0.5)[0][2]
    both = cap_sells(orders, inv, 0.5)
    assert sum(o[2] for o in both) == alone


def test_missing_inventory_defaults_to_the_anchor_and_unknown_items_pass_through():
    orders = [["SELL", "STRAWBERRY", 3], ["SELL", "COW", 1]]
    got = cap_sells(orders, {}, 0.99)
    assert got[0] == ["SELL", "STRAWBERRY", 1]     # exactly one unit clears >= 0.99*base at I0
    assert got[1] == ["SELL", "COW", 1]            # not a priced product: left alone


class _Inner(Strategy):
    name = "inner"

    def act(self, obs):
        return {"farmer": ["PLANT", "WHEAT"], "hands": [["WATER"]],
                "market": [["SELL", "STRAWBERRY", 40], ["HIRE"]]}


def test_wrapper_caps_only_the_market_and_names_itself():
    obs = {"market": {"inventory": {"STRAWBERRY": I0 + 50}, "prices": {}}}
    s = SellDiscipline(_Inner(), 1.0)
    got = s.act(obs)
    assert got["farmer"] == ["PLANT", "WHEAT"]
    assert got["hands"] == [["WATER"]]
    assert got["market"] == [["HIRE"]]
    assert s.name == "inner@1.0"
    assert s.benchmark is False
