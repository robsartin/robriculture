"""free_straw (#312): the strawberry cap removed, nothing else."""

from __future__ import annotations

from strategies import field_rival as fr
from strategies import free_straw as fs
from strategies.town_split import TownSplitStrategy


def test_caps_drop_the_strawberry_key_and_keep_the_rest():
    assert fs.CAPS_S == {"MELON": 10, "WHEAT": 24}
    assert "STRAWBERRY" not in fs.CAPS_S
    assert fs.CAPS_S["MELON"] == TownSplitStrategy.CAPS["MELON"] and fs.CAPS_S["WHEAT"] == TownSplitStrategy.CAPS["WHEAT"]
    assert TownSplitStrategy.CAPS["STRAWBERRY"] == 38
    assert fs.FreeStrawStrategy.CAPS is fs.CAPS_S


def test_an_absent_key_means_no_cap_on_the_frozen_crop_rule():
    pivot = TownSplitStrategy().pivot_day()
    standing = {"STRAWBERRY": 40, "MELON": 10}
    assert fr.crop_for_plot(10, standing, caps=fs.CAPS_S, pivot=pivot) == "STRAWBERRY"
    assert fr.crop_for_plot(10, standing, caps=TownSplitStrategy.CAPS, pivot=pivot) == "WHEAT"
    assert fr.crop_for_plot(10, {"STRAWBERRY": 30}, caps=TownSplitStrategy.CAPS, pivot=pivot) == "STRAWBERRY"


def test_the_class_overrides_nothing_but_the_caps():
    from harness import sheep_bench as sb
    p = fs.FreeStrawStrategy()
    assert p.name == "free_straw" and isinstance(p, TownSplitStrategy) and p.FOURTH_DAY == 8 and p.benchmark is False
    assert set(fs.FreeStrawStrategy.__dict__) & set(sb._seam_names()) == set()
    assert not [k for k, v in fs.FreeStrawStrategy.__dict__.items() if callable(v)]
    q = TownSplitStrategy()
    assert p.pivot_day() == q.pivot_day() and p.livestock_workers(8) == q.livestock_workers(8) and p.buy_order() == q.buy_order()
    assert p.sheep_share(["YARN_STORE", "PIZZA_SHOP"]) == q.sheep_share(["YARN_STORE", "PIZZA_SHOP"])


def test_registered():
    from strategies import load
    assert load("free_straw") is fs.FreeStrawStrategy
