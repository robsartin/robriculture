"""Unit tests for the catch_hands experiment (issue #27, ADR-0007).

These exercise the *pure decision helpers* — the catch-crop yield/economics
model, the full-maturity horizon gate, the catch-crop selection, the per-plot
water-then-harvest loop, and the multi-crop crew-staffing rule — so the single
technique under test (catch cropping the idle melon tail) is validated without
spinning up a full 720-turn game. Two `act()` shape tests also pin the two
plumbing changes the tail forces: the crew stays staffed while a catch crop is
plantable, and the shed SELL is emitted *before* HIRE orders (slot 0) so the
steep, shared melon market is not sold into behind our own hires.

The full-game no-crash guard lives in test_no_crash.py (auto-included via the
REGISTRY).
"""

from __future__ import annotations

from strategies import catch_hands as ch


# --- catch-crop yield & economics: watering-window model, unfertilized ---

def test_full_yield_matches_watering_window():
    # One-time crops accrue +1 per watered day in [(max_day+1)//2, max_day],
    # base 1: carrot reaches 3 (unfert), wheat 4.
    assert ch.catch_crop_full_yield("CARROT") == 3
    assert ch.catch_crop_full_yield("WHEAT") == 4


def test_gross_and_profit_use_base_price_and_seed():
    assert ch.catch_crop_gross("CARROT") == 3 * 35
    assert ch.catch_crop_profit("CARROT") == 3 * 35 - 20
    assert ch.catch_crop_profit("WHEAT") == 4 * 25 - 10


# --- cc_plantable: full maturity (age max_day) must fit before the buzzer ---

def test_catch_crop_plantable_while_it_can_fully_mature():
    # Carrot (max_day 3) planted on day 26 matures on day 29 (the final day).
    assert ch.cc_plantable("CARROT", 26) is True


def test_catch_crop_not_plantable_when_it_cannot_fully_mature():
    # Day 27 + 3 = day 30 > final day 29: it would be stranded half-grown.
    assert ch.cc_plantable("CARROT", 27) is False
    # Wheat needs 4 days, so its last full-maturity plant day is 25.
    assert ch.cc_plantable("WHEAT", 26) is False


# --- choose_catch_crop: best profit-per-occupied-day among plantable fast crops ---

def test_prefers_carrot_for_better_profit_per_day():
    # Carrot 85/3 ~= 28.3 beats wheat 90/4 = 22.5 when both fit.
    assert ch.choose_catch_crop(19) == "CARROT"


def test_falls_back_to_carrot_only_window_then_none():
    # Day 26: only carrot still fully matures (wheat needs day <= 25).
    assert ch.choose_catch_crop(26) == "CARROT"
    # Day 27: the horizon has closed on every fast crop.
    assert ch.choose_catch_crop(27) is None


# --- catch_tile_action: water-first, then harvest at full maturity ---

def test_unwatered_catch_plant_is_watered_first():
    tile = {"kind": "PLANT", "crop": "CARROT", "planted_day": 20, "yield_units": 1,
            "watered_today": False}
    assert ch.catch_tile_action(tile, day=20) == ["WATER"]


def test_watered_mature_catch_plant_is_harvested():
    # Age >= max_day (carrot 3) and already watered this day -> full-yield harvest.
    tile = {"kind": "PLANT", "crop": "CARROT", "planted_day": 20, "yield_units": 3,
            "watered_today": True}
    assert ch.catch_tile_action(tile, day=23) == ["HARVEST"]


def test_watered_immature_catch_plant_passes():
    tile = {"kind": "PLANT", "crop": "CARROT", "planted_day": 20, "yield_units": 2,
            "watered_today": True}
    assert ch.catch_tile_action(tile, day=22) == ["PASS"]


def test_mature_catch_plant_waters_before_harvest_to_capture_last_unit():
    # On the harvest day, unwatered: water first (age max_day is in-window, +1),
    # so the final unit is captured before the next-turn harvest.
    tile = {"kind": "PLANT", "crop": "CARROT", "planted_day": 20, "yield_units": 2,
            "watered_today": False}
    assert ch.catch_tile_action(tile, day=23) == ["WATER"]


