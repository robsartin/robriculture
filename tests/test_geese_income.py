"""Unit tests for the geese_income experiment (issue #7, ADR-0007).

The single technique under test is a geese/egg income line layered on top of
`greedy_horizon`'s melon loop. These exercise the *pure decision helpers* — the
cash threshold to stand up the line, the daily feed requirement (the escape-risk
guard), egg collection, movement, and the market orders that buy the goose and
keep it fed — without spinning up a full 720-turn game. The full-game no-crash
guard lives in test_no_crash.py (auto-included via the REGISTRY).
"""

from __future__ import annotations

from strategies import geese_income as gi


# --- tile fixtures -------------------------------------------------------

def _goose(fed_today=False, yield_units=0, consecutive_unfed=0):
    return {
        "kind": "COOP",
        "animal": "GOOSE",
        "placed_day": 0,
        "yield_units": yield_units,
        "consecutive_unfed": consecutive_unfed,
        "fed_today": fed_today,
    }


def _empty_coop():
    return {"kind": "COOP"}


def _weed():
    return {"kind": "WEED"}


# --- movement ------------------------------------------------------------

def test_step_toward_moves_west_then_returns_none_when_arrived():
    # HOME (4,4) -> COOP (3,4): a single WEST step, then nothing left to do.
    assert gi.step_toward(gi.HOME, gi.COOP) == ["WEST"]
    assert gi.step_toward(gi.COOP, gi.COOP) is None


def test_step_toward_returns_east_back_home():
    assert gi.step_toward(gi.COOP, gi.HOME) == ["EAST"]


def test_coop_is_a_free_unlocked_tile_next_to_home():
    # Both live in the NW quadrant (x<5, y<5) and are orthogonally adjacent.
    assert gi.COOP != gi.HOME
    assert abs(gi.COOP[0] - gi.HOME[0]) + abs(gi.COOP[1] - gi.HOME[1]) == 1
    assert gi.COOP[0] < 5 and gi.COOP[1] < 5


# --- coop / goose classification ----------------------------------------

def test_coop_status_classifies_every_tile_kind():
    assert gi.coop_status(None) == "NONE"
    assert gi.coop_status("LOCKED") == "OTHER"
    assert gi.coop_status(_weed()) == "WEED"
    assert gi.coop_status(_empty_coop()) == "COOP_EMPTY"
    assert gi.coop_status(_goose()) == "GOOSE"


def test_is_goose_only_true_for_a_placed_goose():
    assert gi.is_goose(_goose()) is True
    assert gi.is_goose(_empty_coop()) is False
    assert gi.is_goose(None) is False


def test_have_goose_spots_it_in_shed_or_hand_or_on_tile():
    assert gi.have_goose(None, {"GOOSE": 1}, {}) is True
    assert gi.have_goose(None, {}, {"GOOSE": 1}) is True
    assert gi.have_goose(_goose(), {}, {}) is True
    assert gi.have_goose(None, {}, {}) is False


# --- the cash threshold to stand up the line ----------------------------

def test_should_start_when_cash_clears_threshold_early():
    assert gi.should_start_geese(gi.GEESE_CASH_THRESHOLD, 0, None) is True


def test_should_not_start_when_broke():
    assert gi.should_start_geese(gi.GEESE_CASH_THRESHOLD - 1, 0, None) is False


def test_should_not_start_once_a_goose_is_already_placed():
    # The line is stood up exactly once; a placed goose ends the setup phase.
    assert gi.should_start_geese(10_000, 0, _goose()) is False


def test_should_not_start_too_late_to_recoup():
    assert gi.should_start_geese(10_000, gi.GEESE_START_CUTOFF_DAY + 1, None) is False


# --- feeding: the escape-risk guard -------------------------------------

def test_need_feed_true_for_an_unfed_goose_mid_season():
    assert gi.need_feed(_goose(fed_today=False), 5) is True


def test_no_need_to_feed_when_already_fed_today():
    assert gi.need_feed(_goose(fed_today=True), 5) is False


def test_no_feed_without_a_goose():
    assert gi.need_feed(_empty_coop(), 5) is False
    assert gi.need_feed(None, 5) is False


def test_stop_feeding_on_the_final_day_the_egg_can_never_sell():
    # An egg produced from the last day's feed never has a market turn to sell,
    # so feeding then is pure wasted wheat.
    assert gi.need_feed(_goose(fed_today=False), gi.LAST_FEED_DAY) is True
    assert gi.need_feed(_goose(fed_today=False), gi.LAST_FEED_DAY + 1) is False


# --- egg collection ------------------------------------------------------

def test_eggs_ready_only_when_a_goose_holds_yield():
    assert gi.eggs_ready(_goose(yield_units=1)) is True
    assert gi.eggs_ready(_goose(yield_units=0)) is False
    assert gi.eggs_ready(_empty_coop()) is False


# --- selling: keep the feeding wheat, sell everything else ---------------

