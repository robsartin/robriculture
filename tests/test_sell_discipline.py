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


class _ResettableInner(Strategy):
    name = "resettable-inner"

    def __init__(self):
        self.was_reset = False

    def act(self, obs):
        return {"farmer": ["PASS"], "hands": [], "market": []}

    def reset(self):
        self.was_reset = True


def test_reset_is_forwarded_to_the_inner_strategy():
    inner = _ResettableInner()
    s = SellDiscipline(inner, 0.5)
    s.reset()
    assert inner.was_reset is True


def test_min_frac_zero_is_the_champion_to_the_value_on_a_seeded_game():
    # The spec's positive control #1: the wrapper at 0.0 must be the bare
    # champion on a real game, both seats' rewards equal to the value. Pins
    # that cap_sells rebuilds ["SELL", item, n] without losing anything.
    from kaggle_environments import make
    from kaggisim.strategy import make_agent
    from strategies import load
    champion, opponent = load("dense_farm"), load("meta_bot")

    def rewards(ours):
        env = make("kaggriculture", configuration={"episodeSteps": 240, "seed": 3})
        env.run([make_agent(ours), make_agent(opponent())])
        return [s.reward or 0 for s in env.steps[-1]]

    bare = rewards(champion())
    wrapped = rewards(SellDiscipline(champion(), 0.0))
    assert bare[0] > 0, "POSITIVE CONTROL: no money moved, test proves nothing"
    assert wrapped == bare
