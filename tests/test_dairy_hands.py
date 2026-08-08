"""Unit tests for the dairy_hands experiment (issue #32, ADR-0007).

These exercise the *pure cow state machine* (`cow_farmer_action`) — build the
pasture, acquire and place the cow, then harvest / feed / care in strict order —
plus the `act()` overlay's melon-priority rule and cow market orders. The melon
crew itself is `wide_hands` verbatim and is covered by that experiment's tests;
the full-game no-crash guard lives in test_no_crash.py.
"""

from __future__ import annotations

from strategies import dairy_hands as dh


def _empty_board():
    return [[None for _ in range(10)] for _ in range(10)]


def _put(board, plot, tile):
    x, y = plot
    board[y][x] = tile


def _pasture():
    return {"kind": "PASTURE"}


def _cow(yield_units=0, fed=False, cared=False):
    return {
        "kind": "PASTURE",
        "animal": "COW",
        "placed_day": 0,
        "yield_units": yield_units,
        "fed_today": fed,
        "cared_today": cared,
    }


# --- Pasture tile placement: free NW tile, never a melon plot ---

def test_cow_tile_is_free_nw_tile_not_a_melon_plot():
    assert dh.COW_TILE not in dh.PLOTS
    x, y = dh.COW_TILE
    assert 0 <= x < 5 and 0 <= y < 5


def test_cow_tile_is_distance_four_from_shed():
    (cx, cy), (sx, sy) = dh.COW_TILE, dh.SHED_TILE
    assert abs(cx - sx) + abs(cy - sy) == 4  # closest a free tile can be to the shed


# --- Setup phase: build -> acquire -> place ---

def test_builds_pasture_when_standing_on_empty_cow_tile():
    board = _empty_board()
    assert dh.cow_farmer_action(dh.COW_TILE, board, {}, {}) == ["BUILD_PASTURE"]


def test_walks_toward_cow_tile_to_build_when_away():
    board = _empty_board()
    act = dh.cow_farmer_action(dh.SHED_TILE, board, {}, {})
    assert act == dh.hh.step_toward(dh.SHED_TILE, dh.COW_TILE)


def test_picks_up_bought_cow_while_standing_at_the_shed():
    board = _empty_board()
    act = dh.cow_farmer_action(dh.SHED_TILE, board, {}, {"COW": 1})
    assert act == ["PICKUP", "COW", 1]


def test_places_cow_on_empty_pasture_when_carrying_it():
    board = _empty_board()
    _put(board, dh.COW_TILE, _pasture())
    assert dh.cow_farmer_action(dh.COW_TILE, board, {"COW": 1}, {}) == ["PLACE", "COW"]


def test_walks_to_pasture_to_place_carried_cow():
    board = _empty_board()
    _put(board, dh.COW_TILE, _pasture())
    act = dh.cow_farmer_action(dh.SHED_TILE, board, {"COW": 1}, {})
    assert act == dh.hh.step_toward(dh.SHED_TILE, dh.COW_TILE)


def test_defers_to_melon_when_pasture_ready_but_no_cow_owned_yet():
    # Pasture built, no cow in inventory or shed: the market will buy it — the
    # farmer stays on the melon loop rather than idling at the pasture.
    board = _empty_board()
    _put(board, dh.COW_TILE, _pasture())
    assert dh.cow_farmer_action(dh.COW_TILE, board, {}, {}) is None


# --- Maintenance phase: harvest > feed > care, in strict priority ---

def test_harvests_milk_before_anything_else_when_yield_waiting():
    board = _empty_board()
    _put(board, dh.COW_TILE, _cow(yield_units=3, fed=False))
    assert dh.cow_farmer_action(dh.COW_TILE, board, {"WHEAT": 1}, {}) == ["HARVEST"]


def test_feeds_when_unfed_and_carrying_wheat():
    board = _empty_board()
    _put(board, dh.COW_TILE, _cow(yield_units=0, fed=False))
    assert dh.cow_farmer_action(dh.COW_TILE, board, {"WHEAT": 1}, {}) == ["FEED"]


