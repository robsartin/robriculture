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


# --- step_toward / _at_shed navigation primitives -------------------------

def test_step_toward_directions_and_pass():
    """x is closed before y; arriving yields PASS."""
    assert mf.step_toward((0, 0), (2, 0)) == ["EAST"]
    assert mf.step_toward((2, 0), (0, 0)) == ["WEST"]
    assert mf.step_toward((0, 0), (0, 2)) == ["SOUTH"]
    assert mf.step_toward((0, 2), (0, 0)) == ["NORTH"]
    assert mf.step_toward((1, 1), (1, 1)) == ["PASS"]


def test_at_shed_true_only_on_corner():
    """`_at_shed` recognises exactly the shed-access corner."""
    assert mf._at_shed([4, 4]) is True
    assert mf._at_shed([0, 0]) is False


# --- max_sellable / price_aware_sell_orders edge branches -----------------

def test_max_sellable_unknown_item_is_zero():
    """An item with no market params can never be sold."""
    assert mf.max_sellable("NOT_A_PRODUCT", 0, 0.5) == 0


def test_price_aware_skips_non_market_zero_and_buffered_items():
    """Non-products, empty piles, and sub-buffer wheat are all held back."""
    shed = {
        "FISH": 5,                              # not a market product
        "CARROT": 0,                            # nothing on hand
        "WHEAT": mf.WHEAT_FEED_BUFFER - 1,      # below the feed reserve
        "MELON": 5,                             # genuinely sellable
    }
    orders = mf.price_aware_sell_orders(shed, {})
    items = {o[1] for o in orders}
    assert "FISH" not in items
    assert "CARROT" not in items
    assert "WHEAT" not in items
    assert "MELON" in items


# --- crop_tile_chore: remaining edge tiles --------------------------------

def test_crop_tile_chore_edge_tiles_return_none():
    """Non-dict tiles, foreign structures, unknown crops, and nothing-ready
    plants all yield no chore."""
    assert mf.crop_tile_chore("dirt", "MELON", 0, 0, False) is None
    assert mf.crop_tile_chore({"kind": "COOP"}, "MELON", 0, 0, False) is None
    assert mf.crop_tile_chore({"kind": "PLANT", "crop": "ZZ"}, "MELON", 0, 0, False) is None
    watered_no_yield = {"kind": "PLANT", "crop": "TOMATO", "planted_day": 0,
                        "watered_today": True, "yield_units": 0}
    assert mf.crop_tile_chore(watered_no_yield, "TOMATO", 9, 0, False) is None


# --- empty_tiles ----------------------------------------------------------

def test_empty_tiles_counts_none_tiles_in_beat():
    tiles = _grid(None)
    tiles[0][1] = {"kind": "PLANT"}
    beat = [(0, 0), (1, 0), (2, 0)]
    assert mf.empty_tiles(tiles, beat) == 2


# --- animal_chore: structure / feed-from-shed / care branches -------------

def test_animal_picks_up_from_shed_when_structure_built():
    """Coop built but empty: fetch the animal out of the shed, or walk there."""
    tiles = _grid(None)
    tiles[3][4] = {"kind": "COOP"}
    assert mf.animal_chore("GOOSE", (4, 3), [4, 4], tiles, {}, {"GOOSE": 2}) == ["PICKUP", "GOOSE", 1]
    away = mf.animal_chore("GOOSE", (4, 3), [0, 0], tiles, {}, {"GOOSE": 2})
    assert away[0] in {"EAST", "WEST", "NORTH", "SOUTH"}
    assert mf.animal_chore("GOOSE", (4, 3), [4, 4], tiles, {}, {}) is None


def test_animal_fetches_wheat_from_shed_when_hungry():
    """Hungry animal, no wheat in hand: pull a feed batch from the shed."""
    tiles = _grid(None)
    tiles[3][4] = {"kind": "COOP", "animal": "GOOSE", "yield_units": 0, "fed_today": False}
    assert mf.animal_chore("GOOSE", (4, 3), [4, 4], tiles, {}, {"WHEAT": 10}) == [
        "PICKUP", "WHEAT", mf.FEED_BATCH]
    away = mf.animal_chore("GOOSE", (4, 3), [0, 0], tiles, {}, {"WHEAT": 10})
    assert away[0] in {"EAST", "WEST", "NORTH", "SOUTH"}
    # Hungry but no wheat anywhere -> nothing to do.
    assert mf.animal_chore("GOOSE", (4, 3), [4, 3], tiles, {}, {}) is None


