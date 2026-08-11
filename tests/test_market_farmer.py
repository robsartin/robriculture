"""Unit tests for the market_farmer pure decision helpers.

These exercise the design's load-bearing logic without a full 720-turn game:
the sim-faithful price curve, the price-aware sell throttle (the anti-flood
mechanism), roaming crop chores + nearest-tile dispatch, the animal state
machine, and crew sizing. The full-game no-crash guard lives in test_no_crash.py
(auto-included via the REGISTRY).
"""

from __future__ import annotations

from kaggisim import economy
from strategies import market_farmer as mf

# Cross-check our price model against the installed sim itself.
from kaggle_environments.envs.kaggriculture import kaggriculture as sim


# --- market_price: mirrors the sim exactly --------------------------------

def test_price_at_base_equals_base_when_inventory_at_I0():
    for item, p in economy.MARKET_PARAMS.items():
        assert mf.market_price(item, p["I0"]) == p["base"]


def test_market_price_matches_sim_across_inventories():
    for item in economy.MARKET_PARAMS:
        I0 = economy.MARKET_PARAMS[item]["I0"]
        for inv in (I0 - 500, I0, I0 + 1, I0 + 50, I0 + 200, I0 + 1000):
            assert mf.market_price(item, inv) == sim.market_price(item, inv), (item, inv)


def test_selling_more_lowers_price_above_I0():
    I0 = economy.MARKET_PARAMS["MELON"]["I0"]
    assert mf.market_price("MELON", I0 + 100) < mf.market_price("MELON", I0 + 10)


# --- max_sellable: the price-aware throttle -------------------------------

def test_bottomless_market_allows_many_units():
    # WHEAT stays ~flat well above its floor, so hundreds clear.
    I0 = economy.MARKET_PARAMS["WHEAT"]["I0"]
    assert mf.max_sellable("WHEAT", I0, 0.55) > 200


def test_trap_market_is_throttled_hard():
    # MELON craters fast; at a 0.66 floor only a modest count clears.
    I0 = economy.MARKET_PARAMS["MELON"]["I0"]
    k = mf.max_sellable("MELON", I0, 0.66)
    assert 0 < k < 100


def test_max_sellable_respects_already_flooded_inventory():
    # If the shared market is already deep in glut (a flooder crashed it), we
    # sell nothing more into the crater.
    I0 = economy.MARKET_PARAMS["MELON"]["I0"]
    assert mf.max_sellable("MELON", I0 + 5000, 0.66) == 0


def test_price_aware_sell_holds_wheat_feed_buffer():
    shed = {"WHEAT": mf.WHEAT_FEED_BUFFER + 3}
    market_inv = {"WHEAT": economy.MARKET_PARAMS["WHEAT"]["I0"]}
    orders = mf.price_aware_sell_orders(shed, market_inv)
    wheat = [o for o in orders if o[1] == "WHEAT"]
    assert wheat and wheat[0][2] == 3  # only the surplus above the feed buffer


def test_price_aware_sell_skips_flooded_trap():
    shed = {"MELON": 10}
    market_inv = {"MELON": economy.MARKET_PARAMS["MELON"]["I0"] + 5000}
    orders = mf.price_aware_sell_orders(shed, market_inv)
    assert all(o[1] != "MELON" for o in orders)


# --- crop_tile_chore ------------------------------------------------------

def test_empty_tile_plants_when_seed_and_horizon_ok():
    assert mf.crop_tile_chore(None, "CARROT", day=0, hour=0, have_seed=True) == ["PLANT", "CARROT"]


def test_empty_tile_no_plant_without_seed():
    assert mf.crop_tile_chore(None, "CARROT", day=0, hour=0, have_seed=False) is None


def test_empty_tile_no_plant_on_last_turn_of_day():
    last = mf.TURNS_PER_DAY - 1
    assert mf.crop_tile_chore(None, "CARROT", day=0, hour=last, have_seed=True) is None


def test_weed_is_dug():
    assert mf.crop_tile_chore({"kind": "WEED"}, "MELON", 0, 0, False) == ["DIG"]


def test_live_plant_waters_when_dry():
    tile = {"kind": "PLANT", "crop": "MELON", "planted_day": 0, "watered_today": False,
            "yield_units": 0}
    assert mf.crop_tile_chore(tile, "MELON", day=1, hour=0, have_seed=True) == ["WATER"]


