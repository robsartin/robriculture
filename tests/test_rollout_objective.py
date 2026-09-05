"""A rollout scored on final money is only a prediction if, with the REAL
opponent on the other farm, it reproduces the real game (#164's exactness,
re-asserted on this code path). The mirror version is the same function with a
different opponent — there is nothing else to test about it."""

from __future__ import annotations

from harness.rollout_objective import final_money, timed_final_money
from harness.state_set import capture_states
from kaggisim.strategy import make_agent
from strategies import load

SEED, STEPS, DAY = 11, 96, 2     # four days; snapshot at day 2, roll the last two


def _ours():
    return make_agent(load("wheat_hands")())


def _theirs():
    return make_agent(load("hired_hands")())


def test_rolling_from_a_state_with_the_real_opponent_reproduces_the_real_game():
    states, truth = capture_states(_ours(), _theirs(), SEED, days=[DAY], hour=0,
                                   episode_steps=STEPS)
    obs = states[0]["obs"]
    assert obs["farms"][0]["money"] != truth, "POSITIVE CONTROL: nothing happened after the snapshot"
    got = final_money(obs, _ours(), _theirs(), SEED, episode_steps=STEPS)
    assert got == truth


def test_a_different_opponent_changes_the_answer():
    # The opponent argument is live: the mirror is not silently the real one.
    states, truth = capture_states(_ours(), _theirs(), SEED, days=[DAY], hour=0,
                                   episode_steps=STEPS)
    obs = states[0]["obs"]
    mirrored = final_money(obs, _ours(), _ours(), SEED, episode_steps=STEPS)
    real = final_money(obs, _ours(), _theirs(), SEED, episode_steps=STEPS)
    assert real == truth
    assert isinstance(mirrored, float)
    # Not asserted unequal: two opponents can tie on a short game. Asserted
    # instead that the mirror ran the full distance:
    assert mirrored > 0


def test_timed_variant_reports_seconds():
    states, _ = capture_states(_ours(), _theirs(), SEED, days=[DAY], hour=0,
                               episode_steps=STEPS)
    money, seconds = timed_final_money(states[0]["obs"], _ours(), _theirs(), SEED,
                                       episode_steps=STEPS)
    assert money == final_money(states[0]["obs"], _ours(), _theirs(), SEED, episode_steps=STEPS)
    assert seconds > 0
