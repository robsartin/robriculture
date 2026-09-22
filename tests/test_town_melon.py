"""town_melon (#337): melon instead of strawberry from day 9 while the town has
no strawberry shop, and nothing else."""

from __future__ import annotations

from strategies import free_straw
from strategies import second_melon as sm
from strategies import town_melon as tm
from strategies.second_melon import SecondMelonStrategy


def _obs(day, shops):
    return {"day": day, "town": {"unlocked_shops": list(shops)}}


def test_the_declared_constants():
    assert tm.DEAD_DAY == 9 and tm.LAST_MELON_DAY == 18 and tm.DEAD_WINDOWS == ((9, 18),)
    assert tm.DEAD_CAPS == {**free_straw.CAPS_S, "MELON": 24, "STRAWBERRY": 0}
    assert tm.STRAW_SHOPS == {"BRUNCH_SPOT", "ICE_CREAM_SHOP", "SMOOTHIE_SHOP", "FARMERS_MARKET"}


def test_straw_dead_reads_the_sims_shop_table():
    assert tm.straw_dead([]) and tm.straw_dead(["YARN_STORE", "PET_CAFE", "BAKERY"])
    assert not tm.straw_dead(["YARN_STORE", "ICE_CREAM_SHOP"])
    assert not tm.straw_dead(["FARMERS_MARKET"]) and not tm.straw_dead(["BRUNCH_SPOT"]) and not tm.straw_dead(["SMOOTHIE_SHOP"])


def test_crop_plan_fires_from_day_nine_in_a_dead_town_and_reverts():
    p = tm.TownMelonStrategy()
    dead = ["YARN_STORE", "PET_CAFE", "BAKERY"]
    assert p.crop_plan(_obs(9, dead)) == (tm.DEAD_CAPS, tm.DEAD_WINDOWS)
    assert p.crop_plan(_obs(18, dead)) == (tm.DEAD_CAPS, tm.DEAD_WINDOWS)
    assert p.crop_plan(_obs(8, dead)) is None                                   # before the day
    assert p.crop_plan(_obs(9, dead + ["ICE_CREAM_SHOP"])) is None               # a strawberry shop: frozen
    assert p.crop_plan(_obs(12, dead + ["BRUNCH_SPOT"])) is None                # reverts when one unlocks
    assert p.crop_plan({"day": 9}) == (tm.DEAD_CAPS, tm.DEAD_WINDOWS)          # no town key: no shops
    assert p.crop_plan(_obs(9, dead))[0] is tm.DEAD_CAPS and p.crop_plan(_obs(9, dead))[1] is tm.DEAD_WINDOWS


def test_the_class_defines_only_crop_plan():
    from harness import sheep_bench as sb
    p = tm.TownMelonStrategy()
    assert p.name == "town_melon" and isinstance(p, SecondMelonStrategy) and p.benchmark is False
    assert set(tm.TownMelonStrategy.__dict__) & set(sb._seam_names()) == {"crop_plan"}
    assert {k for k, v in tm.TownMelonStrategy.__dict__.items() if callable(v)} == {"crop_plan"}
    assert p.CAPS is free_straw.CAPS_S and p.melon_windows() is sm.MELON_WINDOWS
    assert p.fertilize_crops(16) == SecondMelonStrategy().fertilize_crops(16)


def test_registered():
    from strategies import load
    assert load("town_melon") is tm.TownMelonStrategy
