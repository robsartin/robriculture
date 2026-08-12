"""meta_rancher — tuned contender sibling of the frozen meta_bot benchmark (#61)."""

from __future__ import annotations

from strategies import meta_rancher as mr


def test_meta_rancher_is_a_contender_not_a_benchmark():
    assert mr.STRATEGY.benchmark is False
    assert mr.STRATEGY.name == "meta_rancher"


def test_composition_matches_the_phase0_comp():
    cows = [t for t in mr.ANIMAL_TILES if t[1] == "COW"]
    sheep = [t for t in mr.ANIMAL_TILES if t[1] == "SHEEP"]
    assert len(cows) == mr.N_COW == 9
    assert len(sheep) == mr.N_SHEEP == 4
    assert len({t[0] for t in mr.ANIMAL_TILES}) == len(mr.ANIMAL_TILES)


def test_seed_restock_orders_buys_melon_seed_for_empty_active_plots():
    # Extracted from act(): an empty active melon plot with no seed on hand and
    # money to spare yields a BUY_SEED MELON order.
    tiles = [[None for _ in range(10)] for _ in range(10)]
    orders = mr.seed_restock_orders(
        tiles=tiles, seeds={}, melon_open=True, catch=None,
        n_workers=3, money=100000, market_len=0,
    )
    assert ["BUY_SEED", "MELON", 3] in orders


def test_seed_restock_orders_respects_the_market_cap():
    tiles = [[None for _ in range(10)] for _ in range(10)]
    orders = mr.seed_restock_orders(
        tiles=tiles, seeds={}, melon_open=True, catch=None,
        n_workers=3, money=100000, market_len=10,
    )
    assert orders == []


def test_most_at_risk_returns_the_hungriest_animal_first():
    # Two placed cows in a beat; one already went a day unfed (fed_today False and
    # a low/again-unfed marker), the other fed. The at-risk one is returned.
    # Tiles are addressed tiles[y][x] (matching hh.tile_at and the sim's own
    # "tiles[y][x]" layout — see test_livestock_hand.py for the same convention).
    tiles = [[None for _ in range(10)] for _ in range(10)]
    a, b = (5, 0), (6, 0)
    tiles[a[1]][a[0]] = {"kind": "PASTURE", "animal": "COW", "fed_today": False}
    tiles[b[1]][b[0]] = {"kind": "PASTURE", "animal": "COW", "fed_today": True}
    beat = [(a, "COW"), (b, "COW")]
    assert mr.most_at_risk(beat, tiles) == a


def test_most_at_risk_none_when_all_fed():
    tiles = [[None for _ in range(10)] for _ in range(10)]
    a = (5, 0)
    tiles[a[1]][a[0]] = {"kind": "PASTURE", "animal": "COW", "fed_today": True}
    assert mr.most_at_risk([(a, "COW")], tiles) is None


# --- nearest_hungry_beat: the idle-non-livestock-worker reassignment fallback,
# added only after the survivor measurement (Step 4) showed most_at_risk alone
# still left escapes (11/13 unchanged across seeds 0-2). ---

def test_nearest_hungry_beat_returns_the_closest_unlocked_beat_with_a_hungry_animal():
    tiles = [[None for _ in range(10)] for _ in range(10)]
    x, y = mr.BEATS[8][0][0]  # a sheep beat, SW quadrant
    tiles[y][x] = {"kind": "PASTURE", "animal": "SHEEP", "fed_today": False}
    unlocked = ["NW", "NE", "SW"]
    assert mr.nearest_hungry_beat((0, 4), tiles, unlocked) == 8


def test_nearest_hungry_beat_ignores_beats_whose_land_is_locked():
    tiles = [[None for _ in range(10)] for _ in range(10)]
    x, y = mr.BEATS[8][0][0]
    tiles[y][x] = {"kind": "PASTURE", "animal": "SHEEP", "fed_today": False}
    unlocked = ["NW"]  # SW not unlocked yet
    assert mr.nearest_hungry_beat((0, 4), tiles, unlocked) is None


def test_nearest_hungry_beat_none_when_nothing_hungry():
    tiles = [[None for _ in range(10)] for _ in range(10)]
    assert mr.nearest_hungry_beat((0, 0), tiles, ["NW", "NE", "SW"]) is None


