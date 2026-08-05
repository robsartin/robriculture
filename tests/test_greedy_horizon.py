"""Unit tests for the greedy_horizon experiment (issue #8, ADR-0007).

These exercise the *pure decision helpers* directly — the horizon-aware crop
gate, the ROI ranking, and the end-game liquidation — so the single technique
under test is validated without spinning up a full 720-turn game. The full-game
no-crash guard lives in test_no_crash.py (auto-included via the REGISTRY).
"""

from __future__ import annotations

from strategies import greedy_horizon as gh


# --- Horizon-aware crop selection: the plantability gate ---

def test_strawberry_not_plantable_late_in_season():
    # Strawberry needs ~10-16 days to a meaningful yield; on day 28 of a 30-day
    # season it can never mature (and sell) before turn 720.
    assert gh.plantable("STRAWBERRY", 28) is False


def test_short_crops_plantable_early():
    assert gh.plantable("WHEAT", 0) is True
    assert gh.plantable("CARROT", 0) is True
    assert gh.plantable("MELON", 0) is True


def test_melon_gate_closes_once_it_cannot_mature_and_sell():
    # Melon matures in 10 days; leave a day to liquidate. Plantable mid-season,
    # not once the harvest+sell can't finish by season end.
    assert gh.plantable("MELON", 10) is True
    assert gh.plantable("MELON", 25) is False


def test_nothing_plantable_at_the_very_end():
    # On the final day even wheat can't reach a yield in time.
    assert gh.choose_crop(29, 3000) is None


# --- Greedy: prefers the highest profit-per-tile-per-day ---

def test_roi_ranking_puts_melon_first_and_orders_the_rest():
    assert gh.roi("MELON") > gh.roi("CARROT")
    assert gh.roi("CARROT") > gh.roi("TOMATO")
    ranked = gh.ranked_crops()
    assert ranked[0] == "MELON"


def test_chooses_highest_roi_affordable_and_plantable_crop():
    # Flush with cash early: the top-ROI crop (melon) wins.
    assert gh.choose_crop(0, 3000) == "MELON"


def test_affordability_downgrades_the_choice():
    # $30 affords wheat (10) and carrot (20) seed, not melon (80).
    # Among affordable+plantable, carrot has the higher ROI than wheat.
    assert gh.choose_crop(0, 30) == "CARROT"


def test_no_choice_when_broke():
    assert gh.choose_crop(0, 5) is None


# --- End-game liquidation ---

def test_is_endgame_only_in_the_final_stretch():
    assert gh.is_endgame(28) is True
    assert gh.is_endgame(29) is True
    assert gh.is_endgame(27) is False


def test_sell_orders_liquidates_every_sellable_shed_item():
    shed = {"MELON": 6, "CARROT": 2, "WHEAT": 0, "BOGUS": 9}
    orders = gh.sell_orders(shed)
    # Deterministic, sorted by item; zero-count and unknown items excluded.
    assert orders == [["SELL", "CARROT", 2], ["SELL", "MELON", 6]]


def test_sell_orders_empty_when_shed_empty():
    assert gh.sell_orders({}) == []
