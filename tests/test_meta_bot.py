"""meta_bot — a frozen benchmark hard-coded to the top-Elo modal comp (#59).

Helper-level unit tests only (the pin/golden test is Task 5). Every decision in
`strategies.meta_bot` lives in a pure module-level helper so the technique is
testable without spinning up a full 720-turn game. Constants and mechanics are
the ones recovered by the Phase-0 feasibility spike (task-3-report on #59).
"""

from __future__ import annotations

from strategies import meta_bot as mb


# --- helpers -----------------------------------------------------------------

def _bare_tiles():
    """A 10x10 board of empty (buildable) tiles."""
    return [[None for _ in range(10)] for _ in range(10)]


def _set(tiles, pos, tile):
    x, y = pos
    tiles[y][x] = tile
    return tiles


def _pasture():
    return {"kind": "PASTURE"}


def _cow(**over):
    t = {
        "kind": "PASTURE",
        "animal": "COW",
        "placed_day": 0,
        "yield_units": 0,
        "fed_today": False,
        "cared_today": False,
        "fertilizer_available": False,
    }
    t.update(over)
    return t


def _windowed_melon(day, age=8):
    """A live melon whose age (default 8) sits inside its fertilizer window
    [6, 12] on the given game `day`, not yet capped or already covered."""
    return {"kind": "PLANT", "crop": "MELON", "planted_day": day - age, "yield_units": 0}


# --- identity / composition --------------------------------------------------

def test_meta_bot_is_a_readonly_benchmark():
    """The whole point: it is a fixed benchmark opponent, never a contender."""
    assert mb.STRATEGY.benchmark is True
    assert mb.STRATEGY.name == "meta_bot"


def test_composition_matches_the_reachable_meta_comp():
    """9 COW + 4 SHEEP, all on distinct tiles (Phase-0 reachable comp)."""
    cows = [t for t in mb.ANIMAL_TILES if t[1] == "COW"]
    sheep = [t for t in mb.ANIMAL_TILES if t[1] == "SHEEP"]
    assert len(cows) == mb.N_COW == 9
    assert len(sheep) == mb.N_SHEEP == 4
    assert len({t[0] for t in mb.ANIMAL_TILES}) == len(mb.ANIMAL_TILES)


def test_animal_tiles_are_the_exact_phase0_layout():
    """The NE 3x3 cow block + the SW sheep row, verbatim from task-3-report."""
    cow_tiles = {t for t, k in mb.ANIMAL_TILES if k == "COW"}
    sheep_tiles = {t for t, k in mb.ANIMAL_TILES if k == "SHEEP"}
    assert cow_tiles == {(5, 0), (6, 0), (7, 0),
                         (5, 1), (6, 1), (7, 1),
                         (5, 2), (6, 2), (7, 2)}
    assert sheep_tiles == {(0, 5), (1, 5), (2, 5), (3, 5)}


def test_cow_tiles_live_in_NE_and_sheep_tiles_in_SW():
    """Placement respects the land the comp unlocks (NE for cows, SW for sheep)."""
    for (x, y), kind in mb.ANIMAL_TILES:
        if kind == "COW":
            assert x >= 5 and y < 5      # NE quadrant
        else:
            assert x < 5 and y >= 5      # SW quadrant


# --- land purchases ----------------------------------------------------------

def test_land_orders_buys_NE_first_then_SW_never_SE():
    """Cheapest two-quadrant expansion, in the sim's fixed NE->SW order."""
    assert mb.land_orders(["NW"], money=100000) == [["BUY_LAND"]]
    assert mb.land_orders(["NW", "NE"], money=100000) == [["BUY_LAND"]]
    # Already own NW+NE+SW -> never reach for SE.
    assert mb.land_orders(["NW", "NE", "SW"], money=100000) == []


def test_land_orders_respects_a_money_buffer():
    """Never spend melon working capital down to nothing on land."""
    assert mb.land_orders(["NW"], money=1000) == []          # NE price 1000, no buffer left
    assert mb.land_orders(["NW", "NE"], money=2100) == []     # SW price 2000, buffer short


# --- animal purchases --------------------------------------------------------

