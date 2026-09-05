"""Unit tests for the dung farm — a micro-herd kept as a fertilizer mine (#206).

The correction #206 was filed with: FERTILIZER has the **gentlest glut curve in
the game** (`linear/0.4`, base 100). It is in no shop and excluded from
``TOWN_CENTER_PRODUCTS``, so nothing ever drains it and the price only falls —
but it falls slowly. Cumulative revenue from a standing start is 9,010 for the
first 100 units and 16,020 for 200. So the mine is bounded but real, and
``COLLECT_FERTILIZER`` is a free byproduct of any tile holding an animal.

The hypothesis: a **micro-herd** — two to four head, fed on bought wheat, tended
by **one** dedicated hand — mines that curve without the crop line paying for
it. The champion, `dense_farm`, dedicates **two** of its eleven workers to a
ramp that reaches eleven head; this module keeps one hand on four head and
returns the other to the crop clusters.

The argument against, from #196: FEED count tracks tiles-per-worker almost
exactly (153 FEED at 1.8 tiles/worker, 17 at 5.6, 0 at 6.9). Every feeding is a
round trip to the shed. So the tests that matter here are the ones that pin the
herd small, pin the crop line *unshrunk*, and pin the feed supply — because
#187's null was a herd that starved rather than a herd that did not pay.
"""

from __future__ import annotations

from strategies import dense_farm as df
from strategies import dung_farm as dg
from strategies import field_rival as fr


def _orders(**kw):
    """`market_orders` on a quiet turn: no hire hour, land ramp already met, no
    empty plots — so only the herd and its feed can produce an order."""
    args = dict(day=20, hour=5, money=10_000, hands=10, quadrants=3, animals=0,
                shed={}, seeds={}, empty_plots=0, standing={},
                caps=dg.STRATEGY.CAPS)
    args.update(kw)
    return dg.market_orders(**args)


def _ops(orders, op):
    return [o for o in orders if o and o[0] == op]


# --- the herd is a micro-herd, tended by one hand ---

def test_exactly_one_hand_is_dedicated_to_the_herd():
    # The champion spends two of eleven workers on livestock; the whole idea is
    # that one is enough when the herd is four head.
    assert len(dg.LIVESTOCK_WORKERS) == 1
    assert len(fr.LIVESTOCK_WORKERS) == 2


def test_the_herd_never_grows_past_the_declared_band():
    # #206 declared "two to four animals" before any code existed.
    targets = [dg.animal_target(d) for d in range(fr.SEASON_DAYS)]
    assert max(targets) == 4
    assert dg.DECLARED_BAND == (2, 4)
    assert dg.DECLARED_BAND[0] <= max(targets) <= dg.DECLARED_BAND[1]


def test_the_champions_ramp_is_the_thing_being_replaced():
    # Positive control on the parameter: the benchmark really does ramp past the
    # band, so this module is changing something.
    assert max(fr.animal_target(d) for d in range(fr.SEASON_DAYS)) == 11


# --- the crop line does not pay for it ---

def test_the_crop_caps_are_the_champions_untouched():
    # The bar in #206 is additive: trading crop tiles for animals is #193/#202's
    # question and is already answered.
    assert dg.STRATEGY.CAPS == df.STRATEGY.CAPS
    assert dg.STRATEGY.CAPS == {"MELON": 18, "STRAWBERRY": 22, "WHEAT": 8}


def test_the_freed_hand_goes_back_to_the_crop_clusters():
    # Ten crop workers of four tiles each, against the champion's nine.
    assert dg.crop_cluster(1) == ()
    assigned = sum(len(dg.crop_cluster(i)) for i in range(11))
    champion = sum(len(fr.crop_cluster(i)) for i in range(11))
    assert assigned == 40
    assert assigned == champion + fr.CLUSTER


def test_no_crop_worker_shares_a_tile_with_another():
    tiles = [t for i in range(11) for t in dg.crop_cluster(i)]
    assert len(tiles) == len(set(tiles))
    assert not set(tiles) & set(fr.PASTURE_TILES)


