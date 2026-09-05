"""Snapshot our observation from a real game at chosen (day, hour) — the state
set for the #172 objective check.

The game is driven step by step (as `tests/test_forward.py` does) so that the
observation each seat acts on is `env.state[i].observation`, the same object
`env.run` hands the agents; `test_state_set.py` pins that the drive lands on
`env.run`'s final money to the value. Observations are deep-copied at capture
because the env mutates them in place as the game continues.
"""

from __future__ import annotations

import copy

TURNS_PER_DAY = 24


def capture_states(agent_a, agent_b, seed, days, hour=0, episode_steps=720):
    """Drive a full game of `agent_a` (seat 0) vs `agent_b` (seat 1) under
    `seed`; return `(states, final_money)` where `states` holds seat 0's
    observation at hour `hour` of each day in `days` (in the order given) and
    `final_money` is seat 0's money when the game ends.

    Each state also carries `opponent_private`: seat 1's `private` at the
    same step, deep-copied. The harness drives the real game so it knows the
    other farm's shed even though our observation never carries it; the
    truth rollout restores it (spec amendment 2026-09-05: seed 0 day 15
    diverged on the opponent's unseen stock). The planner's mirror never
    sees it.

    Both agents are callables `agent(obs) -> action`. A requested (day, hour)
    at or past `episode_steps` is refused up front rather than silently
    missing from the result (#153: a partial set must not look like a set).
    """
    from kaggle_environments import make

    wanted = {int(day) * TURNS_PER_DAY + int(hour): int(day) for day in days}
    too_late = [d for s, d in wanted.items() if s >= episode_steps]
    if too_late:
        raise ValueError(
            f"day(s) {sorted(too_late)} at hour {hour} are at or past the game's "
            f"{episode_steps} steps")

    env = make("kaggriculture", configuration={"episodeSteps": episode_steps, "seed": seed})
    env.reset(2)
    found, opp_found = {}, {}
    # `episode_steps` configures the total state count (len(env.steps)), which
    # is the reset state plus (episode_steps - 1) env.step() calls; calling
    # step() episode_steps times overruns an already-done env.
    for step in range(episode_steps - 1):
        obs0 = env.state[0].observation
        if step in wanted:
            found[step] = copy.deepcopy(obs0)
            opp_found[step] = copy.deepcopy(env.state[1].observation["private"])
        env.step([agent_a(obs0), agent_b(env.state[1].observation)])
    if episode_steps - 1 in wanted:
        found[episode_steps - 1] = copy.deepcopy(env.state[0].observation)
        opp_found[episode_steps - 1] = copy.deepcopy(env.state[1].observation["private"])
    final_money = float(env.state[0].observation["farms"][0]["money"])
    states = []
    for day in days:
        step = int(day) * TURNS_PER_DAY + int(hour)
        states.append({"seed": seed, "day": int(day), "hour": int(hour),
                       "step": step, "obs": found[step],
                       "opponent_private": opp_found[step]})
    return states, final_money
