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


def test_beat_outstanding_false_when_fed_even_with_chores_left():
    # Harvest/fertilizer/care are not survival-critical, so a fed animal with
    # those still pending does NOT keep the beat "outstanding".
    tiles = [[None for _ in range(10)] for _ in range(10)]
    a = (5, 0)
    tiles[a[1]][a[0]] = {"kind": "PASTURE", "animal": "COW", "fed_today": True,
                         "yield_units": 3, "fertilizer_available": True,
                         "cared_today": False}
    assert mr._beat_outstanding([(a, "COW")], tiles) is False
