"""six_melon (#341): water a melon before cutting it and carry eighteen, and
nothing else."""

from __future__ import annotations

from strategies import field_rival as fr
from strategies import six_melon as sx
from strategies.town_melon import TownMelonStrategy


def test_the_declared_constants_and_hooks():
    p = sx.SixMelonStrategy()
    assert sx.CARRY == 18 and p.carry_limit() == 18 and p.water_first() is True
    assert TownMelonStrategy().carry_limit() is None and TownMelonStrategy().water_first() is None
    assert fr.CARRY_LIMIT == 6


def test_the_class_defines_only_the_two_hooks():
    from harness import sheep_bench as sb
    p = sx.SixMelonStrategy()
    assert p.name == "six_melon" and isinstance(p, TownMelonStrategy) and p.benchmark is False
    assert set(sx.SixMelonStrategy.__dict__) & set(sb._seam_names()) == {"carry_limit", "water_first"}
    assert {k for k, v in sx.SixMelonStrategy.__dict__.items() if callable(v)} == {"carry_limit", "water_first"}
    assert p.crop_plan({"day": 9}) == TownMelonStrategy().crop_plan({"day": 9})


def test_registered():
    from strategies import load
    assert load("six_melon") is sx.SixMelonStrategy