def test_non_ongoing_harvests_only_at_maturity():
    # Wheat matures at max_yield_day=4. Watered, with yield, but only age 3: wait.
    young = {"kind": "PLANT", "crop": "WHEAT", "planted_day": 0, "watered_today": True,
             "yield_units": 3}
    assert mf.crop_tile_chore(young, "WHEAT", day=3, hour=0, have_seed=False) is None
    mature = dict(young)
    assert mf.crop_tile_chore(mature, "WHEAT", day=4, hour=0, have_seed=False) == ["HARVEST"]


def test_ongoing_harvests_whenever_yield_ready():
    tile = {"kind": "PLANT", "crop": "TOMATO", "planted_day": 0, "watered_today": True,
            "yield_units": 1}
    # first_yield_day=8; at day 9 with yield, take it.
    assert mf.crop_tile_chore(tile, "TOMATO", day=9, hour=0, have_seed=False) == ["HARVEST"]


# --- roam_action: nearest pending tile ------------------------------------

def _grid(fill=None):
    return [[fill for _ in range(5)] for _ in range(5)]


def test_roam_moves_toward_nearest_needy_tile():
    tiles = _grid(None)  # every beat tile is empty (wants planting)
    beat = [(0, 0), (2, 0)]
    pos = [1, 0]
    # nearest empty tile is (0,0) at distance 1 vs (2,0) at distance 1 -> tie
    # breaks to lower coord (0,0): step WEST.
    assert mf.roam_action(pos, tiles, beat, "CARROT", 0, 0, True) == ["WEST"]


def test_roam_acts_when_standing_on_needy_tile():
    tiles = _grid(None)
    beat = [(0, 0)]
    assert mf.roam_action([0, 0], tiles, beat, "CARROT", 0, 0, True) == ["PLANT", "CARROT"]


def test_roam_passes_when_beat_fully_tended():
    tiles = _grid(None)
    beat = [(0, 0)]
    # no seed and can't plant -> nothing to do
    assert mf.roam_action([0, 0], tiles, beat, "CARROT", 0, 0, have_seed=False) == ["PASS"]


# --- animal_chore ---------------------------------------------------------

def test_animal_builds_structure_when_standing_on_empty_tile():
    tiles = _grid(None)
    assert mf.animal_chore("GOOSE", (4, 3), [4, 3], tiles, {}, {}) == ["BUILD_COOP"]
    assert mf.animal_chore("COW", (3, 3), [3, 3], tiles, {}, {}) == ["BUILD_PASTURE"]


def test_animal_places_held_animal_on_structure():
    tiles = _grid(None)
    tiles[3][4] = {"kind": "COOP"}
    assert mf.animal_chore("GOOSE", (4, 3), [4, 3], tiles, {"GOOSE": 1}, {}) == ["PLACE", "GOOSE"]


def test_animal_harvests_ready_yield_first():
    tiles = _grid(None)
    tiles[3][4] = {"kind": "COOP", "animal": "GOOSE", "yield_units": 2, "fed_today": False}
    assert mf.animal_chore("GOOSE", (4, 3), [4, 3], tiles, {}, {}) == ["HARVEST"]


def test_animal_feeds_when_hungry_and_holding_wheat():
    tiles = _grid(None)
    tiles[3][4] = {"kind": "COOP", "animal": "GOOSE", "yield_units": 0, "fed_today": False}
    assert mf.animal_chore("GOOSE", (4, 3), [4, 3], tiles, {"WHEAT": 1}, {}) == ["FEED"]


# --- plan_crew ------------------------------------------------------------

def test_plan_crew_hires_full_target_when_flush():
    assert mf.plan_crew(3000, hands_now=0, target=mf.NW_CREW - 1) == mf.NW_CREW - 1


def test_plan_crew_hires_remaining_when_partially_staffed():
    assert mf.plan_crew(3000, hands_now=2, target=5) == 3


def test_plan_crew_limited_by_money():
    # $2 covers hand 1 (wage 1) and hand 2 (wage 1); hand 3 (wage 2) unaffordable.
    assert mf.plan_crew(2, hands_now=0, target=6) == 2


# --- layout / active_workers ----------------------------------------------

def test_only_nw_workers_active_before_land_bought():
    active = mf.active_workers({"NW"})
    assert len(active) == mf.NW_CREW
    assert all(w["quad"] == "NW" for w in active)


def test_ne_workers_activate_after_land_bought():
    active = mf.active_workers({"NW", "NE"})
    assert len(active) == mf.FULL_CREW
