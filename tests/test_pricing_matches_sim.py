"""Claim-check: our pricing model reproduces the sim's market price exactly.

The ADR-0002 pattern (cf. test_economy_matches_sim.py): assert
``kaggisim.pricing.market_price`` equals the installed simulator's
``market_price`` across every product and every inventory regime (scarce, at the
anchor, flooded to $1), so the model can never silently drift from the game it
is supposed to mirror.
"""

from __future__ import annotations

import math

import pytest

from kaggisim import pricing
from kaggisim.economy import MARKET_PARAMS

sim = pytest.importorskip(
    "kaggle_environments.envs.kaggriculture.kaggriculture",
    reason="installed kaggriculture simulator required for the claim-check",
)


def _inventories(I0: int):
    """A spread across the scarce (< I0), anchor, and flooded (> I0) regimes,
    including the melon floor point (~I0+158) and a deeply flooded value."""
    offsets = [-8000, -1000, -100, -1, 0, 1, 50, 100, 158, 300, 500, 1000, 5000, 20000]
    return [I0 + d for d in offsets]


def test_market_price_matches_sim_for_every_product_and_regime():
    for item in MARKET_PARAMS:
        I0 = MARKET_PARAMS[item]["I0"]
        for inv in _inventories(I0):
            assert pricing.market_price(item, inv) == sim.market_price(item, inv), (
                f"{item} @ inv={inv}: ours={pricing.market_price(item, inv)} "
                f"sim={sim.market_price(item, inv)}"
            )


def test_price_floor_matches_sim():
    assert pricing.PRICE_FLOOR == sim.PRICE_FLOOR


def test_shape_matches_sim_including_log10_and_default():
    for func in ("linear", "sq", "sqrt", "log", "log10", "unknown-defaults-to-linear"):
        for x in (0.0, 1.0, 7.5, 300.0):
            assert pricing._shape(func, x) == sim._shape(func, x)
    # negative distances clamp to 0 (mirrors the sim)
    assert pricing._shape("sqrt", -5.0) == 0.0


# --- marginal helpers strategies use ---

def test_marginal_revenue_is_the_per_unit_lockstep_sum():
    # Melon floods fast: selling 200 units clears far less than 200 * base.
    inv = MARKET_PARAMS["MELON"]["I0"]
    expected = sum(pricing.market_price("MELON", inv + j) for j in range(200))
    assert pricing.marginal_revenue("MELON", inv, 200) == expected
    assert pricing.marginal_revenue("MELON", inv, 0) == 0
    assert pricing.marginal_revenue("MELON", inv, -3) == 0


def test_sell_quantity_caps_a_shallow_market_but_not_a_deep_one():
    melon_I0 = MARKET_PARAMS["MELON"]["I0"]
    wheat_I0 = MARKET_PARAMS["WHEAT"]["I0"]
    # Melon (squared, shallow): holding 200, selling to >=200/unit stops early.
    capped = pricing.sell_quantity("MELON", melon_I0, have=200, min_price=200)
    assert 0 < capped < 200
    # Wheat (log, ~bottomless near base): all 200 clear at/above ~20.
    assert pricing.sell_quantity("WHEAT", wheat_I0, have=200, min_price=20) == 200
    # Never exceeds what you hold.
    assert pricing.sell_quantity("MELON", melon_I0, have=0, min_price=1) == 0


def test_best_market_picks_the_richest_and_respects_the_floor_fraction():
    I0 = {k: MARKET_PARAMS[k]["I0"] for k in ("MELON", "WHEAT", "EGG")}
    # Fresh inventories at I0 -> each clears its base; melon (250) is richest.
    assert pricing.best_market(["WHEAT", "EGG", "MELON"], I0) == "MELON"
    # Flood melon past its floor; wheat (base 25) now beats melon ($1).
    flooded = dict(I0, MELON=I0["MELON"] + 400)
    assert pricing.best_market(["WHEAT", "MELON"], flooded) == "WHEAT"
    # With a base-fraction gate above every clearing price, nothing qualifies.
    assert pricing.best_market(["WHEAT"], I0, base_frac=100.0) is None
