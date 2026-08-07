"""Unit tests for the fertilized_hands experiment (issue #26, ADR-0007).

These exercise the *pure fertilizer helpers* layered on top of `hired_hands` —
"is this melon worth fertilizing right now?", the buy/pickup/apply supply chain,
and the farmer's per-turn fertilize decision — so the single technique under test
(fertilize melon tiles to reach the yield cap sooner) is validated without a full
720-turn game. The full-game no-crash guard lives in test_no_crash.py (auto-
included via the REGISTRY).

`hired_hands` behaviour it builds on (hiring, navigation, watering, selling) is
already covered by test_hired_hands.py; these tests focus on the delta.
"""

from __future__ import annotations

from strategies import fertilized_hands as fh


def _melon(planted_day=0, yield_units=2, fertilized_until_day=-1, watered=False):
    return {
        "kind": "PLANT",
        "crop": "MELON",
        "planted_day": planted_day,
        "yield_units": yield_units,
        "fertilized_until_day": fertilized_until_day,
        "watered_today": watered,
    }


# --- wants_fertilizer: a live melon in its growth window, not yet capped/covered ---

def test_wants_fertilizer_true_at_window_start():
    # Age 6 is the first day a WATER accrues yield (window_start = (12+1)//2).
    assert fh.wants_fertilizer(_melon(planted_day=0), day=6) is True


def test_no_fertilizer_before_the_growth_window():
    # Age 5: watering does not accrue yield yet, so fertilizer buys nothing.
    assert fh.wants_fertilizer(_melon(planted_day=0), day=5) is False


def test_no_fertilizer_after_the_yield_window():
    # Past max_yield_day (12): no further growth, so no point fertilizing.
    assert fh.wants_fertilizer(_melon(planted_day=0), day=13) is False


def test_no_fertilizer_once_yield_is_capped():
    assert fh.wants_fertilizer(_melon(planted_day=0, yield_units=6), day=7) is False


def test_no_fertilizer_while_still_covered():
    # Already fertilized through day 8: re-applying now would waste a unit.
    tile = _melon(planted_day=0, fertilized_until_day=8)
    assert fh.wants_fertilizer(tile, day=7) is False


def test_wants_fertilizer_again_once_coverage_lapses():
    tile = _melon(planted_day=0, fertilized_until_day=6)
    assert fh.wants_fertilizer(tile, day=7) is True


def test_no_fertilizer_when_horizon_closed_on_the_melon():
    # Planted too late to ever be harvested (harvest gated at first_yield_day=10);
    # fertilizing a melon that never sells is pure waste.
    tile = _melon(planted_day=22)
    assert fh.wants_fertilizer(tile, day=28) is False  # age 6 but harvest day 32 > 29


def test_no_fertilizer_for_non_melon_tiles():
    assert fh.wants_fertilizer(None, day=7) is False
    assert fh.wants_fertilizer({"kind": "WEED"}, day=7) is False
    assert fh.wants_fertilizer({"kind": "PLANT", "crop": "WHEAT",
                                "planted_day": 0, "yield_units": 2}, day=7) is False


# --- have_fertilizer: does this worker's inventory hold a unit to apply? ---

def test_have_fertilizer_reads_worker_inventory():
    assert fh.have_fertilizer({"FERTILIZER": 1}) is True
    assert fh.have_fertilizer({"FERTILIZER": 0}) is False
    assert fh.have_fertilizer({}) is False


# --- fertilize_or_fetch: apply from inventory, else pick up from the shed ---

def test_fertilize_from_inventory_when_held():
    action = fh.fertilize_or_fetch(_melon(), day=6, inv={"FERTILIZER": 1}, shed={})
    assert action == ["FERTILIZE"]


def test_pickup_from_shed_when_stocked_but_not_held():
    action = fh.fertilize_or_fetch(_melon(), day=6, inv={}, shed={"FERTILIZER": 2})
    assert action == ["PICKUP", "FERTILIZER", 1]


def test_no_fertilize_action_when_none_available_anywhere():
    assert fh.fertilize_or_fetch(_melon(), day=6, inv={}, shed={}) is None


def test_no_fertilize_action_when_melon_does_not_want_it():
    # Capped melon: neither apply nor fetch.
    tile = _melon(yield_units=6)
    assert fh.fertilize_or_fetch(tile, day=6, inv={"FERTILIZER": 1}, shed={"FERTILIZER": 1}) is None


