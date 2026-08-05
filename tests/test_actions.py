"""The action-dict builders are tiny, but a typo here silently no-ops a turn."""

from __future__ import annotations

from kaggisim import actions


def test_turn_defaults_to_a_safe_noop():
    assert actions.turn() == {"farmer": ["PASS"], "hands": [], "market": []}


def test_turn_passes_through_its_parts():
    assert actions.turn(
        farmer=["WATER"], hands=[["PASS"]], market=[["SELL", "WHEAT", 1]]
    ) == {"farmer": ["WATER"], "hands": [["PASS"]], "market": [["SELL", "WHEAT", 1]]}


def test_farmer_and_hand_builders():
    assert actions.pass_() == ["PASS"]
    assert actions.move("NORTH") == ["NORTH"]
    assert actions.plant("WHEAT") == ["PLANT", "WHEAT"]
    assert actions.water() == ["WATER"]
    assert actions.harvest() == ["HARVEST"]
    assert actions.fertilize() == ["FERTILIZE"]
    assert actions.feed() == ["FEED"]
    assert actions.care() == ["CARE"]
    assert actions.collect_fertilizer() == ["COLLECT_FERTILIZER"]
    assert actions.dig() == ["DIG"]
    assert actions.pickup("WHEAT", 2) == ["PICKUP", "WHEAT", 2]
    assert actions.drop() == ["DROP"]
    assert actions.place("EGG", 3) == ["PLACE", "EGG", 3]
    assert actions.build_coop() == ["BUILD_COOP"]
    assert actions.build_pasture() == ["BUILD_PASTURE"]


def test_market_order_builders():
    assert actions.buy_seed("WHEAT") == ["BUY_SEED", "WHEAT", 1]
    assert actions.buy_animal("GOOSE") == ["BUY_ANIMAL", "GOOSE", 1]
    assert actions.buy_product("WHEAT", 5) == ["BUY_PRODUCT", "WHEAT", 5]
    assert actions.sell("WHEAT", 3) == ["SELL", "WHEAT", 3]
    assert actions.hire() == ["HIRE"]
    assert actions.buy_land() == ["BUY_LAND"]
    assert actions.MOVES == ("NORTH", "SOUTH", "EAST", "WEST")