def test_animal_buy_orders_stand_up_cows_before_sheep():
    """Cows lead; the batch is capped at the 10-order market limit."""
    orders = mb.animal_buy_orders(tiles=_bare_tiles(), shed={}, inventories=[{}],
                                  money=100000)
    kinds = [o[1] for o in orders if o[0] == "BUY_ANIMAL"]
    assert kinds and kinds[0] == "COW"
    assert len(orders) <= 10


def test_animal_buy_orders_gate_on_unlocked_land():
    """No cow before NE is unlocked; no sheep before SW is unlocked."""
    only_nw = mb.animal_buy_orders(_bare_tiles(), {}, [{}], 100000, unlocked=("NW",))
    assert only_nw == []
    ne_only = mb.animal_buy_orders(_bare_tiles(), {}, [{}], 100000,
                                   unlocked=("NW", "NE"))
    assert ne_only and all(o[1] == "COW" for o in ne_only)


def test_animal_buy_orders_do_not_rebuy_existing_animals():
    """A cow already placed / in shed / in a worker's inventory is not re-bought."""
    tiles = _bare_tiles()
    for pos in [(5, 0), (6, 0), (7, 0), (5, 1), (6, 1), (7, 1), (5, 2), (6, 2), (7, 2)]:
        _set(tiles, pos, _cow())            # all 9 cows already placed
    orders = mb.animal_buy_orders(tiles, shed={"SHEEP": 1}, inventories=[{}],
                                  money=100000)
    kinds = [o[1] for o in orders]
    assert "COW" not in kinds               # cows fully stood up
    assert kinds.count("SHEEP") == mb.N_SHEEP - 1   # one sheep already in shed


def test_animal_buy_orders_stop_when_broke():
    """No order we cannot afford (money below cost + buffer)."""
    assert mb.animal_buy_orders(_bare_tiles(), {}, [{}], money=100) == []


# --- fertilizer (day-2 gate, prefer the free herd byproduct) -----------------

def test_fertilizer_orders_never_before_day_two():
    """Day-2 floor: even a melon that wants fertilizer buys nothing before day 2."""
    tiles = _bare_tiles()
    _set(tiles, mb.MELON_PLOTS[0], _windowed_melon(day=1))
    assert mb.fertilizer_orders(day=1, tiles=tiles, shed={}, inventories=[{}],
                                money=100000) == []


def test_fertilizer_orders_buy_when_the_farmer_melon_wants_it():
    """From day 2, a melon in its window with none on hand triggers a buy."""
    tiles = _bare_tiles()
    _set(tiles, mb.MELON_PLOTS[0], _windowed_melon(day=2))
    orders = mb.fertilizer_orders(day=2, tiles=tiles, shed={}, inventories=[{}],
                                  money=100000)
    assert orders == [["BUY_PRODUCT", "FERTILIZER", 1]]


def test_fertilizer_orders_prefer_the_free_unit_already_in_the_shed():
    """A free COLLECT_FERTILIZER unit in the shed means we never buy one."""
    tiles = _bare_tiles()
    _set(tiles, mb.MELON_PLOTS[0], _windowed_melon(day=2))
    orders = mb.fertilizer_orders(day=2, tiles=tiles, shed={"FERTILIZER": 1},
                                  inventories=[{}], money=100000)
    assert orders == []


# --- worker role assignment --------------------------------------------------

def test_melon_plot_for_is_the_wide_crew_mapping():
    """Every worker maps to its wide-crew melon plot; livestock hands farm one
    too until their land opens. Indices past the crew clamp to the last plot."""
    assert mb.melon_plot_for(0) == mb.MELON_PLOTS[0]
    assert mb.melon_plot_for(9) == mb.MELON_PLOTS[9]
    assert mb.melon_plot_for(50) == mb.MELON_PLOTS[-1]


def test_beat_active_only_once_the_beat_land_is_unlocked():
    """A livestock hand keeps farming melon until its animal's land is bought."""
    cow_beat = mb.BEATS[7]      # cows -> NE
    sheep_beat = mb.BEATS[9]    # sheep -> SW
    assert mb.beat_active(cow_beat, ["NW"]) is False
    assert mb.beat_active(cow_beat, ["NW", "NE"]) is True
    assert mb.beat_active(sheep_beat, ["NW", "NE"]) is False
    assert mb.beat_active(sheep_beat, ["NW", "NE", "SW"]) is True


