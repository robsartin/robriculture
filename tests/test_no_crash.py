"""Regression guard: no strategy may ever crash or stall.

A crash during evaluation is an automatic loss, so this is the single most
important test in the repo. Every strategy plays full games against the built-in
bots across several seeds; any exception (with strict mode on) or non-DONE status
fails the suite.

Run from the repo root with the venv active:  pytest -q
"""

from __future__ import annotations

import os

import pytest
from kaggle_environments import make

# Force strategies to raise rather than silently PASS, so bugs surface in tests.
os.environ["ROBRICULTURE_STRICT"] = "1"

from kaggisim.strategy import make_agent  # noqa: E402
from strategies import REGISTRY, load     # noqa: E402

SEEDS = [0, 1, 2]


@pytest.mark.parametrize("name", sorted(REGISTRY))
@pytest.mark.parametrize("opponent", ["random", "starter"])
def test_strategy_completes_without_crashing(name, opponent):
    agent = make_agent(load(name)())
    for seed in SEEDS:
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed}, debug=True)
        env.run([agent, opponent])
        statuses = [s.status for s in env.steps[-1]]
        assert all(s == "DONE" for s in statuses), f"{name} vs {opponent} seed {seed}: {statuses}"


@pytest.mark.parametrize("name", sorted(REGISTRY))
def test_strategy_beats_random_sometimes(name):
    """Sanity floor: each strategy should out-earn 'random' on average."""
    agent = make_agent(load(name)())
    wins = 0
    for seed in SEEDS:
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
        env.run([agent, "random"])
        ra, rb = (s.reward or 0 for s in env.steps[-1])
        wins += ra > rb
    assert wins >= 2, f"{name} only beat random {wins}/{len(SEEDS)} times"
