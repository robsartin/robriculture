"""Sanity on the economic tables and the placeholder ROI helper."""

from __future__ import annotations

from kaggisim.economy import (
    ANIMALS,
    CONFIG_DEFAULTS,
    CROPS,
    base_price,
    naive_crop_roi,
)


def test_season_is_720_turns():
    assert CONFIG_DEFAULTS["episodeSteps"] == 720


def test_base_price_known_and_unknown():
    assert base_price("WHEAT") == 25
    assert base_price("NOT_A_THING") == 0


def test_naive_crop_roi_is_positive_for_every_crop():
    for crop in CROPS:
        assert naive_crop_roi(crop) > 0


def test_each_animal_has_the_expected_fields():
    required = {"cost", "product", "base", "first", "interval", "max_held", "structure"}
    for name, data in ANIMALS.items():
        assert required <= set(data), name