def test_every_animal_tile_is_covered_by_exactly_one_beat():
    """The livestock beats partition the herd — no animal is orphaned."""
    covered = [tp for idx in mb.LIVESTOCK_INDICES for tp, _ in mb.BEATS[idx]]
    assert sorted(covered) == sorted(tp for tp, _ in mb.ANIMAL_TILES)
    assert len(covered) == len(set(covered))    # each animal in exactly one beat


# --- livestock state machine -------------------------------------------------

def test_livestock_hand_waits_near_shed_until_its_land_is_unlocked():
    """A cow hand cannot build on locked NE land; it idles toward the shed."""
    beat = mb.BEATS[min(mb.LIVESTOCK_INDICES)]     # a cow beat
    action = mb.livestock_action(pos=[4, 4], beat=beat, tiles=_bare_tiles(),
                                 inv={}, shed={}, unlocked=("NW",))
    assert action == ["PASS"]                      # already at the shed tile


def test_livestock_hand_builds_a_pasture_when_standing_on_an_empty_tile():
    """On its animal tile with the land unlocked and nothing built, it builds."""
    tp = mb.BEATS[min(mb.LIVESTOCK_INDICES)][0][0]  # first cow tile
    action = mb.livestock_action(pos=list(tp), beat=mb.BEATS[min(mb.LIVESTOCK_INDICES)],
                                 tiles=_bare_tiles(), inv={}, shed={},
                                 unlocked=("NW", "NE", "SW"))
    assert action == ["BUILD_PASTURE"]


def test_livestock_hand_places_a_held_animal_on_its_empty_pasture():
    """Holding a cow while standing on an empty pasture -> PLACE it."""
    beat = mb.BEATS[min(mb.LIVESTOCK_INDICES)]
    tp = beat[0][0]
    tiles = _set(_bare_tiles(), tp, _pasture())
    action = mb.livestock_action(pos=list(tp), beat=beat, tiles=tiles,
                                 inv={"COW": 1}, shed={}, unlocked=("NW", "NE", "SW"))
    assert action == ["PLACE", "COW"]


def test_livestock_hand_feeds_a_hungry_animal_it_has_wheat_for():
    """A placed, unfed animal + wheat in hand -> FEED (survival priority)."""
    beat = mb.BEATS[min(mb.LIVESTOCK_INDICES)]
    tp = beat[0][0]
    tiles = _set(_bare_tiles(), tp, _cow(fed_today=False))
    action = mb.livestock_action(pos=list(tp), beat=beat, tiles=tiles,
                                 inv={"WHEAT": 3}, shed={}, unlocked=("NW", "NE", "SW"))
    assert action == ["FEED"]


def test_livestock_hand_fetches_wheat_from_shed_when_hungry_and_empty_handed():
    """Hungry animal, no wheat in hand but wheat in the shed -> go pick it up."""
    beat = mb.BEATS[min(mb.LIVESTOCK_INDICES)]
    tp = beat[0][0]
    tiles = _set(_bare_tiles(), tp, _cow(fed_today=False))
    action = mb.livestock_action(pos=list(mb.SHED_TILE), beat=beat, tiles=tiles,
                                 inv={}, shed={"WHEAT": 10}, unlocked=("NW", "NE", "SW"))
    assert action[0] == "PICKUP" and action[1] == "WHEAT"


def test_livestock_hand_harvests_before_the_yield_buffer_overflows():
    """A placed animal carrying product (already fed) -> HARVEST it."""
    beat = mb.BEATS[min(mb.LIVESTOCK_INDICES)]
    tp = beat[0][0]
    tiles = _set(_bare_tiles(), tp, _cow(fed_today=True, yield_units=3))
    action = mb.livestock_action(pos=list(tp), beat=beat, tiles=tiles,
                                 inv={}, shed={}, unlocked=("NW", "NE", "SW"))
    assert action == ["HARVEST"]


