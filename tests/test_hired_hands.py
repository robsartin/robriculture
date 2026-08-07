"""Unit tests for the hired_hands experiment (issue #6, ADR-0007).

These exercise the *pure decision helpers* — the hiring wage curve, the dynamic
crew-sizing rule (marginal output vs wage), plot navigation, and the per-plot
melon micro-loop — so the single technique under test (dynamic farm-hand hiring)
is validated without spinning up a full 720-turn game. The full-game no-crash
guard lives in test_no_crash.py (auto-included via the REGISTRY).
"""

from __future__ import annotations

from strategies import hired_hands as hh


# --- Hiring wage curve: fib(k-1), matching the sim's per-day escalation ---

def test_hand_wage_follows_fibonacci_from_one():
    # First hand of the day is cheapest; cost escalates as fib.
    assert [hh.hand_wage(k) for k in range(1, 8)] == [1, 1, 2, 3, 5, 8, 13]


def test_hand_wage_scales_with_mult():
    assert hh.hand_wage(4, mult=10) == 30  # fib(3)=3 * 10


# --- melon_tile_value: worth a fresh plot, unless the horizon closed on it ---

def test_fresh_melon_tile_has_positive_value_early():
    assert hh.melon_tile_value(0) > 0


def test_melon_tile_worthless_once_it_cannot_mature():
    # Melon needs ~10 days to first yield plus a day to sell; day 25 is too late.
    assert hh.melon_tile_value(25) == 0.0


# --- plan_hands: the marginal-output-vs-wage crew-sizing rule ---

def test_hires_full_crew_early_when_flush_and_plantable():
    # Flush with cash, plenty of horizon: grow to the full crew.
    assert hh.plan_hands(0, 3000, max_live=-1) == hh.MAX_HANDS


def test_stops_growing_once_horizon_closes_but_keeps_live_plots_staffed():
    # Late season: can't plant a new melon, but two live plots (indices 0..2)
    # still need watering -> staff up to the highest live index.
    assert hh.plan_hands(25, 3000, max_live=2) == 2


def test_no_new_hires_at_end_when_nothing_alive():
    # Horizon closed and no live plots: paying for a hand earns nothing.
    assert hh.plan_hands(25, 3000, max_live=-1) == 0


def test_broke_farm_hires_what_it_can_afford():
    # $2 buys hand 1 (wage 1) and hand 2 (wage 1); hand 3 (wage 2) is unaffordable.
    assert hh.plan_hands(0, 2, max_live=-1) == 2


def test_marginal_gate_stops_when_wage_exceeds_tile_value():
    # With a huge cap and cash but every hand covering a *new* plot, hiring stops
    # once the escalating wage would exceed a fresh melon tile's value (~1420).
    hired = hh.plan_hands(0, 10_000, max_live=-1, max_hands=40)
    wage_at_stop = hh.hand_wage(hired + 1)
    assert wage_at_stop >= hh.melon_tile_value(0)
    assert hh.hand_wage(hired) < hh.melon_tile_value(0)


# --- harvest_ready: mature, yielding melon only ---

def test_harvest_ready_true_for_mature_yielding_melon():
    tile = {"kind": "PLANT", "crop": "MELON", "planted_day": 0, "yield_units": 6}
    assert hh.harvest_ready(tile, day=10) is True


def test_not_harvest_ready_before_first_yield_day():
    tile = {"kind": "PLANT", "crop": "MELON", "planted_day": 0, "yield_units": 3}
    assert hh.harvest_ready(tile, day=5) is False


def test_not_harvest_ready_with_no_yield():
    tile = {"kind": "PLANT", "crop": "MELON", "planted_day": 0, "yield_units": 0}
    assert hh.harvest_ready(tile, day=12) is False


def test_harvest_ready_false_for_non_plant_tiles():
    assert hh.harvest_ready(None, day=12) is False
    assert hh.harvest_ready({"kind": "WEED"}, day=12) is False


# --- tile_action: the per-plot melon micro-loop ---

def test_empty_plot_plants_melon_when_plantable():
    assert hh.tile_action(None, day=0, hour=0) == ["PLANT", "MELON"]


