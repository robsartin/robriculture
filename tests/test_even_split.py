"""even_split (#310): a half share whenever the town takes both, nothing else."""

from __future__ import annotations

from strategies import even_split as es
from strategies.town_split import TownSplitStrategy


def test_even_share_is_a_half_whenever_the_town_takes_both():
    assert es.even_share(["BAKERY", "BRUNCH_SPOT"]) is None and es.even_share([]) is None and es.even_share(None) is None
    assert es.even_share(["YARN_STORE"]) == 1.0 and es.even_share(["YARN_STORE", "YARN_STORE"]) == 1.0
    assert es.even_share(["PIZZA_SHOP"]) == 0.0 and es.even_share(["SMOOTHIE_SHOP", "ICE_CREAM_SHOP"]) == 0.0
    assert es.even_share(["YARN_STORE", "PIZZA_SHOP"]) == 0.5
    assert es.even_share(["YARN_STORE", "YARN_STORE", "PIZZA_SHOP", "SMOOTHIE_SHOP", "ICE_CREAM_SHOP"]) == 0.5


def _tiles(*animals):
    row = [{"animal": a} if a else None for a in animals]
    return [row + ["LOCKED", {"kind": "WEED"}]]


def _obs(shops, *animals, shed=None, rival_sheep=0, player=1):
    rival = [[{"animal": "SHEEP"}] * rival_sheep]
    ours = _tiles(*animals)
    farms = [{"tiles": rival}, {"tiles": ours}] if player == 1 else [{"tiles": ours}, {"tiles": rival}]
    return {"player": player, "farms": farms, "private": {"shed": shed or {}},
            "town": {"unlocked_shops": list(shops)}}


def _walk(p, shops, cows, sheep, n):
    out = []
    for _ in range(n):
        k = p.herd_preference(_obs(shops, *(["COW"] * cows + ["SHEEP"] * sheep)))
        out.append(k[0])
        cows, sheep = (cows + 1, sheep) if k == "COW" else (cows, sheep + 1)
    return "".join(out), (cows, sheep)


def test_herd_preference_walks_the_day_0_herd_to_even_and_to_all_sheep():
    p = es.EvenSplitStrategy()
    assert p.name == "even_split" and isinstance(p, TownSplitStrategy) and p.FOURTH_DAY == 8
    assert p.sheep_share(["YARN_STORE", "PIZZA_SHOP", "PIZZA_SHOP", "PIZZA_SHOP"]) == 0.5
    assert _walk(p, ["YARN_STORE", "PIZZA_SHOP"], 1, 3, 8) == ("CCSCSCSC", (6, 6))
    assert _walk(p, ["YARN_STORE"], 1, 3, 8) == ("SSSSSSSS", (1, 11))
    assert _walk(p, ["PIZZA_SHOP"], 1, 3, 8) == ("CCCCCCCC", (9, 3))


def test_herd_preference_falls_through_to_the_inherited_rule():
    p = es.EvenSplitStrategy()
    assert p.herd_preference(_obs(["BAKERY", "PET_CAFE"], "COW", rival_sheep=0)) is None
    assert p.herd_preference(_obs(["BAKERY", "PET_CAFE"], "COW", rival_sheep=2)) == "COW"   # rival_aware's rule
    assert p.herd_preference({}) is None
    assert p.herd_preference({"player": 3, "farms": [], "private": None, "town": None}) is None


def test_the_class_defines_no_seam_of_its_own():
    from harness import sheep_bench as sb
    assert set(es.EvenSplitStrategy.__dict__) & set(sb._seam_names()) == set()
    assert set(es.EvenSplitStrategy.__dict__) >= {"sheep_share", "name"}
    p, q = es.EvenSplitStrategy(), TownSplitStrategy()
    assert p.livestock_workers(8) == q.livestock_workers(8) and p.CAPS == q.CAPS and p.buy_order() == q.buy_order()


def test_registered():
    from strategies import load
    assert load("even_split") is es.EvenSplitStrategy
