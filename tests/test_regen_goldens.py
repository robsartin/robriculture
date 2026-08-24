"""Golden-regeneration helper for the champion-genome guard (#115)."""
from __future__ import annotations

from scripts.regen_goldens import stale_scenarios


def _act_from(table):
    """An `act` stand-in that reads a fixed table, so these tests never load
    the real genome or play a game."""
    return lambda name: table[name]


def test_stale_scenarios_is_empty_when_every_golden_matches():
    # The normal state of a healthy branch: nothing to re-bless.
    table = {"a": {"farmer": ["PASS"]}, "b": {"farmer": ["WATER"]}}
    assert stale_scenarios(list(table), _act_from(table), dict(table)) == []


def test_stale_scenarios_names_only_the_ones_that_moved():
    # Re-blessing must be surgical: an unrelated scenario drifting is the
    # signal that a change was broader than intended, so the report has to
    # distinguish which moved rather than say "something did".
    fresh = {"a": {"farmer": ["PASS"]}, "b": {"farmer": ["HARVEST"]}}
    current = {"a": {"farmer": ["PASS"]}, "b": {"farmer": ["WATER"]}}
    assert stale_scenarios(list(fresh), _act_from(fresh), current) == ["b"]


def test_stale_scenarios_treats_a_missing_golden_as_stale():
    # A newly added scenario has no golden yet; it must show up as needing
    # one rather than silently reporting clean.
    fresh = {"a": {"farmer": ["PASS"]}, "new": {"farmer": ["DIG"]}}
    assert stale_scenarios(list(fresh), _act_from(fresh), {"a": fresh["a"]}) == ["new"]