# --- _beat_outstanding: lets a livestock hand whose OWN animals are placed and
# fed for the day (survival-critical work only — harvest/fertilizer/care can
# wait) recognize it's free to help a neighbor instead of sitting on PASS.
# Added after a seeded full-game trace showed the real end-game idle capacity
# is a livestock hand done with feeding early — but gating on "every chore
# done" (harvest/fertilizer/care too) kept it tied to its own beat until too
# late in the day to complete the shed round-trip to a short-staffed neighbor
# (its dedicated hand not hired that day) before the day resets. ---

def test_beat_outstanding_true_when_an_animal_is_unfed():
    tiles = [[None for _ in range(10)] for _ in range(10)]
    a = (5, 0)
    tiles[a[1]][a[0]] = {"kind": "PASTURE", "animal": "COW", "fed_today": False,
                         "cared_today": True}
    assert mr._beat_outstanding([(a, "COW")], tiles) is True


# --- hire_orders: hires yield market slots to sells + herd-critical buys
# (tuning target #2, #61) -- forcing the full crew every hire-eligible morning
# must never push the 10-order cap past the price-sensitive sells or the
# herd-critical land/animal buys; any surplus hire target simply catches up
# the next morning instead. ---

def test_hire_orders_never_exceed_the_remaining_cap():
    # 8 orders already queued (e.g. sells + buys); at most 2 hire slots remain.
    assert mr.hire_orders(n_target=9, market_len=8, reserved=0) == [["HIRE"], ["HIRE"]]


def test_hire_orders_yield_slots_reserved_for_herd_buys():
    # 5 orders queued, but reserve 3 slots for land/animal buys -> only 2 hires.
    assert mr.hire_orders(n_target=9, market_len=5, reserved=3) == [["HIRE"], ["HIRE"]]


def test_hire_orders_empty_when_no_slots():
    assert mr.hire_orders(n_target=9, market_len=10, reserved=0) == []


def test_heavy_sell_dawn_hire_never_displaces_sell_or_herd_buy():
    """End-to-end: a fresh dawn with a heavy-sell shed and the herd already up.

    Every melon plot is already a live, watered plant (so seed restock wants
    nothing) and the shed is stuffed with sellable produce plus a herd-existing
    COW. NE land is unlocked, SW is not, so land_orders wants one more BUY_LAND
    and animal_buy_orders wants COW purchases -- these, sized to fill the
    10-order cap exactly, leave zero slots for the forced full-crew hire
    target. Every SELL and every herd-critical BUY_LAND/BUY_ANIMAL order that
    the pure helpers would emit must still be present; hiring must yield
    entirely rather than truncate any of them.
    """
    tiles = [[None for _ in range(10)] for _ in range(10)]
    live_plant = {"kind": "PLANT", "crop": mr.MELON, "watered_today": True, "planted_day": 0}
    for x, y in mr.MELON_PLOTS:
        tiles[y][x] = live_plant
    shed = {"WHEAT": 50, "CARROT": 5, "MELON": 5, "MILK": 5, "TOMATO": 5, "COW": 1}
    obs = {
        "player": 0, "day": 1, "hour": 0,
        "farms": [
            {"money": 1_000_000, "tiles": tiles, "farmer": [4, 4],
             "hands": [], "unlocked_quadrants": ["NW", "NE"]},
            {"money": 1_000_000, "tiles": [[None] * 10 for _ in range(10)],
             "farmer": [4, 4], "hands": []},
        ],
        "market": {"inventory": {}, "prices": {}},
        "town": {"unlocked_shops": []},
        "private": {"shed": shed, "seeds": {}, "inventories": [{}]},
    }

    market = mr.MetaRancherStrategy().act(obs)["market"]

    assert len(market) <= 10
    for order in mr._sell_orders_keep_feed(shed):
        assert order in market
    assert ["BUY_LAND"] in market
    assert market.count(["BUY_ANIMAL", "COW", 1]) == 4
    # No room left this turn -- the forced full-crew hire target yields entirely.
    assert ["HIRE"] not in market


def test_beat_outstanding_false_when_fed_even_with_chores_left():
    # Harvest/fertilizer/care are not survival-critical, so a fed animal with
    # those still pending does NOT keep the beat "outstanding".
    tiles = [[None for _ in range(10)] for _ in range(10)]
    a = (5, 0)
    tiles[a[1]][a[0]] = {"kind": "PASTURE", "animal": "COW", "fed_today": True,
                         "yield_units": 3, "fertilizer_available": True,
                         "cared_today": False}
    assert mr._beat_outstanding([(a, "COW")], tiles) is False
