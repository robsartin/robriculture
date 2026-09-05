"""The ghost: a real ladder rival replayed move for move (issue #204).

Every test here guards one of the two traps #157 paid for: the action recorded
at replay index `t` belongs to the observation at index `t-1`, and a ghost must
never invent a move it did not make.
"""

from __future__ import annotations

from strategies import REGISTRY
from strategies.ghost import PASS, Ghost, replay_actions, turn_index

A1 = {"farmer": ["NORTH"], "hands": [], "market": []}
A2 = {"farmer": ["PLANT", "MELON"], "hands": [], "market": [["SELL", "MELON", 3]]}


def _steps(p0_actions, p1_actions):
    """A minimal replay `steps` table: steps[t][player]['action']."""
    return [
        [{"action": a0, "observation": {}}, {"action": a1, "observation": {}}]
        for a0, a1 in zip(p0_actions, p1_actions)
    ]


def test_replay_actions_returns_one_players_actions_in_replay_index_order():
    """The script is indexed by replay index, so index 0 is the pre-game slot."""
    steps = _steps([None, A1, A2], [None, A2, A1])
    assert replay_actions(steps, 1) == [None, A2, A1]


def test_replay_actions_drops_non_dict_actions_when_a_slot_is_malformed():
    """A missing or malformed action is None, never a guess at what was played."""
    steps = _steps([None, "TIMEOUT", A1], [None, None, None])
    assert replay_actions(steps, 0) == [None, None, A1]


def test_turn_index_is_one_past_the_observed_step_when_obs_carries_step():
    """Trap #157: the action at index t was applied to the observation at t-1,
    so an agent looking at obs.step==t-1 owes the action recorded at index t."""
    assert turn_index({"step": 288}, fallback=1) == 289


def test_turn_index_falls_back_to_the_call_counter_when_step_is_absent():
    """Player 1's stored observation has no `step`; the counter is self-sufficient."""
    assert turn_index({"day": 3}, fallback=7) == 7


def test_ghost_replays_the_action_recorded_one_index_past_the_observation():
    """The whole point: obs.step==1 must return the action at replay index 2."""
    ghost = Ghost([None, A1, A2])
    assert ghost.act({"step": 1}) == A2


def test_ghost_passes_when_the_script_has_run_out():
    """A ghost never improvises: past the end of its replay it does nothing."""
    ghost = Ghost([None, A1])
    assert ghost.act({"step": 5}) == PASS


def test_ghost_uses_its_own_call_count_when_the_observation_has_no_step():
    """First call is the transition into index 1, second into index 2."""
    ghost = Ghost([None, A1, A2])
    assert ghost.act({}) == A1
    assert ghost.act({}) == A2


def test_ghost_is_flagged_a_benchmark_so_it_can_never_be_submitted():
    """A measurement opponent: scripts/submit.py refuses to package it (ADR-0005)."""
    assert Ghost.benchmark is True


def test_ghost_is_not_in_the_strategy_registry():
    """A ghost has no behaviour without a replay, so there is no module-level
    STRATEGY to register: a scriptless ghost would be a PASS bot sitting in the
    tournament and in tests/test_no_crash.py's sanity floor."""
    assert "ghost" not in REGISTRY


def test_from_replay_scripts_the_named_player_not_the_other_one():
    """Picking the wrong seat gives a ghost of ourselves; assert the seat."""
    replay = {"steps": _steps([None, A1], [None, A2])}
    assert Ghost.from_replay(replay, 1).act({"step": 0}) == A2
    assert Ghost.from_replay(replay, 0).act({"step": 0}) == A1


def test_ghost_passes_on_a_slot_the_replay_did_not_record():
    """A timeout mid-episode is a None slot: the ghost does nothing there
    rather than sliding the rest of the script forward by one turn."""
    ghost = Ghost([None, A1, None, A2])
    assert ghost.act({"step": 1}) == PASS
    assert ghost.act({"step": 2}) == A2


def test_reset_puts_a_reused_ghost_back_at_the_start_of_its_script():
    """The counter fallback desyncs if a ghost is reused across episodes."""
    ghost = Ghost([None, A1, A2])
    ghost.act({})
    ghost.reset()
    assert ghost.act({}) == A1
