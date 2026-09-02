"""The forward model must reproduce the real game, or a planner built on it is
inventing its own answers (#159)."""

from __future__ import annotations

import copy
import json

from kaggle_environments import make

from harness.evolve import genome_agent
from kaggisim import forward


def _live(farm):
    return sum(1 for row in farm["tiles"] for t in row
               if isinstance(t, dict) and t.get("kind") == "PLANT")


def test_rebuilt_env_reproduces_the_real_game():
    """Rebuild from an observation alone, roll forward, and land on the same
    state the real game reached. Checked against a real agent rather than a stub
    so the rollout exercises planting, harvesting, hiring and market orders."""
    champ = json.load(open("strategies/champion_genome.json"))["genome"]
    n, k, seed = 240, 48, 4242

    real = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
    real.reset(2)
    agent = genome_agent(champ)
    snapshot = None
    for step in range(n + k):
        if step == n:
            snapshot = copy.deepcopy(real.state[0].observation)
        real.step([agent(real.state[0].observation), forward.ROLLOUT_PASS])
    truth = real.state[0].observation["farms"][0]

    env = forward.rebuild(snapshot, seed=seed)
    replay = genome_agent(champ)
    for _ in range(k):
        env.step([replay(env.state[0].observation), forward.ROLLOUT_PASS])
    got = env.state[0].observation["farms"][0]

    assert _live(truth) > 0, "POSITIVE CONTROL: nothing was growing, test proves nothing"
    assert got["money"] == truth["money"]
    assert _live(got) == _live(truth)
    assert len(got["hands"]) == len(truth["hands"])
    assert got["unlocked_quadrants"] == truth["unlocked_quadrants"]


def test_standing_value_credits_crops_still_in_the_ground():
    """Cash alone would score every planting as a loss inside a short horizon."""
    farm = {"money": 100.0, "tiles": [[{"kind": "PLANT", "crop": "MELON", "yield_units": 3}]]}

    assert forward.standing_value(farm, {"MELON": 250}) == 100.0 + 750.0


def test_standing_value_ignores_empty_and_weed_tiles():
    farm = {"money": 50.0, "tiles": [[None, {"kind": "WEED"}]]}

    assert forward.standing_value(farm, {"MELON": 250}) == 50.0
