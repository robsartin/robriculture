"""The 1.32.7 `hinge` scarcity curve, pinned by value (issue #195).

Every other pricing check in this repo compares `kaggisim` against *whatever
simulator is installed*, which is exactly how #133 went wrong: a drifted install
makes those checks agree with the wrong sim and say nothing about which one it
is. So these assertions carry the numbers themselves.

`hinge` is new in 1.32.7 and applies to the scarcity (below-I0) branch of
CARROT, TOMATO and EGG:

    u = x / T
    shape = u + HINGE_GAIN * max(0, u - 1) ** 2      HINGE_GAIN = 8.0

It is calm up to the knee at x == T and then runs away, so a market that is
merely below its anchor prices normally while a genuinely drained one spikes.
"""

from __future__ import annotations

import math

from kaggisim import economy


def test_hinge_is_linear_in_x_over_T_below_the_knee():
    # u < 1: the quadratic term is clamped off, so shape == u exactly.
    assert economy._shape("hinge", 225.0, T=450.0) == 0.5
    assert economy._shape("hinge", 45.0, T=450.0) == 0.1


def test_hinge_is_exactly_one_at_the_knee():
    # f(T) == 1 by construction, which is what keeps `target` meaning the same
    # thing for hinge as for every other shape.
    assert economy._shape("hinge", 450.0, T=450.0) == 1.0


def test_hinge_runs_away_above_the_knee():
    # u = 2 -> 2 + 8 * 1**2 = 10, an order of magnitude over the linear term.
    assert economy._shape("hinge", 900.0, T=450.0) == 10.0


def test_hinge_degenerates_to_linear_without_a_usable_scale():
    # The sim's own guard: no T, or a non-positive one, falls back to linear.
    assert economy._shape("hinge", 7.0, T=None) == 7.0
    assert economy._shape("hinge", 7.0, T=0) == 7.0


def test_the_three_hinge_items_are_the_ones_1_32_7_changed():
    hinged = {i for i, p in economy.MARKET_PARAMS.items() if p["below_func"] == "hinge"}
    assert hinged == {"CARROT", "TOMATO", "EGG"}


def test_carrot_scarcity_target_is_the_1_32_7_value():
    # 1.32.7 also moved carrot's below_target from 0.20 to 1.00; missing this
    # leaves the shape right and the amplitude wrong.
    assert economy.MARKET_PARAMS["CARROT"]["below_target"] == 1.00


def test_a_drained_carrot_market_spikes_rather_than_creeping():
    # The visible consequence, pinned end to end. Under the old 'log' curve a
    # carrot at an empty market cleared at 46; under 1.32.7 it spikes.
    assert economy.market_price("CARROT", 0) > 100_000


def test_prices_at_the_anchor_are_untouched_by_the_change():
    # The hinge only shapes the scarcity branch; nothing at or above I0 moves.
    for item in ("CARROT", "TOMATO", "EGG"):
        assert economy.market_price(item, 10_000) == economy.base_price(item)


def test_the_hinge_bites_inside_the_range_real_games_actually_reach():
    # I had assumed this drift was latent because market inventory never leaves
    # roughly 9,500-10,150 in a real game. That was wrong, and it is the reason
    # this issue matters: TOMATO's knee is at T=200, so an inventory of 9,500 is
    # already 2.5 knees into scarcity.
    #
    # Under the old 'linear' curve our model priced tomato at 9,500 as 120.
    # Under 1.32.7's hinge it is 552 -- our planning model was 4.6x low across
    # the whole normal operating range, not only at extremes.
    assert economy.market_price("TOMATO", 9_500) == 552
    assert economy.market_price("TOMATO", 9_800) > economy.base_price("TOMATO")


def test_a_real_games_observed_tomato_price_is_reproduced():
    # Ground truth rather than self-consistency: a downloaded ladder replay
    # showed TOMATO at 189 with market inventory 9,664 on the final step. The
    # model must land on that number, not merely agree with whatever simulator
    # happens to be installed (#133).
    assert economy.market_price("TOMATO", 9_664) == 189
