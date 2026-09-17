"""town_split (#305): the town's drain sets the herd's sheep share, nothing else."""

from __future__ import annotations

import pytest

from strategies import town_split as ts
from strategies.four_at_eight import FourAtEightStrategy


def test_sheep_share_is_the_wool_drain_over_the_wool_and_milk_drain():
    assert ts.sheep_share(["BAKERY", "BRUNCH_SPOT"]) is None
    assert ts.sheep_share([]) is None and ts.sheep_share(None) is None
    assert ts.sheep_share(["YARN_STORE"]) == 1.0
    assert ts.sheep_share(["PIZZA_SHOP"]) == 0.0
    assert ts.sheep_share(["YARN_STORE", "PIZZA_SHOP"]) == pytest.approx(2 / 3)          # 12 / (12 + 6)
    assert ts.sheep_share(["YARN_STORE", "ICE_CREAM_SHOP", "PIZZA_SHOP", "SMOOTHIE_SHOP"]) == pytest.approx(0.4)
    assert ts.sheep_share(["YARN_STORE", "YARN_STORE", "PIZZA_SHOP"]) == pytest.approx(0.8)


def _buys(share, cows, sheep, n):
    out = []
    for _ in range(n):
        k = ts.split_kind(share, cows, sheep)
        out.append(k[0])
        cows, sheep = (cows + 1, sheep) if k == "COW" else (cows, sheep + 1)
    return "".join(out), (cows, sheep)


def test_split_kind_walks_the_herd_to_its_share_from_the_frozen_day_0_herd():
    assert _buys(1.0, 1, 3, 8) == ("SSSSSSSS", (1, 11))
    assert _buys(0.0, 1, 3, 8) == ("CCCCCCCC", (9, 3))
    assert _buys(2 / 3, 1, 3, 8) == ("SCSSCSSC", (4, 8))
    assert _buys(0.4, 1, 3, 8) == ("CCCSCCSC", (7, 5))
    assert ts.split_kind(0.5, 0, 0) == "SHEEP" and ts.split_kind(0.5, 0, 1) == "COW"


def _tiles(*animals):
    row = [{"animal": a} if a else None for a in animals]
    return [row + ["LOCKED", {"kind": "WEED"}]]


def _obs(shops, *animals, shed=None, rival_sheep=0, player=1):
    rival = [[{"animal": "SHEEP"}] * rival_sheep]
    ours = _tiles(*animals)
    farms = [{"tiles": rival}, {"tiles": ours}] if player == 1 else [{"tiles": ours}, {"tiles": rival}]
    return {"player": player, "farms": farms, "private": {"shed": shed or {}},
            "town": {"unlocked_shops": list(shops)}}


def test_herd_preference_reads_the_town_and_our_farm():
    p = ts.TownSplitStrategy()
    assert p.name == "town_split" and isinstance(p, FourAtEightStrategy) and p.FOURTH_DAY == 8
    assert p.sheep_share(["YARN_STORE", "PIZZA_SHOP"]) == pytest.approx(2 / 3)
    assert p.owned(_obs([], "COW", "SHEEP", "SHEEP", shed={"COW": 2})) == (3, 2)
    assert p.herd_preference(_obs(["YARN_STORE"], "COW", "SHEEP", "SHEEP", "SHEEP")) == "SHEEP"
    assert p.herd_preference(_obs(["PIZZA_SHOP"], "COW", "SHEEP", "SHEEP", "SHEEP")) == "COW"
    assert p.herd_preference(_obs(["YARN_STORE", "PIZZA_SHOP"], "COW", "SHEEP", "SHEEP", "SHEEP")) == "SHEEP"   # 3 < 3.33
    assert p.herd_preference(_obs(["YARN_STORE", "PIZZA_SHOP"], "COW", "SHEEP", "SHEEP", "SHEEP", shed={"SHEEP": 1})) == "COW"  # 4 < 4 is false


def test_herd_preference_falls_through_to_the_inherited_rule_when_the_town_is_silent():
    p = ts.TownSplitStrategy()
    assert p.herd_preference(_obs(["BAKERY", "PET_CAFE"], "COW", rival_sheep=0)) is None
    assert p.herd_preference(_obs(["BAKERY", "PET_CAFE"], "COW", rival_sheep=2)) == "COW"   # rival_aware's rule
    assert p.herd_preference(_obs(["YARN_STORE"], rival_sheep=9)) == "SHEEP"                 # the town outranks the rival


def test_herd_preference_degrades_to_the_inherited_rule_on_a_malformed_observation():
    p = ts.TownSplitStrategy()
    assert p.herd_preference({}) is None
    assert p.herd_preference({"player": 3, "farms": [], "private": None, "town": None}) is None
    assert p.herd_preference({"player": 0, "farms": [{"tiles": None}, "x"], "town": {"unlocked_shops": "YARN_STORE"}}) is None


def test_every_other_seam_is_four_at_eights():
    from harness import sheep_bench as sb
    assert set(ts.TownSplitStrategy.__dict__) & set(sb._seam_names()) == {"herd_preference"}
    p, q = ts.TownSplitStrategy(), FourAtEightStrategy()
    assert p.livestock_workers(8) == q.livestock_workers(8) and p.CAPS == q.CAPS and p.buy_order() == q.buy_order()


def test_registered():
    from strategies import load
    assert load("town_split") is ts.TownSplitStrategy