def test_animal_cares_only_when_fed_and_standing_on_it():
    tiles = _grid(None)
    tiles[3][4] = {"kind": "COOP", "animal": "GOOSE", "yield_units": 0,
                   "fed_today": True, "cared_today": False}
    assert mf.animal_chore("GOOSE", (4, 3), [4, 3], tiles, {}, {}) == ["CARE"]
    tiles[3][4]["cared_today"] = True
    assert mf.animal_chore("GOOSE", (4, 3), [4, 3], tiles, {}, {}) is None


# --- animal_worker_action -------------------------------------------------

def test_animal_worker_grabs_feed_at_shed_proactively():
    tiles = _grid(None)
    tiles[3][4] = {"kind": "COOP", "animal": "GOOSE", "yield_units": 0, "fed_today": False}
    assignments = [((4, 3), "GOOSE")]
    assert mf.animal_worker_action([4, 4], tiles, {}, {"WHEAT": 10}, assignments, day=1) == [
        "PICKUP", "WHEAT", mf.FEED_BATCH]


def test_animal_worker_services_nearest_then_idles_toward_shed():
    tiles = _grid(None)
    assignments = [((4, 3), "GOOSE")]
    # Empty tile, standing on it: build the coop.
    assert mf.animal_worker_action([4, 3], tiles, {}, {}, assignments, day=1) == ["BUILD_COOP"]
    # Fully-tended animal: nothing to service, so idle toward the shed.
    tiles[3][4] = {"kind": "COOP", "animal": "GOOSE", "yield_units": 0,
                   "fed_today": True, "cared_today": True}
    idle = mf.animal_worker_action([0, 0], tiles, {}, {}, assignments, day=1)
    assert idle[0] in {"EAST", "WEST", "NORTH", "SOUTH", "PASS"}


# --- _owns ----------------------------------------------------------------

def test_owns_counts_placed_shed_and_hand():
    tiles = _grid(None)
    tiles[3][3] = {"kind": "PASTURE", "animal": "COW"}
    assignments = [((3, 3), "COW"), ((2, 4), "COW")]
    shed = {"COW": 1}
    inventories = [{"COW": 2}, {}]
    assert mf._owns("COW", tiles, assignments, shed, inventories) == 1 + 1 + 2


# --- act(): end-to-end obs shaping ----------------------------------------

def _board(w=10, h=10):
    return [[None for _ in range(w)] for _ in range(h)]


def _obs(*, hour=0, day=0, money=3000, farmer=None, hands=None, tiles=None,
         seeds=None, shed=None, inventories=None, market_inv=None,
         unlocked=None, player=0):
    board = tiles if tiles is not None else _board()
    me = {
        "money": money,
        "tiles": board,
        "farmer": farmer or [4, 4],
        "hands": hands or [],
        "unlocked_quadrants": unlocked or ["NW"],
    }
    other = {"money": money, "tiles": _board(), "farmer": [4, 4], "hands": []}
    return {
        "player": player,
        "day": day,
        "hour": hour,
        "farms": [me, other],
        "market": {"inventory": market_inv or {}, "prices": {}},
        "town": {"unlocked_shops": []},
        "private": {
            "seeds": seeds or {},
            "shed": shed or {},
            "inventories": inventories or [{}],
        },
    }


def _run(**kw):
    return mf.MarketFarmerStrategy().act(_obs(**kw))


def test_act_hires_active_crew_at_dawn():
    """At dawn the whole active crew (minus the farmer) is queued to hire."""
    action = _run(hour=0, money=3000)
    hires = [o for o in action["market"] if o[0] == "HIRE"]
    assert len(hires) == mf.NW_CREW - 1
    assert action["hands"] == []
    assert isinstance(action["farmer"], list) and action["farmer"]
    assert len(action["market"]) <= 10


def test_act_midday_no_hiring_and_one_action_per_hand():
    """Off-dawn hours never hire and emit exactly one action per hand."""
    hands = [[0, 0], [1, 2]]
    action = _run(hour=5, hands=hands, seeds={"MELON": 5, "CARROT": 5})
    assert not any(o[0] == "HIRE" for o in action["market"])
    assert len(action["hands"]) == len(hands)


def test_act_emits_price_aware_sells_and_throttles_trap_market():
    """Deep markets clear; the MELON trap is throttled below what's on hand."""
    shed = {"CARROT": 60, "MELON": 200, "WHEAT": 40}
    action = _run(hour=6, shed=shed)
    sells = {o[1]: o[2] for o in action["market"] if o[0] == "SELL"}
    assert "CARROT" in sells
    assert 0 < sells.get("MELON", 0) < 200


def test_act_does_not_dump_into_a_flooded_market():
    """A shared market already in glut receives no fresh MELON sells."""
    shed = {"MELON": 50}
    flooded = {"MELON": economy.MARKET_PARAMS["MELON"]["I0"] + 5000}
    action = _run(hour=6, shed=shed, market_inv=flooded)
    assert all(o[1] != "MELON" for o in action["market"] if o[0] == "SELL")


