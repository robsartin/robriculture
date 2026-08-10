"""Unit tests for the ranch_adaptive experiment (issue #52, ADR-0007).

`ranch_adaptive` = the champion `ranch_hands` + a **price-adaptive sell rule**.
The 1v1 ladder shares one melon market, and melon is not consumed by any town
shop, so an opponent that floods melon (see `strategies/spoiler.py`) can crash
the price `ranch_hands` leans on. This variant reads the live melon price and,
when it is depressed, **throttles melon selling** (holds it out of the trough)
and leans on the next-best markets (wheat / milk / wool) instead; when melon's
price is healthy it is byte-for-byte the champion, and in the end-game
liquidation window it dumps everything regardless (nothing may be stranded past
the buzzer).

These pin the pure sell-rule helpers that carry the one variable — `melon_depressed`
(the price signal) and `adaptive_sell_orders` (throttle + diversify) — plus the
`act()` shape. The melon / livestock / hiring machinery is `ranch_hands`' own and
is covered by its suite; the full-game no-crash guard lives in test_no_crash.py.
"""

from __future__ import annotations

from strategies import ranch_adaptive as ra
from strategies import ranch_hands as rh


# --- melon_depressed: the price signal that gates the adaptive rule ----------

def test_melon_not_depressed_at_base_price():
    # At (or above) the base price the melon market is healthy.
    assert not ra.melon_depressed({"MELON": ra.MELON_BASE})


def test_melon_depressed_when_price_far_below_base():
    # A crashed melon market (a spoiler flooding it) trips the signal.
    assert ra.melon_depressed({"MELON": 100})


def test_missing_price_is_treated_as_healthy():
    # No market price yet (game start / empty obs) -> behave like the champion.
    assert not ra.melon_depressed({})


def test_depressed_boundary_is_the_ratio():
    # The threshold is DEPRESSED_RATIO of the base price, and nothing else.
    thresh = ra.MELON_BASE * ra.DEPRESSED_RATIO
    assert ra.melon_depressed({"MELON": thresh - 1})
    assert not ra.melon_depressed({"MELON": thresh + 1})


# --- adaptive_sell_orders: healthy == champion; depressed == throttle+diversify

HEALTHY = {"MELON": ra.MELON_BASE}
DEPRESSED = {"MELON": 80}


def test_identical_to_ranch_hands_when_price_healthy():
    # Whole point: no behaviour change while melon's market is healthy.
    shed = {"MELON": 12, "MILK": 3, "WOOL": 2, "WHEAT": 9}
    assert ra.adaptive_sell_orders(shed, HEALTHY) == rh._sell_orders_keep_feed(shed)


def test_throttles_melon_when_price_depressed():
    # Melon selling is capped at the throttle, not dumped into the trough.
    shed = {"MELON": 20}
    orders = ra.adaptive_sell_orders(shed, DEPRESSED)
    melon = [o for o in orders if o[1] == "MELON"]
    assert melon == [["SELL", "MELON", ra.MELON_THROTTLE]]


def test_diversifies_into_next_best_markets_when_depressed():
    # With melon crashed, the non-melon products still clear in full, so the sell
    # mix tilts toward wheat/milk/wool -- income shifts off the crashed market.
    shed = {"MELON": 20, "MILK": 4, "WOOL": 3, "WHEAT": 9}
    orders = ra.adaptive_sell_orders(shed, DEPRESSED)
    assert ["SELL", "MILK", 4] in orders
    assert ["SELL", "WOOL", 3] in orders
    assert ["SELL", "WHEAT", 9 - rh.WHEAT_BUFFER] in orders
    melon_units = sum(o[2] for o in orders if o[1] == "MELON")
    nonmelon_units = sum(o[2] for o in orders if o[1] != "MELON")
    # The champion would dump all 20 melons (melon-dominant); the adaptive rule
    # holds melon back and tilts the mix to the next-best markets.
    assert melon_units < 20
    assert melon_units < nonmelon_units


def test_endgame_liquidates_melon_even_when_depressed():
    # In the final liquidation window melon cannot be held past the buzzer, so it
    # is dumped in full regardless of price -- adaptive == champion there.
    shed = {"MELON": 20, "WHEAT": 9}
    assert (
        ra.adaptive_sell_orders(shed, DEPRESSED, endgame=True)
        == rh._sell_orders_keep_feed(shed)
    )


def test_wheat_feed_buffer_still_respected_when_depressed():
    # The livestock feed buffer is sacred in every regime.
    shed = {"WHEAT": rh.WHEAT_BUFFER}
    orders = ra.adaptive_sell_orders(shed, DEPRESSED)
    assert not any(o[1] == "WHEAT" for o in orders)


# --- act(): end-to-end shape; healthy price reproduces the champion's market ---

def _empty_board():
    return [[None for _ in range(10)] for _ in range(10)]


def _obs(hour=0, day=5, money=3000, shed=None, prices=None, hands=None):
    n_inv = 1 + len(hands or [])
    return {
        "player": 0,
        "day": day,
        "hour": hour,
        "farms": [
            {"money": money, "tiles": _empty_board(), "farmer": [4, 4], "hands": hands or []},
            {"money": money, "tiles": _empty_board(), "farmer": [4, 4], "hands": []},
        ],
        "market": {"inventory": {}, "prices": prices or {}},
        "town": {"unlocked_shops": []},
        "private": {"shed": shed or {}, "seeds": {}, "inventories": [{} for _ in range(n_inv)]},
    }


def test_strategy_name_is_ranch_adaptive():
    assert ra.RanchAdaptiveStrategy.name == "ranch_adaptive"


def test_act_matches_champion_market_when_price_healthy():
    obs = _obs(hour=5, shed={"MELON": 12, "WHEAT": 10}, prices={"MELON": ra.MELON_BASE})
    action = ra.RanchAdaptiveStrategy().act(obs)
    assert ["SELL", "MELON", 12] in action["market"]
    assert ["SELL", "WHEAT", 10 - rh.WHEAT_BUFFER] in action["market"]


def test_act_throttles_melon_when_market_is_crashed_midgame():
    # Mid-game (not the liquidation window) with a crashed price -> throttle.
    obs = _obs(hour=5, day=12, shed={"MELON": 12, "WHEAT": 10}, prices={"MELON": 80})
    action = ra.RanchAdaptiveStrategy().act(obs)
    melon = [o for o in action["market"] if o[0] == "SELL" and o[1] == "MELON"]
    assert melon == [["SELL", "MELON", ra.MELON_THROTTLE]]


def test_act_returns_valid_shape_and_respects_order_cap():
    action = ra.RanchAdaptiveStrategy().act(_obs(hour=0))
    assert isinstance(action["farmer"], list) and action["farmer"]
    assert len(action["market"]) <= 10
