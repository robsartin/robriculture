"""Market revenue ceiling as an LP (#136).

The formulation is tested without a solver: the arithmetic that decides the
answer is worth pinning independently of the library that reports it, and these
run in milliseconds without touching scipy.
"""
from __future__ import annotations

import pytest

from harness import ceiling_lp as lp


def test_town_demand_matches_the_centre_cadence_by_hand():
    """1.32.7 drains a flat 1 unit per town-centre product every
    `townCenterSellInterval` (24) turns -- the 1x/2x/4x day-band schedule of
    1.32.4 is gone (#195). Over a 720-turn season that is 30 events.

    MELON is a town-centre product and appears in no shop, so its demand is the
    centre cadence alone -- the cleanest hand-check available, and it is 30, not
    the 140 the old schedule gave."""
    demand = lp.town_demand()
    assert demand["MELON"] == lp.TURNS // lp.CENTER_INTERVAL == 30


def test_single_product_shops_consume_double():
    """YARN_STORE sells only WOOL, so it consumes 2 per event rather than 1 --
    the rule that makes WOOL a bigger market than its shop count suggests."""
    demand = lp.town_demand()
    centre_only = lp.TURNS // lp.CENTER_INTERVAL
    shop_events = lp.TURNS // lp.SHOP_INTERVAL
    assert demand["WOOL"] == centre_only + shop_events * 2


def test_ongoing_crop_yields_once_per_interval_not_once_per_plant():
    """TOMATO produces every day after first yield; MELON pays out once. This is
    the distinction the 2-crop controller could not express (#127)."""
    tomato_units, _ = lp.crop_activity("TOMATO")
    melon_units, _ = lp.crop_activity("MELON")
    assert tomato_units >= lp.economy.CROPS["TOMATO"]["max_yield"]
    assert melon_units % lp.economy.CROPS["MELON"]["max_yield"] == 0


def test_every_crop_is_charged_survival_watering():
    """A plant unwatered for two days becomes a WEED, so a tile costs at least
    one watering every two days for the whole season regardless of yield."""
    for crop in lp.CROPS:
        _, actions = lp.crop_activity(crop)
        assert actions >= lp.SEASON_DAYS // 2


def test_animal_activity_reports_its_product():
    """Animals are valued by what they produce, not by the animal itself --
    MILK and WOOL are 46% of the market (#136) while the animal sells nothing."""
    _, _, product = lp.animal_activity("COW")
    assert product == "MILK"


def test_program_constrains_land_labour_and_demand():
    """Shape check: the LP must carry a labour row, two land rows, one demand
    row per product, and the wheat-as-feed coupling."""
    activities, objective, A_ub, b_ub, _units, product = lp.build_program(10, 0.45)
    assert len(objective) == len(activities) == len(lp.CROPS) + len(lp.ANIMALS)
    assert all(len(row) == len(activities) for row in A_ub)
    assert len(A_ub) == len(b_ub)
    # 1 labour + 2 land + one per distinct product + 1 feed coupling
    assert len(A_ub) == 1 + 2 + len(set(product.values())) + 1


def test_objective_is_negated_because_linprog_minimises():
    """A sign slip here would silently return the WORST mix while reporting
    'Optimal', which is the kind of wrong answer that looks right."""
    _activities, objective, _A, _b, _u, _p = lp.build_program(10, 0.45)
    assert all(c <= 0 for c in objective)


def test_more_travel_leaves_less_labour():
    """Travel is charged once globally as a fraction of capacity, so raising it
    must shrink the labour budget rather than any per-tile cost."""
    _a, _o, _A1, b_low, _u, _p = lp.build_program(10, 0.10)
    _a2, _o2, _A2, b_high, _u2, _p2 = lp.build_program(10, 0.80)
    assert b_low[0] > b_high[0]


def test_solved_mix_respects_melon_demand():
    """The headline finding, end to end: melon caps on demand long before land
    or labour. The town buys 140 a season, both players combined."""
    pytest.importorskip("scipy")
    out = lp.solve()
    melon_tiles = out["mix"].get("MELON", 0.0)
    assert melon_tiles * out["units"]["MELON"] <= lp.town_demand()["MELON"] + 1e-6