def test_fetches_wheat_from_shed_when_unfed_and_empty_handed():
    board = _empty_board()
    _put(board, dh.COW_TILE, _cow(fed=False))
    act = dh.cow_farmer_action(dh.SHED_TILE, board, {}, {"WHEAT": 5})
    assert act == ["PICKUP", "WHEAT", dh.WHEAT_BUFFER]


def test_cares_after_feeding_when_still_on_the_tile():
    board = _empty_board()
    _put(board, dh.COW_TILE, _cow(yield_units=0, fed=True, cared=False))
    assert dh.cow_farmer_action(dh.COW_TILE, board, {}, {}) == ["CARE"]


def test_releases_farmer_to_melon_once_cow_fully_tended():
    board = _empty_board()
    _put(board, dh.COW_TILE, _cow(yield_units=0, fed=True, cared=True))
    assert dh.cow_farmer_action(dh.COW_TILE, board, {}, {}) is None


def test_never_makes_a_trip_just_to_care():
    # Fed but uncared and away from the tile: caring is not worth a dedicated
    # trip, so the farmer is released back to the melon loop.
    board = _empty_board()
    _put(board, dh.COW_TILE, _cow(fed=True, cared=False))
    assert dh.cow_farmer_action(dh.SHED_TILE, board, {}, {}) is None


# --- act(): overlay shape, melon priority, and cow market orders ---

def _obs(hour=0, day=0, money=3000, hands=None, board=None, shed=None, inv=None):
    board = board if board is not None else _empty_board()
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
        "private": {"shed": shed or {}, "seeds": {}, "inventories": [inv or {}]},
    }


def test_act_buys_a_cow_when_flush_and_none_owned():
    # On a non-hiring turn there is market room; the cow is bought (lowest
    # priority — it never displaces the melon crew's hire/sell/seed orders).
    action = dh.DairyHandsStrategy().act(_obs(hour=5, money=3000))
    assert ["BUY_ANIMAL", "COW", 1] in action["market"]
    assert len(action["market"]) <= 10


def test_act_does_not_buy_a_second_cow_when_one_is_placed():
    board = _empty_board()
    _put(board, dh.COW_TILE, _cow())
    action = dh.DairyHandsStrategy().act(_obs(hour=3, board=board))
    assert not any(o[0] == "BUY_ANIMAL" for o in action["market"])


def test_act_gives_melon_watering_priority_over_cow_chores():
    # Farmer stands on its unwatered melon at (4,4); a hungry cow waits at (2,2).
    board = _empty_board()
    _put(board, (4, 4), {"kind": "PLANT", "crop": "MELON", "planted_day": 3,
                         "yield_units": 1, "watered_today": False})
    _put(board, dh.COW_TILE, _cow(fed=False))
    action = dh.DairyHandsStrategy().act(_obs(hour=5, day=4, board=board,
                                              inv={"WHEAT": 1}))
    assert action["farmer"] == ["WATER"]


def test_act_sends_idle_farmer_to_tend_the_cow():
    # Melon at (4,4) already watered -> PASS; the farmer heads to the hungry cow.
    board = _empty_board()
    _put(board, (4, 4), {"kind": "PLANT", "crop": "MELON", "planted_day": 3,
                         "yield_units": 1, "watered_today": True})
    _put(board, dh.COW_TILE, _cow(fed=False))
    action = dh.DairyHandsStrategy().act(_obs(hour=5, day=4, board=board,
                                              inv={"WHEAT": 1}))
    assert action["farmer"] == dh.hh.step_toward((4, 4), dh.COW_TILE)


def test_act_sells_milk_sitting_in_the_shed():
    action = dh.DairyHandsStrategy().act(_obs(hour=5, shed={"MILK": 6}))
    assert ["SELL", "MILK", 6] in action["market"]
