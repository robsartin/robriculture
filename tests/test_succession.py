"""Designation by gate succession (#241; ADR-0007 amendment 2026-09-07).

Pool share (#76) ranked a gate-REJECTED contender above one that swept the
incumbent 16/16 once every contender beat the anchors outright — reward share
against opponents that no longer resolve wins is not a ranking of strength.
The champion is now the most recent strategy to PROMOTE through the ADR-0007
gate against the incumbent; `harness/champion.json` records that succession.
"""

from __future__ import annotations

import json
import os

import pytest

from harness import promotion

RECORD = {"wins": 16, "ties": 0, "games": 16, "seeds": "816-831"}


def test_succeed_puts_both_roles_on_the_challenger_and_records_the_succession():
    body = promotion.succeed("third_herder", "rival_aware", issue=239, pr=240,
                             record=RECORD, date="2026-09-07", benchmarks=set())
    assert body["criterion"] == "gate_succession"
    assert body["gate_opponent"] == "third_herder"
    assert body["submit_default"] == "third_herder"
    s = body["succession"]
    assert s["predecessor"] == "rival_aware"
    assert (s["issue"], s["pr"], s["date"]) == (239, 240, "2026-09-07")
    assert s["record"] == dict(RECORD, p=pytest.approx(0.5 ** 16))


def test_succeed_refuses_a_benchmark_challenger():
    """A vendored competitor can be the gate opponent but never the submit default (ADR-0005)."""
    with pytest.raises(ValueError, match="benchmark"):
        promotion.succeed("lonespear", "rival_aware", issue=1, pr=2, record=RECORD,
                          date="2026-09-07", benchmarks={"lonespear"})


def test_succeed_refuses_a_record_below_the_gate_bar():
    """Succession is the gate's verdict restated; a record that did not PROMOTE cannot designate."""
    short = dict(RECORD, wins=9)  # 56.25% < 60%
    with pytest.raises(ValueError, match="bar"):
        promotion.succeed("x", "y", issue=1, pr=2, record=short, date="2026-09-07",
                          benchmarks=set())


def test_succeed_counts_a_tie_as_not_a_win():
    tied = {"wins": 9, "ties": 7, "games": 16, "seeds": "0-15"}  # 9/16, not 9/9
    with pytest.raises(ValueError, match="bar"):
        promotion.succeed("x", "y", issue=1, pr=2, record=tied, date="2026-09-07",
                          benchmarks=set())


def test_save_champion_refuses_to_overwrite_a_succession_with_a_pool_share_body(tmp_path):
    """`--designate` and `harness.rounds` still rank by pool share; neither may
    silently revert the criterion — the failure #76 was itself a fix for."""
    p = tmp_path / "champion.json"
    body = promotion.succeed("b", "a", issue=1, pr=2, record=RECORD, date="2026-09-07",
                             benchmarks=set())
    promotion.save_champion(str(p), body)
    pool = {"criterion": "pool_share", "gate_opponent": "c", "submit_default": "c",
            "games": 2, "pool": [], "ranking": []}
    with pytest.raises(ValueError, match="gate_succession"):
        promotion.save_champion(str(p), pool)
    assert json.loads(p.read_text()) == body


def test_save_champion_lets_a_succession_replace_a_succession(tmp_path):
    p = tmp_path / "champion.json"
    first = promotion.succeed("b", "a", issue=1, pr=2, record=RECORD, date="2026-09-07",
                              benchmarks=set())
    promotion.save_champion(str(p), first)
    second = promotion.succeed("c", "b", issue=3, pr=4, record=RECORD, date="2026-09-08",
                               benchmarks=set())
    promotion.save_champion(str(p), second)
    assert promotion.gate_opponent(str(p)) == "c"


def test_designation_criterion_reads_the_artifact(tmp_path):
    p = tmp_path / "champion.json"
    p.write_text(json.dumps({"criterion": "pool_share", "gate_opponent": "a",
                             "submit_default": "a"}))
    assert promotion.designation_criterion(str(p)) == "pool_share"
    assert promotion.designation_criterion(str(tmp_path / "missing.json")) is None


def test_the_committed_champion_is_a_gate_succession_whose_record_clears_the_bar():
    """The committed artifact must be reproducible from its own fields: rebuild
    the body from the recorded succession and it must say the same thing."""
    with open(promotion.CHAMPION_PATH) as fh:
        data = json.load(fh)
    assert data["criterion"] == "gate_succession"
    s = data["succession"]
    rebuilt = promotion.succeed(data["gate_opponent"], s["predecessor"], issue=s["issue"],
                                pr=s["pr"], record={k: v for k, v in s["record"].items() if k != "p"},
                                date=s["date"])
    assert rebuilt == data