def test_livestock_hand_collects_the_free_fertilizer_byproduct():
    """Fully fed animal with fertilizer available -> COLLECT_FERTILIZER (free income)."""
    beat = mb.BEATS[min(mb.LIVESTOCK_INDICES)]
    tp = beat[0][0]
    tiles = _set(_bare_tiles(), tp, _cow(fed_today=True, cared_today=True,
                                         fertilizer_available=True))
    action = mb.livestock_action(pos=list(tp), beat=beat, tiles=tiles,
                                 inv={}, shed={}, unlocked=("NW", "NE", "SW"))
    assert action == ["COLLECT_FERTILIZER"]


def test_livestock_hand_fetches_a_bought_animal_from_the_shed():
    """Empty pasture, no animal in hand, one waiting in the shed -> head to shed."""
    beat = mb.BEATS[min(mb.LIVESTOCK_INDICES)]
    tp = beat[0][0]
    tiles = _set(_bare_tiles(), tp, _pasture())
    action = mb.livestock_action(pos=list(tp), beat=beat, tiles=tiles,
                                 inv={}, shed={"COW": 5}, unlocked=("NW", "NE", "SW"))
    # Not on the shed tile -> it must walk toward it (a move verb).
    assert action in (["WEST"], ["NORTH"], ["SOUTH"], ["EAST"])


# --- market shaping ----------------------------------------------------------

def test_sell_orders_hold_back_the_wheat_feed_buffer():
    """Crop-wheat is sold only down to the herd's feed buffer, never below it."""
    orders = mb._sell_orders_keep_feed({"WHEAT": mb.WHEAT_BUFFER + 5, "MILK": 4})
    wheat = [o for o in orders if o[1] == "WHEAT"]
    assert wheat == [["SELL", "WHEAT", 5]]           # only the surplus above the buffer
    assert ["SELL", "MILK", 4] in orders             # animal product sells in full
    # At or below the buffer, no wheat is sold.
    assert not any(o[1] == "WHEAT"
                   for o in mb._sell_orders_keep_feed({"WHEAT": mb.WHEAT_BUFFER}))


def test_wheat_orders_stock_feed_only_once_the_herd_exists_and_from_surplus():
    """No feed buy before there's an animal, nor when money is below the reserve."""
    tiles = _bare_tiles()
    # No herd yet -> nothing.
    assert mb.wheat_orders(tiles, {}, [{}], money=100000) == []
    # A cow in the shed (bought, awaiting placement) -> stock the buffer.
    orders = mb.wheat_orders(tiles, {"COW": 1}, [{}], money=100000)
    assert orders and orders[0][0] == "BUY_PRODUCT" and orders[0][1] == "WHEAT"
    # Below the melon reserve -> protect capital, buy no feed.
    assert mb.wheat_orders(tiles, {"COW": 1}, [{}], money=mb.MELON_RESERVE - 1) == []


# --- behavior pin (frozen benchmark, #59) ------------------------------------

import hashlib
import json


def _fresh_obs(hour=0, day=0, money=100000, hands=None):
    board = [[None for _ in range(10)] for _ in range(10)]
    hands = hands or []
    n_inv = 1 + len(hands)
    return {
        "player": 0, "day": day, "hour": hour,
        "farms": [
            {"money": money, "tiles": board, "farmer": [4, 4], "hands": hands},
            {"money": money, "tiles": [[None]*10 for _ in range(10)], "farmer": [4, 4], "hands": []},
        ],
        "market": {"inventory": {}, "prices": {}},
        "town": {"unlocked_shops": []},
        "private": {"shed": {}, "seeds": {}, "inventories": [{} for _ in range(n_inv)]},
    }


def test_meta_bot_dawn_move_is_frozen():
    # meta_bot is a readonly benchmark: its opening move is pinned so any edit
    # to its behavior breaks CI (the "can't be changed" contract, #59).
    action = mb.MetaBotStrategy().act(_fresh_obs(hour=0, day=0))
    digest = hashlib.sha256(json.dumps(action, sort_keys=True).encode()).hexdigest()
    assert digest == "b12fed068545aec8006f6b8f93ab18a9b7e4e12f507ad274f80f0eae211fbd48"
