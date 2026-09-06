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


def test_every_member_names_its_source():
    for m in _members():
        assert m["source"] in ("recorded", "fresh"), m
        if m["source"] == "fresh":
            assert m["issue"] == 172 and m["opponent"] == "meta_bot" and m["games"] == 16, m


def test_meta_rancher_notes_its_zero_wins_are_ties_not_losses():
    # meta_rancher is behaviourally identical to meta_bot (every game a tie,
    # since 5130174), so its 0/16 fresh row would otherwise read as a clean
    # loss. The row must say so.
    members = {m["name"]: m for m in _members()}
    assert members["meta_rancher"].get("note"), members["meta_rancher"]
