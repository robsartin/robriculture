"""meta_rancher — tuned contender sibling of the frozen meta_bot benchmark (#61)."""

from __future__ import annotations

from strategies import meta_rancher as mr


def test_meta_rancher_is_a_contender_not_a_benchmark():
    assert mr.STRATEGY.benchmark is False
    assert mr.STRATEGY.name == "meta_rancher"


def test_composition_matches_the_phase0_comp():
    cows = [t for t in mr.ANIMAL_TILES if t[1] == "COW"]
    sheep = [t for t in mr.ANIMAL_TILES if t[1] == "SHEEP"]
    assert len(cows) == mr.N_COW == 9
    assert len(sheep) == mr.N_SHEEP == 4
    assert len({t[0] for t in mr.ANIMAL_TILES}) == len(mr.ANIMAL_TILES)


def test_seed_restock_orders_buys_melon_seed_for_empty_active_plots():
    # Extracted from act(): an empty active melon plot with no seed on hand and
    # money to spare yields a BUY_SEED MELON order.
    tiles = [[None for _ in range(10)] for _ in range(10)]
    orders = mr.seed_restock_orders(
        tiles=tiles, seeds={}, melon_open=True, catch=None,
        n_workers=3, money=100000, market_len=0,
    )
    assert ["BUY_SEED", "MELON", 3] in orders


def test_seed_restock_orders_respects_the_market_cap():
    tiles = [[None for _ in range(10)] for _ in range(10)]
    orders = mr.seed_restock_orders(
        tiles=tiles, seeds={}, melon_open=True, catch=None,
        n_workers=3, money=100000, market_len=10,
    )
    assert orders == []
