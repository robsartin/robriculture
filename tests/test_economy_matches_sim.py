"""Claim check: ``economy.py`` must match the installed sim source (issue #16).

``kaggisim/economy.py`` is a hand-transcribed copy of the numbers the real
simulator runs on. Transcription drifts — a max-yield day copied wrong, a field
the sim added that we never picked up. This module is the *claim check* from #3:
it reads the ground-truth tables straight out of the installed sim
(``kaggle_environments.envs.kaggriculture``) and asserts our constants match,
field for field, so the two can never silently diverge again.

The sim and our tables use different field names for the same quantity; the
maps below are the single place that translation is spelled out.
"""

from __future__ import annotations

import pytest
from kaggle_environments.envs.kaggriculture import kaggriculture as sim

from kaggisim.economy import ANIMALS, CROPS, MARKET_PARAMS

# economy field -> sim field, for the quantities both tables carry.
_CROP_FIELD_MAP = {
    "seed": "seed",
    "first": "first_yield_day",
    "max_day": "max_yield_day",
    "interval": "interval",
    "max_yield": "max_yield",
    "ongoing": "ongoing",
}

_ANIMAL_FIELD_MAP = {
    "cost": "cost",
    "product": "product",
    "first": "first_yield_day",
    "interval": "interval",
    "max_held": "max_held",
    "structure": "structure",
}

# The market-curve params carry identical field names in both tables.
_MARKET_FIELDS = (
    "base",
    "I0",
    "T",
    "below_func",
    "below_target",
    "above_func",
    "above_target",
)


def test_crop_names_match_sim():
    assert set(CROPS) == set(sim.CROPS)


@pytest.mark.parametrize("crop", sorted(sim.CROPS))
def test_crop_constants_match_sim(crop):
    ours = CROPS[crop]
    theirs = sim.CROPS[crop]
    for our_field, sim_field in _CROP_FIELD_MAP.items():
        assert ours[our_field] == theirs[sim_field], (
            f"{crop}.{our_field} is {ours[our_field]!r}, "
            f"sim {sim_field} is {theirs[sim_field]!r}"
        )
    # Our tables also denormalise the market base price onto each crop; it must
    # agree with the sim's authoritative market table.
    assert ours["base"] == sim.MARKET_PARAMS[crop]["base"]


def test_animal_names_match_sim():
    assert set(ANIMALS) == set(sim.ANIMALS)


@pytest.mark.parametrize("animal", sorted(sim.ANIMALS))
def test_animal_constants_match_sim(animal):
    ours = ANIMALS[animal]
    theirs = sim.ANIMALS[animal]
    for our_field, sim_field in _ANIMAL_FIELD_MAP.items():
        assert ours[our_field] == theirs[sim_field], (
            f"{animal}.{our_field} is {ours[our_field]!r}, "
            f"sim {sim_field} is {theirs[sim_field]!r}"
        )
    # The animal's product base price is denormalised from the market table.
    assert ours["base"] == sim.MARKET_PARAMS[theirs["product"]]["base"]


def test_market_param_names_match_sim():
    assert set(MARKET_PARAMS) == set(sim.MARKET_PARAMS)


@pytest.mark.parametrize("item", sorted(sim.MARKET_PARAMS))
def test_market_params_match_sim(item):
    ours = MARKET_PARAMS[item]
    theirs = sim.MARKET_PARAMS[item]
    for field in _MARKET_FIELDS:
        assert ours[field] == theirs[field], (
            f"{item}.{field} is {ours[field]!r}, sim is {theirs[field]!r}"
        )


# --- market_price must match the sim exactly (ADR-0002 claim-check) ---


def test_market_price_matches_the_sim_across_the_curve():
    """`economy.market_price` is a reconciliation of the sim's own function, not
    an approximation: the whole point of #162 is reasoning about what our own
    sales do to the price we get, so a drifting curve would silently invent the
    answer. Checked on both sides of the I0 anchor, including the glut region
    where melon's `sq` curve is steepest."""
    from kaggle_environments.envs.kaggriculture import kaggriculture as sim
    from kaggisim import economy

    checked = 0
    for item in economy.MARKET_PARAMS:
        for inv in (0, 5000, 9000, 9999, 10000, 10001, 10500, 11000, 15000, 30000):
            assert economy.market_price(item, inv) == sim.market_price(item, inv), (item, inv)
            checked += 1
    assert checked >= 80, f"POSITIVE CONTROL: only {checked} points compared"
