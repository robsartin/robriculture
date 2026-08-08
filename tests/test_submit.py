"""Unit tests for scripts/submit.py (issue #21).

The build + submit flow is exercised with injected fakes for the build, smoke
test, git SHA and the Kaggle CLI runner, so nothing here touches the network,
the Kaggle CLI, or the real packaging subprocess.
"""

from __future__ import annotations

import types

import pytest

from scripts import submit


# --- pure helpers ---

def test_load_champion_reads_the_champion_field(tmp_path):
    p = tmp_path / "champion.json"
    p.write_text('{"champion": "mixed_hands", "games": 20, "ranking": []}')
    assert submit.load_champion(str(p)) == "mixed_hands"


def test_default_message_is_strategy_then_short_sha():
    assert submit.default_message("dairy_hands", "abc1234") == "dairy_hands abc1234"


def test_submit_command_is_the_kaggle_cli_invocation():
    cmd = submit.submit_command("dist/x.tar.gz", "a note")
    assert cmd == [
        "kaggle", "competitions", "submit", "kaggriculture",
        "-f", "dist/x.tar.gz", "-m", "a note",
    ]


def test_prepare_defaults_strategy_to_champion_and_out_to_dist(tmp_path):
    p = tmp_path / "champion.json"
    p.write_text('{"champion": "wide_hands"}')
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
