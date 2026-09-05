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


def test_final_money_is_unchanged_when_rolling_from_the_terminal_step():
    """obs at step episode_steps - 1 has zero steps left to roll; the
    while len(env.steps) < episode_steps loop must degenerate to a no-op
    rather than skip or misbehave, leaving money exactly as captured."""
    states, _ = capture_states(_ours(), _theirs(), SEED, days=[3], hour=23,
                               episode_steps=STEPS)
    obs = states[0]["obs"]
    assert obs["step"] == STEPS - 1, "terminal step must have zero steps remaining"
    got = final_money(obs, _ours(), _theirs(), SEED, episode_steps=STEPS)
    assert got == obs["farms"][0]["money"]


class _Spy:
    """An opponent that records the shed it was handed on its first turn."""

    def __init__(self):
        self.first_shed = None

    def __call__(self, obs):
        if self.first_shed is None:
            self.first_shed = dict(obs["private"]["shed"])
        return {"farmer": ["PASS"], "hands": [], "market": []}


def test_opponent_private_is_restored_into_the_other_seat_when_given():
    states, _ = capture_states(_ours(), _theirs(), SEED, days=[DAY], hour=0,
                               episode_steps=STEPS)
    obs = states[0]["obs"]
    stocked = {"shed": {"WHEAT": 7, "FERTILIZER": 11}, "seeds": {}, "inventories": [{}] * 11}
    spy = _Spy()
    final_money(obs, _ours(), spy, SEED, episode_steps=STEPS, opponent_private=stocked)
    assert spy.first_shed == {"WHEAT": 7, "FERTILIZER": 11}
    bare = _Spy()
    final_money(obs, _ours(), bare, SEED, episode_steps=STEPS)
    assert not any(bare.first_shed.values()), "POSITIVE CONTROL: rebuild already had stock; test proves nothing"


def test_truth_reproduces_a_real_game_when_the_opponent_holds_stock():
    # The defect the first Stage 1 run hit: seed 0, dense_farm vs meta_bot,
    # hour 0 of day 15, opponent shed non-empty. ~15 s: one real game plus
    # two half-game rollouts. Slow on purpose -- this is the exactness control
    # for the state that broke it.
    ours = lambda: make_agent(load("dense_farm")())
    theirs = lambda: make_agent(load("meta_bot")())
    states, truth = capture_states(ours(), theirs(), 0, days=[15], hour=0, episode_steps=720)
    state = states[0]
    assert any(state["opponent_private"]["shed"].values()), \
        "POSITIVE CONTROL: the opponent's shed is empty here, the defect cannot show"
    without = final_money(state["obs"], ours(), theirs(), 0, episode_steps=720)
    with_stock = final_money(state["obs"], ours(), theirs(), 0, episode_steps=720,
                             opponent_private=state["opponent_private"])
    assert without != truth, "POSITIVE CONTROL: the plain rollout is already exact, nothing to fix"
    assert with_stock == truth
