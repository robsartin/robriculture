"""The calibration data must be citable and shaped so the sample size is
visible: wins/games with the issue each number came from (#172 Stage 2)."""

from __future__ import annotations

import json

from harness import triage
from strategies import REGISTRY


def _members():
    return json.load(open(triage.VERDICTS_PATH))["members"]


def test_every_member_is_a_registered_strategy_with_a_cited_issue():
    members = _members()
    assert members, "POSITIVE CONTROL: no members, nothing to check"
    for m in members:
        assert m["name"] in REGISTRY, m
        assert isinstance(m["issue"], int) and m["issue"] > 0, m
        assert isinstance(m["wins"], int) and isinstance(m["games"], int), m
        assert 0 <= m["wins"] <= m["games"] and m["games"] > 0, m


def test_load_verdicts_returns_rates_by_name():
    rates = triage.load_verdicts()
    members = _members()
    assert set(rates) == {m["name"] for m in members}
    for m in members:
        assert rates[m["name"]] == m["wins"] / m["games"]


def test_no_member_is_duplicated():
    names = [m["name"] for m in _members()]
    assert len(names) == len(set(names))
