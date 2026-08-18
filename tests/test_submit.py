"""Unit tests for scripts/submit.py (issue #21).

The build + submit flow is exercised with injected fakes for the build, smoke
test, git SHA and the Kaggle CLI runner, so nothing here touches the network,
the Kaggle CLI, or the real packaging subprocess.
"""

from __future__ import annotations

import json
import types

import pytest

from scripts import submit


# --- pure helpers ---

def test_load_submit_default_reads_the_submit_default_field(tmp_path):
    """submit.py packages the submit default, never the gate opponent."""
    p = tmp_path / "champion.json"
    p.write_text(json.dumps({"gate_opponent": "meta_bot", "submit_default": "mixed_hands"}))
    assert submit.load_submit_default(str(p)) == "mixed_hands"


def test_load_submit_default_raises_on_an_old_format_artifact(tmp_path):
    """A stale artifact must not silently resolve to the old champion field."""
    p = tmp_path / "champion.json"
    p.write_text(json.dumps({"champion": "market_farmer"}))
    with pytest.raises(ValueError, match="re-designate"):
        submit.load_submit_default(str(p))


def test_prepare_refuses_a_benchmark_strategy():
    """Belt and braces: even a hand-edited artifact cannot submit a vendored agent.

    meta_bot is someone else's code, vendored readonly under their license
    (ADR-0005). Packaging it under our name is a licensing problem, not a bad
    score, so the cost of getting this wrong is asymmetric.
    """
    with pytest.raises(SystemExit, match="benchmark"):
        submit.prepare("meta_bot", out=None)


def test_prepare_refuses_a_hand_edited_artifact_with_a_benchmark_submit_default(tmp_path):
    """The no-strategy-argument path must be guarded too, not just the explicit name.

    A hand-edited `champion.json` could set `submit_default` to a vendored
    benchmark directly; `prepare(None, ...)` resolves that default and must
    refuse it exactly as it refuses an explicit benchmark name.
    """
    p = tmp_path / "champion.json"
    p.write_text(json.dumps({"gate_opponent": "meta_bot", "submit_default": "meta_bot"}))
    with pytest.raises(SystemExit, match="benchmark"):
        submit.prepare(None, out=None, champion_path=str(p))


def test_default_message_is_strategy_then_short_sha():
    assert submit.default_message("dairy_hands", "abc1234") == "dairy_hands abc1234"


def test_submit_command_is_the_kaggle_cli_invocation():
    cmd = submit.submit_command("dist/x.tar.gz", "a note")
    assert cmd == [
        "kaggle", "competitions", "submit", "kaggriculture",
        "-f", "dist/x.tar.gz", "-m", "a note",
    ]


def test_prepare_defaults_strategy_to_submit_default_and_out_to_dist(tmp_path):
    p = tmp_path / "champion.json"
    p.write_text('{"gate_opponent": "meta_bot", "submit_default": "wide_hands"}')
    strategy, out = submit.prepare(None, None, champion_path=str(p))
    assert strategy == "wide_hands"
    assert out.replace("\\", "/").endswith("dist/wide_hands.tar.gz")


def test_prepare_honors_explicit_strategy_and_out():
    strategy, out = submit.prepare("dairy_hands", "/tmp/d.tar.gz")
    assert strategy == "dairy_hands"
    assert out == "/tmp/d.tar.gz"


# --- run(): orchestration with injected dependencies ---

def _ok_runner(record):
    def runner(cmd):
        record["submit"] = cmd
        return types.SimpleNamespace(returncode=0)
    return runner


def test_dry_run_builds_and_smokes_but_never_submits():
    rec = {}
    cmd = submit.run(
        "dairy_hands", message="m", out="/tmp/d.tar.gz", dry_run=True,
        build_fn=lambda s, o: rec.setdefault("build", (s, o)),
        smoke_fn=lambda o: rec.setdefault("smoke", o) or True,
        runner=_ok_runner(rec),
    )
    assert rec["build"] == ("dairy_hands", "/tmp/d.tar.gz")
    assert rec["smoke"] == "/tmp/d.tar.gz"
    assert "submit" not in rec  # dry-run must not submit
    assert cmd[:4] == ["kaggle", "competitions", "submit", "kaggriculture"]


def test_run_submits_when_not_dry_run():
    rec = {}
    submit.run(
        "mixed_hands", message="m", out="/tmp/m.tar.gz",
        build_fn=lambda s, o: None, smoke_fn=lambda o: True, runner=_ok_runner(rec),
    )
    assert rec["submit"][:3] == ["kaggle", "competitions", "submit"]
    assert "/tmp/m.tar.gz" in rec["submit"]


def test_run_uses_default_message_when_none_given():
    rec = {}
    submit.run(
        "dairy_hands", out="/tmp/d.tar.gz",
        build_fn=lambda s, o: None, smoke_fn=lambda o: True,
        sha_fn=lambda: "deadbee", runner=_ok_runner(rec),
    )
    assert "dairy_hands deadbee" in rec["submit"]


def test_run_aborts_and_does_not_submit_when_smoke_fails():
    rec = {}
    with pytest.raises(SystemExit):
        submit.run(
            "x", message="m", out="/tmp/x.tar.gz",
            build_fn=lambda s, o: None, smoke_fn=lambda o: False, runner=_ok_runner(rec),
        )
    assert "submit" not in rec  # a failed smoke must block submission


def test_run_can_skip_the_smoke_test():
    rec = {}
    submit.run(
        "x", message="m", out="/tmp/x.tar.gz", no_smoke=True,
        build_fn=lambda s, o: None,
        smoke_fn=lambda o: pytest.fail("smoke must not run with no_smoke=True"),
        runner=_ok_runner(rec),
    )
    assert "submit" in rec


def test_run_raises_when_kaggle_submit_exits_nonzero():
    with pytest.raises(SystemExit):
        submit.run(
            "x", message="m", out="/tmp/x.tar.gz",
            build_fn=lambda s, o: None, smoke_fn=lambda o: True,
            runner=lambda cmd: types.SimpleNamespace(returncode=1),
        )