# --- should_buy_fertilizer: restock the shed only when a melon needs it ---

def test_buys_when_wanted_and_out_of_stock_and_affordable():
    assert fh.should_buy_fertilizer(_melon(), day=6, shed={}, inv={}, money=3000) is True


def test_no_buy_when_shed_already_stocked():
    assert fh.should_buy_fertilizer(_melon(), day=6, shed={"FERTILIZER": 1}, inv={}, money=3000) is False


def test_no_buy_when_worker_already_holds_fertilizer():
    assert fh.should_buy_fertilizer(_melon(), day=6, shed={}, inv={"FERTILIZER": 1}, money=3000) is False


def test_no_buy_when_unaffordable():
    assert fh.should_buy_fertilizer(_melon(), day=6, shed={}, inv={}, money=5) is False


def test_no_buy_when_no_melon_wants_fertilizer():
    assert fh.should_buy_fertilizer(_melon(yield_units=6), day=6, shed={}, inv={}, money=3000) is False


# --- act(): the fertilizer delta on the farmer's shed-adjacent plot (4, 4) ---

def _obs(hour=0, day=0, money=3000, hands=None, farmer_tile=None, shed=None,
         farmer_inv=None):
    board = [[None for _ in range(10)] for _ in range(10)]
    if farmer_tile is not None:
        fx, fy = fh.PLOTS[0]
        board[fy][fx] = farmer_tile
    inventories = [farmer_inv or {}]
    return {
        "player": 0,
        "day": day,
        "hour": hour,
        "farms": [
            {"money": money, "tiles": board, "farmer": list(fh.PLOTS[0]), "hands": hands or []},
            {"money": money, "tiles": [[None] * 10 for _ in range(10)], "farmer": [4, 4], "hands": []},
        ],
        "market": {"inventory": {}, "prices": {}},
        "town": {"unlocked_shops": []},
        "private": {"shed": shed or {}, "seeds": {"MELON": 5}, "inventories": inventories},
    }


def test_farmer_fertilizes_its_melon_when_holding_fertilizer():
    obs = _obs(hour=3, day=6, farmer_tile=_melon(planted_day=0, watered=True),
               farmer_inv={"FERTILIZER": 1})
    action = fh.FertilizedHandsStrategy().act(obs)
    assert action["farmer"] == ["FERTILIZE"]


def test_farmer_picks_up_fertilizer_from_shed_when_stocked():
    obs = _obs(hour=3, day=6, farmer_tile=_melon(planted_day=0, watered=True),
               shed={"FERTILIZER": 1})
    action = fh.FertilizedHandsStrategy().act(obs)
    assert action["farmer"] == ["PICKUP", "FERTILIZER", 1]


def test_farmer_buys_fertilizer_when_a_melon_wants_it_and_stock_is_empty():
    obs = _obs(hour=3, day=6, farmer_tile=_melon(planted_day=0, watered=True))
    action = fh.FertilizedHandsStrategy().act(obs)
    assert ["BUY_PRODUCT", "FERTILIZER", 1] in action["market"]


def test_farmer_waters_when_melon_does_not_want_fertilizer():
    # Unwatered melon before the growth window: behaves exactly like hired_hands.
    obs = _obs(hour=3, day=4, farmer_tile=_melon(planted_day=0, yield_units=1, watered=False))
    action = fh.FertilizedHandsStrategy().act(obs)
    assert action["farmer"] == ["WATER"]


def test_still_hires_a_crew_at_dawn():
    action = fh.FertilizedHandsStrategy().act(_obs(hour=0))
    hire_orders = [o for o in action["market"] if o[0] == "HIRE"]
    assert len(hire_orders) == fh.MAX_HANDS
    assert len(action["market"]) <= 10


def test_still_sells_melons_sitting_in_the_shed():
    obs = _obs(hour=5, shed={"MELON": 9})
    action = fh.FertilizedHandsStrategy().act(obs)
    assert ["SELL", "MELON", 9] in action["market"]


def test_unique_name_and_registered():
    from strategies import REGISTRY
    assert fh.FertilizedHandsStrategy.name == "fertilized_hands"
    assert "fertilized_hands" in REGISTRY