def test_the_single_herder_is_given_every_pasture_in_play():
    # With two herders the champion strides the list; with one, a pasture left
    # to the missing herder would simply never be fed.
    assert dg.active_pastures(20, 4) == fr.PASTURE_TILES[:4]
    assert len(dg.active_pastures(20, 4)) == 4


def test_a_head_already_on_the_board_keeps_its_pasture_after_the_ramp_flattens():
    # An animal must keep being fed even if it is above target.
    assert len(dg.active_pastures(0, 6)) == 6


# --- the market: the herd stops at four, and it is fed ---

def test_the_market_buys_the_micro_herd_and_no_more():
    assert len(_ops(_orders(animals=0), "BUY_ANIMAL")) == 4


def test_the_market_stops_buying_once_the_micro_herd_stands():
    assert _ops(_orders(animals=4), "BUY_ANIMAL") == []


def test_animals_waiting_in_the_shed_are_not_re_bought():
    # The benchmark counts bought-but-unplaced head as pending; retiring its
    # ramp must not retire that. Re-buying on every one of a day's 24 turns is
    # measured: 79 sheep filled a 100-item shed and it discarded every harvest.
    assert len(_ops(_orders(animals=1, shed={"SHEEP": 2}), "BUY_ANIMAL")) == 1


def test_feed_is_bought_so_the_herd_cannot_starve():
    # The positive control #206 requires. An animal escapes at
    # `consecutive_unfed >= 2`, and the agent's only other BUY_PRODUCT is
    # fertilizer — #187's herd starved for exactly this reason.
    feed = _ops(_orders(animals=4, shed={}), "BUY_PRODUCT")
    assert feed and feed[0][1] == "WHEAT" and feed[0][2] > 0


def test_the_feed_buffer_is_not_sold_back_out_of_the_shed():
    sells = _ops(_orders(animals=4, shed={"WHEAT": 20}), "SELL")
    wheat = [s for s in sells if s[1] == "WHEAT"]
    assert wheat == [["SELL", "WHEAT", 20 - fr.feed_buffer(4)]]


def test_fertilizer_is_sold_rather_than_hoarded():
    # The mine only pays on the sell side; fertilizer is on the sim's own
    # PRODUCTS list at a base of 100 (#184).
    sells = _ops(_orders(animals=4, shed={"FERTILIZER": 12}), "SELL")
    assert ["SELL", "FERTILIZER", 12] in sells


def test_the_ten_order_cap_is_still_respected():
    shed = {"FERTILIZER": 9, "WOOL": 4, "MILK": 4, "MELON": 4, "STRAWBERRY": 4,
            "WHEAT": 40, "EGG": 2, "CARROT": 2, "TOMATO": 2}
    assert len(_orders(animals=0, shed=shed, hour=0, hands=0)) <= fr.MAX_ORDERS


# --- it is a contender, and it leaves the champion alone ---

def test_it_is_a_contender_that_moves_nothing_it_measures_against():
    assert dg.STRATEGY.name == "dung_farm"
    assert dg.STRATEGY.benchmark is False
    assert fr.STRATEGY.benchmark is True
    assert fr.LIVESTOCK_WORKERS == (1, 2)
    assert fr.ANIMAL_RAMP == ((0, 1), (4, 3), (8, 4), (12, 8), (16, 10), (24, 11))
    assert df.STRATEGY.CAPS == {"MELON": 18, "STRAWBERRY": 22, "WHEAT": 8}


def test_the_herder_is_asked_for_a_herd_action_and_the_rest_for_crop_actions():
    # An end-to-end shape check on `act`: the one herder must be indexed out of
    # the crop crew, or the farm silently runs eleven crop workers and no herd.
    obs = _obs()
    out = dg.STRATEGY().act(obs)
    units = [out["farmer"]] + list(out["hands"])
    assert len(units) == 11
    assert all(isinstance(u, list) and u for u in units)


