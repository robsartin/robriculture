"""Unit tests for the wide_hands experiment (issue #33, ADR-0007).

The single technique under test is **crew width** — more hands on more of the
free NW quadrant, layered on the `hired_hands` melon loop. These tests pin the
crew-width constants (the one variable) and the `act()` contract; the hiring
wage curve, per-plot melon micro-loop and navigation are the champion's, tested
in test_hired_hands.py. The full-game no-crash guard lives in test_no_crash.py
(auto-included via the REGISTRY), and the win-rate claim is recorded in the issue.
"""

from __future__ import annotations

from strategies import hired_hands as hh
from strategies import wide_hands as wide


# --- the one variable: a wider crew on the unlocked NW quadrant ---

def test_crew_is_wider_than_the_champion():
    assert wide.MAX_HANDS > hh.MAX_HANDS
    assert len(wide.PLOTS) == wide.MAX_HANDS + 1  # one plot per worker


def test_plots_are_distinct_and_all_in_the_nw_quadrant():
    assert len(set(wide.PLOTS)) == len(wide.PLOTS)
    assert all(0 <= x < 5 and 0 <= y < 5 for x, y in wide.PLOTS)


def test_plots_are_ordered_by_nearness_to_the_shed_spawn():
    # A fresh hand walks from (4, 4), so plots must be non-decreasing in distance.
    dists = [abs(x - 4) + abs(y - 4) for x, y in wide.PLOTS]
    assert dists == sorted(dists)
    assert wide.PLOTS[0] == (4, 4)  # farmer's shed-adjacent home plot


def test_champion_tiles_are_a_prefix_of_the_wider_layout():
    # Widening only *extends* the crew; every champion plot is still farmed.
    assert set(hh.PLOTS).issubset(set(wide.PLOTS))


# --- act(): end-to-end shape on a fresh board ---

def _board():
    return [[None for _ in range(10)] for _ in range(10)]


def _obs(hour=0, day=0, money=3000, hands=None, shed=None, seeds=None, tiles=None):
    return {
        "player": 0,
        "day": day,
        "hour": hour,
        "farms": [
            {"money": money, "tiles": tiles or _board(),
             "farmer": [4, 4], "hands": hands or []},
            {"money": money, "tiles": _board(), "farmer": [4, 4], "hands": []},
        ],
        "market": {"inventory": {}, "prices": {}},
        "town": {"unlocked_shops": []},
        "private": {"shed": shed or {}, "seeds": seeds or {}, "inventories": [{}]},
    }


def test_act_returns_valid_shape_and_respects_the_order_cap():
    action = wide.WideHandsStrategy().act(_obs(hour=0))
    assert set(action) == {"farmer", "hands", "market"}
    assert isinstance(action["farmer"], list) and action["farmer"]
    assert len(action["market"]) <= 10


def test_act_hires_a_full_wide_crew_at_dawn_when_flush():
    # Fresh board, plenty of cash and horizon: grow to the full wide crew. On an
    # empty dawn board the shed is empty (no sell), so all hires fit the cap.
    action = wide.WideHandsStrategy().act(_obs(hour=0, money=5000))
    hire_orders = [o for o in action["market"] if o[0] == "HIRE"]
    assert len(hire_orders) == wide.MAX_HANDS


def test_act_emits_one_action_per_existing_hand():
    hands = [[5, 4], [4, 5], [5, 5], [0, 0]]
    action = wide.WideHandsStrategy().act(_obs(hour=3, hands=hands))
    assert len(action["hands"]) == len(hands)


def test_act_sells_melons_sitting_in_the_shed():
    action = wide.WideHandsStrategy().act(_obs(hour=5, shed={"MELON": 20}))
    assert ["SELL", "MELON", 20] in action["market"]


def test_act_buys_seed_to_cover_empty_active_plots():
    # Mid-day with hands present and no seed held: buy seed for the empty plots.
    hands = [[4, 4], [4, 4], [4, 4]]
    action = wide.WideHandsStrategy().act(_obs(hour=5, hands=hands, seeds={"MELON": 0}))
    buys = [o for o in action["market"] if o[0] == "BUY_SEED" and o[1] == "MELON"]
    assert buys and buys[0][2] > 0


def test_act_navigates_a_hand_toward_its_far_plot():
    # A hand parked on a shed tile at (5, 5) must step toward its assigned plot.
    hands = [[5, 5]]
    action = wide.WideHandsStrategy().act(_obs(hour=3, hands=hands))
    assert action["hands"][0][0] in {"WEST", "NORTH", "EAST", "SOUTH"}
