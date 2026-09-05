"""Roll a state to the end of the game and read our final money (#172 Stage 1).

This is the only rollout configuration that has ever correlated with real
performance in this repo (#177): both seats ACT, and the score is money at
step 720 rather than any valuation of standing stock (#161's error). The
opponent is an argument so that the prediction (a mirror of the candidate on
the other farm) and the truth (the real gate opponent there) are the same
function called twice. `kaggisim.forward.ROLLOUT_PASS` is deliberately not
used: an idle opponent is a dynamics change, not a bias (#174).

The observation never carries the other farm's private shed, so a caller that
knows it (the harness, from the real game) passes `opponent_private` for the
TRUTH rollout; the mirror prediction never does, because the planner never
has it — that asymmetry is the point of the measurement.
"""

from __future__ import annotations

import copy
import time

from kaggisim import forward


def final_money(obs, our_agent, opponent_agent, seed, episode_steps=720,
                opponent_private=None) -> float:
    """Our farm's money at `episode_steps` after rolling forward from `obs`
    with `our_agent` on seat `obs["player"]` and `opponent_agent` on the other.

    When `opponent_private` is given, it replaces the rebuilt env's other
    seat's `observation["private"]` before the first step (the truth
    rollout's fix for #172: the rebuilt opponent otherwise starts with an
    empty shed it may not actually have)."""
    us = int(obs.get("player", 0))
    env = forward.rebuild(obs, episode_steps=episode_steps, seed=seed)
    if opponent_private is not None:
        env.state[1 - us].observation["private"] = copy.deepcopy(opponent_private)
    agents = [None, None]
    agents[us] = our_agent
    agents[1 - us] = opponent_agent
    while len(env.steps) < episode_steps:
        env.step([agents[i](env.state[i].observation) for i in range(2)])
    return float(env.state[us].observation["farms"][us]["money"])


def timed_final_money(obs, our_agent, opponent_agent, seed, episode_steps=720,
                      opponent_private=None):
    """`final_money` plus the wall-clock seconds it took — the cost the issue
    says to budget from measurement, not from #159's one-sided numbers."""
    t0 = time.perf_counter()
    money = final_money(obs, our_agent, opponent_agent, seed, episode_steps,
                        opponent_private)
    return money, time.perf_counter() - t0
