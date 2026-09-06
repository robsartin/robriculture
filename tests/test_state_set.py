"""States for the #172 objective check come from a real game, snapshotted at
(day, hour) from our seat, and the same drive must land where `env.run` lands
— otherwise the per-seat observations we hand the agents are not the ones the
runner hands them."""

from __future__ import annotations

import pytest
from kaggle_environments import make

from harness.state_set import capture_states
from kaggisim.strategy import make_agent
from strategies import load

SEED, STEPS = 7, 72          # three days: enough to plant, not enough to bore


def _agents():
    """Two cheap registered strategies, one per seat; both deterministic under
    a seed. `capture_states` drives `env.step` itself, so seats must be
    callables (a built-in name string is only resolved by `env.run`)."""
    return make_agent(load("wheat_hands")()), make_agent(load("hired_hands")())


def test_captures_our_observation_at_the_requested_days():
    a, b = _agents()
    states, final = capture_states(a, b, SEED, days=[1, 2], hour=0, episode_steps=STEPS)
    assert [s["day"] for s in states] == [1, 2]
    assert [s["step"] for s in states] == [24, 48]
    for s in states:
        assert s["seed"] == SEED and s["hour"] == 0
        assert s["obs"]["day"] == s["day"] and s["obs"]["hour"] == 0
        assert s["obs"]["player"] == 0
        assert "private" in s["obs"] and "shed" in s["obs"]["private"]
    assert isinstance(final, float)


def test_snapshots_are_copies_not_views_of_the_live_env():
    a, b = _agents()
    states, final = capture_states(a, b, SEED, days=[1], hour=0, episode_steps=STEPS)
    snap = states[0]["obs"]
    # A view of the live observation would read the game's LAST turn by the
    # time capture_states returns; a copy still reads day 1, hour 0.
    assert snap["day"] == 1 and snap["hour"] == 0
    assert snap["farms"][0]["money"] != final, "POSITIVE CONTROL: money never moved after day 1"


def test_the_drive_lands_where_env_run_lands():
    # POSITIVE CONTROL for the per-seat observations: stepping the env ourselves
    # with state[i].observation must reach exactly the money env.run reaches.
    a, b = _agents()
    _, final = capture_states(a, b, SEED, days=[1], hour=0, episode_steps=STEPS)
    env = make("kaggriculture", configuration={"episodeSteps": STEPS, "seed": SEED})
    env.run([make_agent(load("wheat_hands")()), make_agent(load("hired_hands")())])
    truth = env.state[0].observation["farms"][0]["money"]
    assert truth > 0, "POSITIVE CONTROL: no money moved, test proves nothing"
    assert final == truth


def test_a_day_past_the_game_is_refused():
    a, b = _agents()
    with pytest.raises(ValueError):
        capture_states(a, b, SEED, days=[3], hour=0, episode_steps=STEPS)


def test_captures_the_final_step_when_requested():
    """The main loop stops one short of episode_steps (step 71 of 72, #172
    fix-round-1 finding 1); the terminal (day, hour) must still be captured by
    the trailing branch rather than silently missing from the result."""
    a, b = _agents()
    states, final = capture_states(a, b, SEED, days=[2], hour=23, episode_steps=STEPS)
    assert len(states) == 1
    s = states[0]
    assert s["day"] == 2 and s["hour"] == 23
    assert s["step"] == STEPS - 1
    assert s["obs"]["day"] == 2 and s["obs"]["hour"] == 23
    assert s["obs"]["farms"][0]["money"] == final


def test_captures_the_opponents_private_state_alongside_ours():
    # The harness drives the real game, so it knows the other farm's shed even
    # though our observation never carries it. The truth rollout needs it
    # (spec amendment 2026-09-05: seed 0 day 15 diverged by the opponent's
    # unseen WHEAT 7 / FERTILIZER 11).
    a, b = _agents()
    states, _ = capture_states(a, b, SEED, days=[1, 2], hour=0, episode_steps=STEPS)
    for s in states:
        opp = s["opponent_private"]
        assert {"shed", "seeds", "inventories"} <= set(opp)
        assert opp is not s["obs"]["private"]
    # The terminal-step path must carry it too.
    last, _ = capture_states(*_agents(), SEED, days=[2], hour=23, episode_steps=STEPS)
    assert "shed" in last[0]["opponent_private"]
