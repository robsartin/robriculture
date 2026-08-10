"""Unit tests for the ranch_hands integration (issue n/a — integration of #45 + #46).

`ranch_hands` is the champion `livestock_hand` (#45) with its tail catch-crop
switched from CARROT to WHEAT (the #46 shop-demand pick) and the #46 feed-buffer
sell rule applied to its two-animal (cow + sheep) cluster. These exercise the
*pure decision helpers* — the forced-wheat catch crop, the feed-buffer sell rule,
the melon/livestock plot assignment, the animal state machine, and the livestock
hand's dawn wheat top-up — so the integration is validated without spinning up a
full 720-turn game. The full-game no-crash guard lives in test_no_crash.py.
"""

from __future__ import annotations

from strategies import ranch_hands as rh


# --- choose_catch_crop: forced to WHEAT (never carrot), horizon-gated ---

def test_catch_crop_is_wheat_early():
    assert rh.choose_catch_crop(0) == "WHEAT"


def test_catch_crop_is_wheat_in_the_tail_while_it_can_mature():
    # Wheat matures in 4 days; day 22 in a 30-day season (final day 29) still fits.
    assert rh.choose_catch_crop(22) == "WHEAT"


def test_catch_crop_none_once_wheat_cannot_fully_mature():
    # day 27 + 4 = 31 > final day 29: no wheat can fill out, so plant nothing.
    assert rh.choose_catch_crop(27) is None


def test_catch_crop_is_never_carrot():
    assert all(rh.choose_catch_crop(d) in ("WHEAT", None) for d in range(0, 30))


# --- _sell_orders_keep_feed: sell crop-wheat only down to the feed buffer ---

def test_sells_wheat_surplus_above_the_feed_buffer():
    orders = rh._sell_orders_keep_feed({"WHEAT": 10})
    assert orders == [["SELL", "WHEAT", 10 - rh.WHEAT_BUFFER]]


def test_never_sells_wheat_below_the_feed_buffer():
    # At or under the buffer, no wheat is sold — the cluster's feed is untouchable.
    assert rh._sell_orders_keep_feed({"WHEAT": rh.WHEAT_BUFFER}) == []
    assert rh._sell_orders_keep_feed({"WHEAT": 1}) == []


def test_products_other_than_wheat_sell_in_full_and_first():
    # Melon/milk/wool clear fully; the price-sensitive melon SELL leads the list.
    orders = rh._sell_orders_keep_feed({"MELON": 12, "MILK": 3, "WHEAT": 7})
    assert ["SELL", "MELON", 12] in orders
    assert ["SELL", "MILK", 3] in orders
    assert ["SELL", "WHEAT", 7 - rh.WHEAT_BUFFER] in orders
    assert orders[-1][1] == "WHEAT"  # wheat surplus sits behind the products


def test_feed_buffer_feeds_two_animals():
    # The two-animal cluster needs a larger held buffer than a single cow; the
    # carry per trip still fits inside it.
    assert rh.WHEAT_BUFFER >= 2 * rh.WHEAT_CARRY - 2  # covers both animals a trip
    assert rh.WHEAT_BUFFER > 2  # strictly larger than dairy_hands' single-cow 2


# --- melon_plot_for: worker 1 is the livestock hand, others farm melon+wheat ---

def test_farmer_keeps_the_first_melon_plot():
    assert rh.melon_plot_for(0) == rh.MELON_PLOTS[0]


def test_worker_one_is_the_livestock_hand_with_no_melon_plot():
    assert rh.melon_plot_for(1) is None


def test_remaining_workers_take_the_shifted_melon_plots():
    assert rh.melon_plot_for(2) == rh.MELON_PLOTS[1]
    assert rh.melon_plot_for(9) == rh.MELON_PLOTS[8]


def test_indices_past_the_crew_clamp_to_the_last_plot():
    assert rh.melon_plot_for(20) == rh.MELON_PLOTS[-1]


def test_melon_crew_drops_the_weakest_tile():
    # Nine melon tiles (the champion's ten minus the last), plus one livestock hand.
    assert len(rh.MELON_PLOTS) == 9
    assert rh.COW_TILE not in rh.MELON_PLOTS
    assert rh.SHEEP_TILE not in rh.MELON_PLOTS


# --- animal_chore: the per-animal state machine (pasture -> place -> maintain) ---

def _empty_board():
    return [[None for _ in range(10)] for _ in range(10)]


def test_builds_pasture_when_standing_on_empty_cow_tile():
    board = _empty_board()
    action = rh.animal_chore("COW", rh.COW_TILE, board, {}, {})
    assert action == ["BUILD_PASTURE"]