# --- plan_hands_multicrop: melon phase unchanged; tail keeps the crew staffed ---

def test_melon_phase_delegates_to_champion_hiring():
    # While melon is plantable, hiring is exactly hired_hands' rule.
    day, money, live = 0, 3000, -1
    assert ch.plan_hands_multicrop(day, money, live, ch.choose_catch_crop(day)) == \
        ch.hh.plan_hands(day, money, live, ch.SEASON_DAYS, ch.MAX_HANDS)


def test_tail_grows_full_crew_while_catch_crop_plantable():
    # Melon closed (day 20) but carrots still plant: staff the full crew so there
    # are workers to plant/tend the catch crop, funds permitting.
    assert ch.plan_hands_multicrop(20, 5000, -1, "CARROT") == ch.MAX_HANDS


def test_tail_without_catch_crop_only_staffs_live_plots():
    # Horizon closed on everything (day 28): hire only enough to harvest the
    # highest live plot, nothing speculative.
    assert ch.plan_hands_multicrop(28, 5000, 2, None) == 2


def test_tail_hires_nothing_when_idle_and_no_catch_crop():
    assert ch.plan_hands_multicrop(28, 5000, -1, None) == 0


# --- act(): end-to-end shape, ordering, and tail behavior ---

def _empty_board():
    return [[None for _ in range(10)] for _ in range(10)]


def _obs(hour=0, day=0, money=3000, hands=None, board=None, shed=None, seeds=None):
    return {
        "player": 0,
        "day": day,
        "hour": hour,
        "farms": [
            {"money": money, "tiles": board or _empty_board(), "farmer": [4, 4],
             "hands": hands or []},
            {"money": money, "tiles": _empty_board(), "farmer": [4, 4], "hands": []},
        ],
        "market": {"inventory": {}, "prices": {}},
        "town": {"unlocked_shops": []},
        "private": {"shed": shed or {}, "seeds": seeds or {}, "inventories": [{}]},
    }


def test_act_sells_before_hiring_so_sell_sits_at_slot_zero():
    # The critical plumbing fix: on a melon-harvest dawn the SELL must precede the
    # HIRE orders, or the shared, steep melon market is sold into behind our hires.
    obs = _obs(hour=0, day=0, money=3000, shed={"MELON": 40})
    market = ch.CatchHandsStrategy().act(obs)["market"]
    assert market[0] == ["SELL", "MELON", 40]
    assert any(o[0] == "HIRE" for o in market)
    sell_i = market.index(["SELL", "MELON", 40])
    first_hire_i = next(i for i, o in enumerate(market) if o[0] == "HIRE")
    assert sell_i < first_hire_i


def test_act_plants_carrot_on_idle_tail_tile():
    # Day 20: melon horizon closed, a home-plot is empty -> plant the catch crop.
    obs = _obs(hour=0, day=20, money=3000, seeds={"CARROT": 5})
    action = ch.CatchHandsStrategy().act(obs)
    assert action["farmer"] == ["PLANT", "CARROT"]


def test_act_plants_melon_not_carrot_during_melon_phase():
    obs = _obs(hour=0, day=0, money=3000, seeds={"MELON": 5, "CARROT": 5})
    action = ch.CatchHandsStrategy().act(obs)
    assert action["farmer"] == ["PLANT", "MELON"]


def test_act_restocks_catch_seed_in_the_tail():
    obs = _obs(hour=0, day=20, money=3000, seeds={})
    market = ch.CatchHandsStrategy().act(obs)["market"]
    assert any(o[0] == "BUY_SEED" and o[1] == "CARROT" for o in market)


def test_act_keeps_market_within_cap():
    obs = _obs(hour=0, day=0, money=3000, shed={"MELON": 90})
    assert len(ch.CatchHandsStrategy().act(obs)["market"]) <= 10