def test_sell_orders_keeps_wheat_but_sells_melon_and_eggs():
    shed = {"MELON": 6, "EGG": 3, "WHEAT": 2}
    orders = gi.sell_orders(shed)
    assert ["SELL", "EGG", 3] in orders
    assert ["SELL", "MELON", 6] in orders
    # WHEAT is feeding stock — never auto-sold out from under the geese.
    assert all(o[1] != "WHEAT" for o in orders)


def test_sell_orders_is_deterministic_and_skips_empties():
    assert gi.sell_orders({"EGG": 0, "MELON": 2}) == [["SELL", "MELON", 2]]


# --- market orders: buy the goose, keep wheat stocked -------------------

def test_market_buys_one_goose_when_starting_the_line():
    orders = gi.goose_market_orders(3000, 0, None, {}, {})
    assert ["BUY_ANIMAL", "GOOSE", 1] in orders


def test_market_does_not_rebuy_a_goose_already_in_flight():
    # Goose sitting in the shed waiting to be placed: don't buy a second one.
    orders = gi.goose_market_orders(3000, 0, None, {"GOOSE": 1}, {})
    assert ["BUY_ANIMAL", "GOOSE", 1] not in orders


def test_wheat_target_covers_remaining_feed_days_plus_margin():
    # Feeds run day..LAST_FEED_DAY inclusive; front-load the whole remaining need.
    assert gi.wheat_target(0) == (gi.LAST_FEED_DAY - 0 + 1) + gi.WHEAT_MARGIN
    assert gi.wheat_target(gi.LAST_FEED_DAY) == 1 + gi.WHEAT_MARGIN
    # Past the last feed day there is nothing left to feed.
    assert gi.wheat_target(gi.LAST_FEED_DAY + 1) == 0


def test_market_front_loads_the_seasons_wheat_when_starting():
    orders = gi.goose_market_orders(3000, 0, None, {"GOOSE": 1}, {})
    buys = [o for o in orders if o[0] == "BUY_PRODUCT" and o[1] == "WHEAT"]
    assert buys == [["BUY_PRODUCT", "WHEAT", gi.wheat_target(0)]]


def test_market_does_not_overbuy_wheat_when_the_target_is_met():
    placed = _goose(fed_today=True)
    shed = {"WHEAT": gi.wheat_target(5)}
    orders = gi.goose_market_orders(3000, 5, placed, shed, {})
    assert not any(o[0] == "BUY_PRODUCT" for o in orders)


def test_market_is_quiet_before_the_cash_threshold():
    assert gi.goose_market_orders(gi.GEESE_CASH_THRESHOLD - 1, 0, None, {}, {}) == []


# --- the goose chore choreography (feed first, then eggs, then setup) ----

def test_goose_action_feeds_when_armed_and_standing_on_the_coop():
    hungry = _goose(fed_today=False)
    assert gi._goose_action(gi.COOP, hungry, 5, 3000, {}, {"WHEAT": 1}) == ["FEED"]


def test_goose_action_fetches_wheat_from_the_shed_before_feeding():
    hungry = _goose(fed_today=False)
    # Unarmed at home: pick a wheat up; then head to the coop to feed.
    assert gi._goose_action(gi.HOME, hungry, 5, 3000, {"WHEAT": 3}, {}) == ["PICKUP", "WHEAT", 1]
    assert gi._goose_action(gi.COOP, hungry, 5, 3000, {"WHEAT": 3}, {}) == gi.step_toward(gi.COOP, gi.HOME)


def test_goose_action_waits_when_no_wheat_anywhere():
    # No wheat in shed or hand (a buy is in flight) -> do nothing, never a bad action.
    hungry = _goose(fed_today=False)
    assert gi._goose_action(gi.HOME, hungry, 5, 3000, {}, {}) is None


def test_goose_action_collects_eggs_once_fed():
    laying = _goose(fed_today=True, yield_units=2)
    assert gi._goose_action(gi.COOP, laying, 5, 3000, {}, {}) == ["HARVEST"]


def test_goose_action_builds_then_places_to_stand_up_the_line():
    # Empty land + cash -> build the coop.
    assert gi._goose_action(gi.COOP, None, 0, 3000, {}, {}) == ["BUILD_COOP"]
    # A weed on the spot -> clear it first.
    assert gi._goose_action(gi.COOP, _weed(), 0, 3000, {}, {}) == ["DIG"]
    # Empty coop with a goose in the shed -> fetch it, then place it.
    assert gi._goose_action(gi.HOME, _empty_coop(), 0, 3000, {"GOOSE": 1}, {}) == ["PICKUP", "GOOSE", 1]
    assert gi._goose_action(gi.COOP, _empty_coop(), 0, 3000, {}, {"GOOSE": 1}) == ["PLACE", "GOOSE", 1]


def test_goose_action_idle_when_nothing_to_do():
    assert gi._goose_action(gi.HOME, None, 0, 10, {}, {}) is None  # broke: never start
