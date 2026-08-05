"""Tests for the multi-tile routing strategy (experiment #9, ADR-0007).

The one technique under test is *nearest-task routing* across several crop
tiles worked by a single farmer. These tests pin the pure routing helpers
(distance, one-step stepping, nearest-task selection, and the composed
route-or-execute decision) plus the managed-tile layout — the parts that carry
the experiment's variable. The economic loop (crop choice, harvest timing,
liquidation) is inherited unchanged from `greedy_horizon` and tested there.
"""

from __future__ import annotations

from strategies import routed


def test_manhattan_distance():
    assert routed.manhattan((0, 0), (0, 0)) == 0
    assert routed.manhattan((0, 0), (3, 4)) == 7
    assert routed.manhattan((4, 4), (1, 2)) == 5
    assert routed.manhattan((2, 5), (2, 1)) == 4


def test_step_toward_none_when_already_there():
    assert routed.step_toward((3, 3), (3, 3)) is None


def test_step_toward_cardinals():
    assert routed.step_toward((0, 0), (2, 0)) == "EAST"
    assert routed.step_toward((2, 0), (0, 0)) == "WEST"
    assert routed.step_toward((0, 0), (0, 2)) == "SOUTH"
    assert routed.step_toward((0, 2), (0, 0)) == "NORTH"


def test_step_toward_moves_along_larger_gap_first():
    # dx (3) dominates dy (1): close the wider gap first.
    assert routed.step_toward((0, 0), (3, 1)) == "EAST"
    # dy (4) dominates dx (2): move vertically first.
    assert routed.step_toward((0, 0), (2, 4)) == "SOUTH"


def test_step_toward_tie_breaks_horizontal():
    # Equal gaps -> deterministic horizontal-first tie-break.
    assert routed.step_toward((0, 0), (2, 2)) == "EAST"
    assert routed.step_toward((2, 2), (0, 0)) == "WEST"


def test_nearest_task_none_when_empty():
    assert routed.nearest_task((4, 4), []) is None


def test_nearest_task_picks_closest():
    tasks = [
        ((0, 0), ["WATER"]),
        ((4, 3), ["HARVEST"]),
        ((2, 2), ["WATER"]),
    ]
    # From (4,4): distances 8, 1, 4 -> the HARVEST at (4,3) wins.
    assert routed.nearest_task((4, 4), tasks) == ((4, 3), ["HARVEST"])


def test_nearest_task_deterministic_tie_break():
    # Both one step away; tie broken by target coordinate (x then y).
    tasks = [
        ((5, 4), ["WATER"]),
        ((4, 3), ["WATER"]),
    ]
    assert routed.nearest_task((4, 4), tasks) == ((4, 3), ["WATER"])


def test_route_action_pass_when_no_tasks():
    assert routed.route_action((4, 4), []) == ["PASS"]


def test_route_action_executes_when_on_tile():
    tasks = [((4, 4), ["HARVEST"]), ((0, 0), ["WATER"])]
    assert routed.route_action((4, 4), tasks) == ["HARVEST"]


def test_route_action_steps_toward_nearest():
    tasks = [((4, 1), ["WATER"]), ((0, 0), ["WATER"])]
    # Nearest is (4,1) at distance 3; step north toward it.
    assert routed.route_action((4, 4), tasks) == ["NORTH"]


def test_managed_tiles_layout():
    tiles = routed.managed_tiles(4)
    assert len(tiles) == 4
    # The shed-adjacent drop tile is always managed and comes first (distance 0).
    assert tiles[0] == routed.SHED_TILE == (4, 4)
    # Every managed tile sits inside the unlocked NW quadrant.
    for (x, y) in tiles:
        assert 0 <= x <= 4 and 0 <= y <= 4
    # No duplicates, and ordered nearest-first by distance to the shed.
    assert len(set(tiles)) == len(tiles)
    dists = [routed.manhattan(routed.SHED_TILE, t) for t in tiles]
    assert dists == sorted(dists)


def test_managed_tiles_are_a_prefix():
    # Asking for more tiles extends the same nearest-first ordering.
    assert routed.managed_tiles(6)[:4] == routed.managed_tiles(4)