def test_empty_plot_passes_once_horizon_closes():
    assert hh.tile_action(None, day=25, hour=0) == ["PASS"]


def test_empty_plot_does_not_plant_on_last_turn_of_day():
    # A melon planted on the final turn dies unwatered overnight.
    last = hh.TURNS_PER_DAY - 1
    assert hh.tile_action(None, day=0, hour=last) == ["PASS"]


def test_weed_gets_dug():
    assert hh.tile_action({"kind": "WEED"}, day=3, hour=0) == ["DIG"]


def test_unwatered_live_plant_gets_watered():
    tile = {"kind": "PLANT", "crop": "MELON", "planted_day": 3, "yield_units": 1,
            "watered_today": False}
    assert hh.tile_action(tile, day=4, hour=0) == ["WATER"]


def test_watered_immature_plant_passes():
    tile = {"kind": "PLANT", "crop": "MELON", "planted_day": 3, "yield_units": 1,
            "watered_today": True}
    assert hh.tile_action(tile, day=4, hour=0) == ["PASS"]


def test_mature_plant_is_harvested():
    tile = {"kind": "PLANT", "crop": "MELON", "planted_day": 0, "yield_units": 6,
            "watered_today": True}
    assert hh.tile_action(tile, day=10, hour=0) == ["HARVEST"]


# --- step_toward: greedy x-then-y navigation to a plot ---

def test_step_toward_moves_west_then_north():
    # From a shed-access spawn at (5, 5) toward plot (2, 3): x first (west),
    # then y (north), then arrive.
    assert hh.step_toward((5, 5), (2, 3)) == ["WEST"]
    assert hh.step_toward((2, 5), (2, 3)) == ["NORTH"]
    assert hh.step_toward((2, 3), (2, 3)) == ["PASS"]


def test_step_toward_moves_east_and_south():
    assert hh.step_toward((0, 0), (4, 4)) == ["EAST"]
    assert hh.step_toward((4, 0), (4, 4)) == ["SOUTH"]


# --- max_live_index: which plots need staffing ---

def _empty_board():
    return [[None for _ in range(10)] for _ in range(10)]


def test_max_live_index_minus_one_on_empty_board():
    assert hh.max_live_index(_empty_board()) == -1


def test_max_live_index_finds_highest_live_plot():
    board = _empty_board()
    for idx in (0, 3):
        x, y = hh.PLOTS[idx]
        board[y][x] = {"kind": "PLANT", "crop": "MELON"}
    assert hh.max_live_index(board) == 3


def test_plots_are_distinct_and_in_nw_quadrant():
    # No two workers share a plot, and every plot is in the unlocked NW quadrant.
    assert len(set(hh.PLOTS)) == len(hh.PLOTS)
    assert len(hh.PLOTS) == hh.MAX_HANDS + 1
    assert all(0 <= x < 5 and 0 <= y < 5 for x, y in hh.PLOTS)


# --- act(): end-to-end shape on a fresh board ---

def _fresh_obs(hour=0, day=0, money=3000, hands=None):
    board = _empty_board()
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
        "private": {"shed": {}, "seeds": {}, "inventories": [{}]},
    }


def test_act_hires_crew_and_returns_valid_shape_at_dawn():
    action = hh.HiredHandsStrategy().act(_fresh_obs(hour=0))
    assert action["farmer"][0] in {"PLANT", "PASS", "WATER"}
    assert action["hands"] == []  # no hands exist yet at hour 0
    hire_orders = [o for o in action["market"] if o[0] == "HIRE"]
    assert len(hire_orders) == hh.MAX_HANDS
    assert len(action["market"]) <= 10


def test_act_emits_one_action_per_existing_hand():
    hands = [[5, 4], [4, 5], [5, 5]]
    action = hh.HiredHandsStrategy().act(_fresh_obs(hour=3, hands=hands))
    assert len(action["hands"]) == len(hands)
    assert isinstance(action["farmer"], list) and action["farmer"]  # farmer acts


def test_act_sells_melons_sitting_in_the_shed():
    obs = _fresh_obs(hour=5)
    obs["private"]["shed"] = {"MELON": 12}
    action = hh.HiredHandsStrategy().act(obs)
    assert ["SELL", "MELON", 12] in action["market"]
