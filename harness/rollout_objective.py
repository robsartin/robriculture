"""Roll a state to the end of the game and read our final money (#172 Stage 1).

This is the only rollout configuration that has ever correlated with real
performance in this repo (#177): both seats ACT, and the score is money at
step 720 rather than any valuation of standing stock (#161's error). The
opponent is an argument so that the prediction (a mirror of the candidate on
the other farm) and the truth (the real gate opponent there) are the same
function called twice. `kaggisim.forward.ROLLOUT_PASS` is deliberately not
used: an idle opponent is a dynamics change, not a bias (#174).

The other farm's private shed is not in our observation, so the opponent
starts a rollout with an empty shed. That is the planner's real information
set at runtime and belongs in the prediction; `tests/test_rollout_objective.py`
shows the truth rollout still reproduces the real game to the value.
"""

from __future__ import annotations

import time

from kaggisim import forward


def final_money(obs, our_agent, opponent_agent, seed, episode_steps=720) -> float:
    """Our farm's money at `episode_steps` after rolling forward from `obs`
    with `our_agent` on seat `obs["player"]` and `opponent_agent` on the other."""
    us = int(obs.get("player", 0))
    env = forward.rebuild(obs, episode_steps=episode_steps, seed=seed)
    agents = [None, None]
    agents[us] = our_agent
    agents[1 - us] = opponent_agent
    while len(env.steps) < episode_steps:
        env.step([agents[i](env.state[i].observation) for i in range(2)])
    return float(env.state[us].observation["farms"][us]["money"])


def timed_final_money(obs, our_agent, opponent_agent, seed, episode_steps=720):
    """`final_money` plus the wall-clock seconds it took — the cost the issue
    says to budget from measurement, not from #159's one-sided numbers."""
    t0 = time.perf_counter()
    money = final_money(obs, our_agent, opponent_agent, seed, episode_steps)
    return money, time.perf_counter() - t0