def _obs():
    """A day-20 board: three quadrants unlocked, empty tiles, full crew."""
    tiles = [[None] * fr.BOARD for _ in range(fr.BOARD)]
    for y in range(fr.BOARD):
        for x in range(fr.BOARD):
            if fr.quadrant_of(x, y) == "SE":
                tiles[y][x] = "LOCKED"
    return {
        "player": 0,
        "day": 20,
        "hour": 5,
        "farms": [{
            "money": 10_000,
            "tiles": tiles,
            "farmer": [4, 4],
            "hands": [[4, 4]] * 10,
            "unlocked_quadrants": ["NW", "NE", "SW"],
        }],
        "private": {"shed": {}, "seeds": {}, "inventories": [{}] * 11},
    }


# --- the weed that pins a single herder (reproduced on seed 300) ---

def test_a_weed_on_a_pasture_tile_is_dug_rather_than_placed_on():
    # Seed 300, measured: a weed spawned on pasture tile (4, 3) on day 7. The
    # benchmark's chore scan treats any dict that is not an animal as a built
    # structure and answers PLACE, which the sim silently no-ops on a WEED. The
    # herder answered PLACE fourteen times a day for the rest of the season and
    # the herd never grew past one head — 2,448 fertilizer against a median of
    # 6,545. With two herders that costs one herder's pastures; with one it is
    # the whole herd, so this module cannot inherit it.
    xy = fr.PASTURE_TILES[1]
    weed = {"kind": "WEED"}
    assert dg.pasture_chore(xy, weed, list(xy), {"SHEEP": 1}, {}) == ["DIG"]
    assert fr._pasture_chore(xy, weed, list(xy), {"SHEEP": 1}, {}) == ["PLACE", "SHEEP"]


def test_a_weeded_pasture_is_walked_to_rather_than_answered_from_afar():
    xy = fr.PASTURE_TILES[1]
    chore = dg.pasture_chore(xy, {"kind": "WEED"}, [9, 9], {"SHEEP": 1}, {})
    assert chore[0] in ("NORTH", "SOUTH", "EAST", "WEST")


def _tended_animal():
    """A head that wants nothing today — seed 300's pasture zero."""
    return {"kind": "PASTURE", "animal": "SHEEP", "yield_units": 0,
            "fed_today": True, "cared_today": True, "fertilizer_available": False}


def test_the_herder_is_not_pinned_by_a_weeded_pasture():
    # End-to-end through the scan, as seed 300 played it: pasture zero is a
    # tended head that wants nothing, pasture one is weeded, and the herd's
    # remaining head are waiting in the shed behind it.
    tiles = [[None] * fr.BOARD for _ in range(fr.BOARD)]
    first = fr.PASTURE_TILES[0]
    tiles[first[1]][first[0]] = _tended_animal()
    weeded = fr.PASTURE_TILES[1]
    tiles[weeded[1]][weeded[0]] = {"kind": "WEED"}
    got = dg.herd_worker_action(list(fr.PASTURE_TILES[:3]), tiles, list(weeded),
                                {"SHEEP": 1}, {}, hour=5)
    assert got == ["DIG"]
    # The benchmark's scan is what stalls: a PLACE the sim silently no-ops.
    assert fr.herd_worker_action(list(fr.PASTURE_TILES[:3]), tiles, list(weeded),
                                 {"SHEEP": 1}, {}, hour=5) == ["PLACE", "SHEEP"]


def test_an_unweeded_pasture_is_still_the_benchmarks_own_chore():
    # The fix adds one branch and must change nothing else about herding.
    tiles = [[None] * fr.BOARD for _ in range(fr.BOARD)]
    pastures = list(fr.PASTURE_TILES[:3])
    for pos in ([4, 4], list(pastures[0]), [9, 9]):
        assert (dg.herd_worker_action(pastures, tiles, pos, {}, {}, hour=5)
                == fr.herd_worker_action(pastures, tiles, pos, {}, {}, hour=5))
