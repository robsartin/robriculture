"""herd_first: field_pace with the herd funded before land and seed (#254).

#252 stood 6 head by day 8 with 15 in cash: the benchmark's buy order funds land
and the whole strawberry seed bill before the herd. The herd is the field's
pre-payday cash engine -- one fertilizer per animal per day at ~100, wool from
day 6 -- so this arm moves it ahead of land and seed through the buy_order seam
and changes nothing else.
"""

from __future__ import annotations

from strategies import field_pace as fp
from strategies import herd_first as hf


def test_the_declared_order():
    # One decision on top of #252's package: the herd before land and seed.
    assert hf.ORDER_H == ("hires", "herd", "land", "seed")
    assert hf.HerdFirstStrategy.ORDER_H == hf.ORDER_H
    assert hf.HerdFirstStrategy.name == "herd_first"
    assert hf.HerdFirstStrategy.benchmark is False


def test_the_hook_answers_with_the_declared_order():
    assert hf.HerdFirstStrategy().buy_order() == hf.ORDER_H
    assert fp.FieldPaceStrategy().buy_order() is None      # field_pace keeps the frozen order


def test_it_is_a_registered_contender_that_inherits_every_field_pace_knob():
    from strategies import REGISTRY, load
    assert "herd_first" in REGISTRY and load("herd_first") is hf.HerdFirstStrategy
    assert issubclass(hf.HerdFirstStrategy, fp.FieldPaceStrategy)
    s, base = hf.HerdFirstStrategy(), fp.FieldPaceStrategy()
    for day in (0, 6, 8, 11, 15):
        assert s.hire_target(day) == base.hire_target(day)
        assert s.land_target(day) == base.land_target(day)
        assert s.herd_target(day) == base.herd_target(day)
        assert s.pasture_count(day, 0) == base.pasture_count(day, 0)
    assert s.pivot_day() == base.pivot_day() and s.cluster_size() == base.cluster_size()
    assert s.capital_reserve() == base.capital_reserve() and s.layout() == base.layout()
    assert hf.HerdFirstStrategy.CAPS == fp.FieldPaceStrategy.CAPS
