"""sheep_first (#268): the sheep count and the one seam it drives."""

from __future__ import annotations

from strategies import field_rival as fr
from strategies import sheep_first as sf
from strategies.lean_feed import LeanFeedStrategy


def _tiles(*animals):
    row = [{"animal": a} if a else None for a in animals]
    return [row + ["LOCKED", {"kind": "WEED"}]]


def test_our_sheep_counts_placed_and_pending_sheep_only():
    assert sf.our_sheep(_tiles("SHEEP", "SHEEP", "COW", None), {"SHEEP": 2, "COW": 5}) == 4
    assert sf.our_sheep(_tiles("COW"), {}) == 0
    assert sf.our_sheep([], None) == 0


def _obs(*animals, shed=None):
    return {"player": 1, "farms": [{"tiles": [[{"animal": "SHEEP"}] * 9]}, {"tiles": _tiles(*animals)}],
            "private": {"shed": shed or {}}}


def test_herd_preference_is_sheep_until_six_then_cow_and_never_reads_the_rival():
    p = sf.SheepFirstStrategy()
    assert p.name == "sheep_first" and sf.SHEEP_TARGET == 6 and isinstance(p, LeanFeedStrategy)
    assert p.herd_preference(_obs("SHEEP", "SHEEP", "SHEEP", "COW", shed={"SHEEP": 2})) == "SHEEP"   # 5
    assert p.herd_preference(_obs("SHEEP", "SHEEP", "SHEEP", "COW", shed={"SHEEP": 3})) == "COW"     # 6
    assert p.herd_preference(_obs("SHEEP", "SHEEP", "SHEEP", "SHEEP", "SHEEP", "SHEEP", "SHEEP")) == "COW"
    # the rival's nine sheep in farm 0 change nothing: the rule reads only our farm


def test_herd_preference_degrades_to_sheep_on_a_malformed_observation():
    p = sf.SheepFirstStrategy()
    assert p.herd_preference({}) == "SHEEP"
    assert p.herd_preference({"player": 3, "farms": [], "private": None}) == "SHEEP"


def test_every_other_seam_is_lean_feeds():
    p, q = sf.SheepFirstStrategy(), LeanFeedStrategy()
    for day in (0, 6, 8, 12, 16):
        assert p.herd_target(day) == q.herd_target(day) and p.hire_target(day) == q.hire_target(day)
    assert p.buy_order() == q.buy_order() and p.feed_carry(8, 3) == q.feed_carry(8, 3) and p.layout() == q.layout()
    assert fr.FieldRivalStrategy.herd_preference(p, {}) is None


def test_registered():
    from strategies import load
    assert load("sheep_first") is sf.SheepFirstStrategy