def test_act_buys_ne_land_when_flush_and_early():
    action = _run(hour=6, money=2000, shed={})
    assert ["BUY_LAND"] in action["market"]


def test_act_with_ne_unlocked_staffs_full_crew_and_skips_land_buy():
    action = _run(hour=0, money=5000, unlocked=["NW", "NE"])
    assert not any(o[0] == "BUY_LAND" for o in action["market"])
    hires = [o for o in action["market"] if o[0] == "HIRE"]
    assert len(hires) == mf.FULL_CREW - 1


def test_act_restocks_seed_for_empty_beats():
    action = _run(hour=6, money=3000, shed={})
    assert any(o[0] == "BUY_SEED" for o in action["market"])


def test_act_animal_worker_harvests_placed_animal():
    """With enough hands to reach an animal worker, a ready coop is harvested."""
    tiles = _board()
    tiles[3][4] = {"kind": "COOP", "animal": "GOOSE", "yield_units": 2,
                   "fed_today": True, "cared_today": True}
    hands = [[0, 0], [0, 2], [3, 0], [4, 3], [3, 3]]
    action = _run(hour=6, hands=hands, tiles=tiles,
                  seeds={"MELON": 99, "CARROT": 99, "TOMATO": 99, "WHEAT": 99})
    assert action["hands"][3] == ["HARVEST"]


def test_act_buys_staggered_animals_when_capitalized():
    """Geese seed the flock; sheep only after a cow is already owned."""
    tiles = _board()
    tiles[3][3] = {"kind": "PASTURE", "animal": "COW"}
    action = _run(hour=6, day=6, money=5000, tiles=tiles, shed={},
                  seeds={"MELON": 99, "CARROT": 99, "TOMATO": 99, "WHEAT": 99})
    kinds = [o[1] for o in action["market"] if o[0] == "BUY_ANIMAL"]
    assert "GOOSE" in kinds
    assert "SHEEP" in kinds


def test_act_tops_up_wheat_feed_when_flock_alive_and_short():
    tiles = _board()
    tiles[3][4] = {"kind": "COOP", "animal": "GOOSE", "yield_units": 0, "fed_today": True}
    action = _run(hour=6, money=3000, tiles=tiles, shed={},
                  seeds={"MELON": 99, "CARROT": 99, "TOMATO": 99, "WHEAT": 99})
    assert any(o[0] == "BUY_PRODUCT" and o[1] == "WHEAT" for o in action["market"])


def test_act_demotes_surplus_plant_to_pass_when_seed_short():
    """Two duplicate wheat workers on empty tiles with a single seed: one plants,
    the other is demoted to PASS so the sim never voids the real plant."""
    tiles = _board()
    hands = [[0, 0]] * 5 + [[5, 2], [5, 0]]  # positions 6 & 7 -> the two NE wheat beats
    action = _run(hour=6, hands=hands, tiles=tiles,
                  seeds={"WHEAT": 1}, unlocked=["NW", "NE"])
    plants = [a for a in action["hands"] if a[:2] == ["PLANT", "WHEAT"]]
    assert len(plants) == 1
    assert ["PASS"] in action["hands"]


def test_animal_chore_returns_none_on_foreign_tile():
    """A non-animal, non-structure tile where an animal belongs is left alone."""
    tiles = _grid(None)
    tiles[3][4] = {"kind": "WEED"}
    assert mf.animal_chore("GOOSE", (4, 3), [4, 3], tiles, {}, {"GOOSE": 0}) is None


def test_act_skips_seed_when_unplantable_and_skips_animals_late():
    """Past the horizon, unplantable crops buy no seed and no animals are bought."""
    action = _run(hour=6, day=20, money=5000, shed={},
                  unlocked=["NW"])
    assert not any(o[:2] == ["BUY_SEED", "MELON"] for o in action["market"])
    assert not any(o[0] == "BUY_ANIMAL" for o in action["market"])


def test_act_skips_seed_buy_when_unaffordable():
    """Empty beats want seed but a near-broke farm can afford none."""
    action = _run(hour=6, money=5, shed={})
    assert not any(o[0] == "BUY_SEED" for o in action["market"])


def test_act_falls_back_to_last_spec_when_more_hands_than_workers():
    """Extra hands beyond the active roster reuse the final worker spec safely."""
    hands = [[x, 0] for x in range(9)]  # 9 hands + farmer = 10 positions > NW crew (6)
    action = _run(hour=6, hands=hands)
    assert len(action["hands"]) == len(hands)
    assert all(isinstance(a, list) and a for a in action["hands"])
