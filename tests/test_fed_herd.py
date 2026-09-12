"""fed_herd (#270): two feedings in the shed, and nothing else."""

from __future__ import annotations

from strategies import fed_herd as fh
from strategies.lean_feed import LeanFeedStrategy


def test_stock_is_two_feedings_never_below_one():
    assert fh.FEEDINGS == 2
    assert fh.stock_for_fed(4) == 8 and fh.stock_for_fed(11) == 22 and fh.stock_for_fed(0) == 1


def test_only_the_stock_seam_is_overridden():
    from harness.sheep_bench import _seam_names
    assert set(fh.FedHerdStrategy.__dict__) & set(_seam_names()) == {"feed_stock"}
    p, q = fh.FedHerdStrategy(), LeanFeedStrategy()
    assert p.name == "fed_herd" and isinstance(p, LeanFeedStrategy)
    assert p.feed_stock(animals=9) == 18 and q.feed_stock(animals=9) == 9
    assert p.feed_stock() == 1
    assert p.feed_carry(9, 3) == q.feed_carry(9, 3) == 3
    assert p.herd_preference({}) == q.herd_preference({})


def test_registered():
    from strategies import load
    assert load("fed_herd") is fh.FedHerdStrategy