def test_places_animal_when_held_and_on_tile():
    board = _empty_board()
    x, y = rh.COW_TILE
    board[y][x] = None
    action = rh.animal_chore("COW", rh.COW_TILE, board, {"COW": 1}, {})
    assert action == ["PLACE", "COW"]


def test_harvests_a_yielding_animal():
    board = _empty_board()
    x, y = rh.SHEEP_TILE
    board[y][x] = {"animal": "SHEEP", "yield_units": 2}
    action = rh.animal_chore("SHEEP", rh.SHEEP_TILE, board, {}, {})
    assert action == ["HARVEST"]


def test_feeds_a_hungry_animal_from_carried_wheat():
    board = _empty_board()
    x, y = rh.COW_TILE
    board[y][x] = {"animal": "COW", "yield_units": 0, "fed_today": False}
    action = rh.animal_chore("COW", rh.COW_TILE, board, {"WHEAT": 1}, {})
    assert action == ["FEED"]


def test_walks_to_shed_for_wheat_when_hungry_and_empty_handed():
    board = _empty_board()
    x, y = rh.COW_TILE
    board[y][x] = {"animal": "COW", "yield_units": 0, "fed_today": False}
    action = rh.animal_chore("COW", rh.COW_TILE, board, {}, {"WHEAT": 5})
    # Standing on the cow tile with no carried wheat but wheat in the shed:
    # step toward the shed (not FEED/PASS).
    assert action in (["EAST"], ["SOUTH"], ["NORTH"], ["WEST"])


def test_fully_tended_animal_wants_nothing():
    board = _empty_board()
    x, y = rh.COW_TILE
    board[y][x] = {
        "animal": "COW", "yield_units": 0, "fed_today": True, "cared_today": True,
    }
    assert rh.animal_chore("COW", rh.COW_TILE, board, {}, {}) is None


# --- livestock_action: never None; dawn wheat top-up; cow before sheep ---

def test_livestock_action_tops_up_wheat_at_shed_at_dawn():
    board = _empty_board()
    # A placed cow so the line is live; hand standing at the shed, low on wheat.
    x, y = rh.COW_TILE
    board[y][x] = {"animal": "COW", "yield_units": 0, "fed_today": True,
                   "cared_today": True}
    action = rh.livestock_action(rh.SHED_TILE, board, {"WHEAT": 0}, {"WHEAT": 5},
                                 want_sheep=False)
    assert action == ["PICKUP", "WHEAT", rh.WHEAT_CARRY]


def test_livestock_action_never_returns_none():
    board = _empty_board()
    action = rh.livestock_action((4, 4), board, {}, {}, want_sheep=True)
    assert action is not None and isinstance(action, list)


# --- act(): end-to-end shape on a fresh board ---

def _fresh_obs(hour=0, day=0, money=3000, hands=None):
    board = _empty_board()
    n_inv = 1 + len(hands or [])
    return {
        "player": 0,
        "day": day,
        "hour": hour,
        "farms": [
            {"money": money, "tiles": board, "farmer": [4, 4], "hands": hands or []},
            {"money": money, "tiles": _empty_board(), "farmer": [4, 4], "hands": []},
        ],
        "market": {"inventory": {}, "prices": {}},
        "town": {"unlocked_shops": []},
        "private": {"shed": {}, "seeds": {}, "inventories": [{} for _ in range(n_inv)]},
    }


def test_act_hires_crew_and_returns_valid_shape_at_dawn():
    action = rh.RanchHandsStrategy().act(_fresh_obs(hour=0))
    assert isinstance(action["farmer"], list) and action["farmer"]
    assert action["hands"] == []  # no hands exist yet at hour 0
    hire_orders = [o for o in action["market"] if o[0] == "HIRE"]
    assert len(hire_orders) >= 1
    assert len(action["market"]) <= 10


def test_act_emits_one_action_per_existing_hand():
    hands = [[5, 4], [4, 5], [5, 5]]
    action = rh.RanchHandsStrategy().act(_fresh_obs(hour=3, hands=hands))
    assert len(action["hands"]) == len(hands)


def test_act_sells_melon_but_withholds_wheat_feed_buffer():
    obs = _fresh_obs(hour=5)
    obs["private"]["shed"] = {"MELON": 12, "WHEAT": 10}
    action = rh.RanchHandsStrategy().act(obs)
    assert ["SELL", "MELON", 12] in action["market"]
    assert ["SELL", "WHEAT", 10 - rh.WHEAT_BUFFER] in action["market"]


def test_act_does_not_sell_wheat_at_or_below_buffer():
    obs = _fresh_obs(hour=5)
    obs["private"]["shed"] = {"WHEAT": rh.WHEAT_BUFFER}
    action = rh.RanchHandsStrategy().act(obs)
    assert not any(o[0] == "SELL" and o[1] == "WHEAT" for o in action["market"])
