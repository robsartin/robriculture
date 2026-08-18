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
        submissions_fn=lambda: [],
    )
    assert rec["submit"][:3] == ["kaggle", "competitions", "submit"]
    assert "/tmp/m.tar.gz" in rec["submit"]


def test_run_uses_default_message_when_none_given():
    rec = {}
    submit.run(
        "dairy_hands", out="/tmp/d.tar.gz",
        build_fn=lambda s, o: None, smoke_fn=lambda o: True,
        sha_fn=lambda: "deadbee", runner=_ok_runner(rec),
        submissions_fn=lambda: [],
    )
    assert "dairy_hands deadbee" in rec["submit"]


def test_run_aborts_and_does_not_submit_when_smoke_fails():
    rec = {}
    with pytest.raises(SystemExit):
        submit.run(
            "x", message="m", out="/tmp/x.tar.gz",
            build_fn=lambda s, o: None, smoke_fn=lambda o: False, runner=_ok_runner(rec),
            submissions_fn=lambda: [],
        )
    assert "submit" not in rec  # a failed smoke must block submission


def test_run_can_skip_the_smoke_test():
    rec = {}
    submit.run(
        "x", message="m", out="/tmp/x.tar.gz", no_smoke=True,
        build_fn=lambda s, o: None,
        smoke_fn=lambda o: pytest.fail("smoke must not run with no_smoke=True"),
        runner=_ok_runner(rec),
        submissions_fn=lambda: [],
    )
    assert "submit" in rec


def test_run_raises_when_kaggle_submit_exits_nonzero():
    with pytest.raises(SystemExit):
        submit.run(
            "x", message="m", out="/tmp/x.tar.gz",
            build_fn=lambda s, o: None, smoke_fn=lambda o: True,
            runner=lambda cmd: types.SimpleNamespace(returncode=1),
            submissions_fn=lambda: [],
        )


# --- slot awareness (issue #79) ---
#
# `kaggle competitions submissions <comp> --format json` records look like:
#   {"ref": 123, "fileName": "ranch_hands.tar.gz", "date": "2026-08-13T13:21:38.590000",
#    "description": "ranch_hands 97bec79", "status": "SubmissionStatus.COMPLETE",
#    "publicScore": "509.5", "privateScore": ""}
# (confirmed against the real `kaggle` CLI's own JSON output). `parse_submissions`
# isolates that messy, API-shaped input from the pure slot logic below.

def _raw(file_name, date, status="SubmissionStatus.COMPLETE", public_score=""):
    return {
        "ref": 1, "fileName": file_name, "date": date, "description": "",
        "status": status, "publicScore": public_score, "privateScore": "",
    }


# The actual Aug-14 incident from the issue: meta_rancher (561.8, older of the
# live pair) got evicted by neuropilot, silently. Used as a realistic fixture
# below rather than an invented one.
_META_RANCHER = _raw("meta_rancher.tar.gz", "2026-08-13T13:20:38.627000", public_score="561.8")
_RANCH_HANDS = _raw("ranch_hands.tar.gz", "2026-08-13T13:21:38.590000", public_score="509.5")
_MARKET_FARMER_OLD = _raw("market_farmer.tar.gz", "2026-08-11T19:20:59.527000", public_score="476.7")


class TestParseSubmissions:
    def test_strategy_name_derived_from_tarball_filename(self):
        """The strategy name comes from `<strategy>.tar.gz`, the build's own naming (`prepare`)."""
        [rec] = submit.parse_submissions([_raw("dairy_hands.tar.gz", "2026-01-01T00:00:00")])
        assert rec["strategy"] == "dairy_hands"

    def test_status_normalized_from_the_enum_repr(self):
        """Kaggle's JSON status is the str() of a Python enum ('SubmissionStatus.COMPLETE')."""
        [rec] = submit.parse_submissions(
            [_raw("x.tar.gz", "2026-01-01T00:00:00", status="SubmissionStatus.PENDING")]
        )
        assert rec["status"] == "pending"

    def test_score_is_none_when_public_score_is_blank(self):
        """A pending/errored submission has no score yet ('' in the raw JSON)."""
        [rec] = submit.parse_submissions([_raw("x.tar.gz", "2026-01-01T00:00:00", public_score="")])
        assert rec["score"] is None

    def test_score_is_a_float_when_public_score_is_numeric(self):
        """The raw publicScore is a JSON string ('561.8'); we want it comparable."""
        [rec] = submit.parse_submissions([_raw("x.tar.gz", "2026-01-01T00:00:00", public_score="561.8")])
        assert rec["score"] == 561.8


class TestLivePair:
    def test_two_most_recent_complete_returned_newest_first(self):
        """The live pair (ADR-0003) is the two most recent COMPLETE submissions."""
        submissions = submit.parse_submissions([_MARKET_FARMER_OLD, _META_RANCHER, _RANCH_HANDS])
        pair = submit.live_pair(submissions)
        assert [r["strategy"] for r in pair] == ["ranch_hands", "meta_rancher"]

    def test_noncomplete_statuses_excluded_from_the_live_pair(self):
        """A PENDING or ERROR submission is not live and must not occupy a slot."""
        pending = _raw("neuropilot.tar.gz", "2026-08-17T00:00:00", status="SubmissionStatus.PENDING")
        submissions = submit.parse_submissions([pending, _META_RANCHER, _RANCH_HANDS])
        pair = submit.live_pair(submissions)
        assert "neuropilot" not in [r["strategy"] for r in pair]

    def test_fewer_than_two_returned_when_history_is_short(self):
        """Early on (or in a fresh competition) there may be 0 or 1 live submissions."""
        submissions = submit.parse_submissions([_META_RANCHER])
        assert len(submit.live_pair(submissions)) == 1
        assert len(submit.live_pair([])) == 0


class TestBestOf:
    def test_higher_scored_record_returned(self):
        """'Best' picks the higher publicScore among the given records."""
        pair = submit.parse_submissions([_META_RANCHER, _RANCH_HANDS])
        assert submit.best_of(pair)["strategy"] == "meta_rancher"

    def test_none_returned_when_nothing_is_scored_yet(self):
        """A freshly-submitted pair may both be unscored; there is no 'best' yet."""
        unscored = submit.parse_submissions([
            _raw("a.tar.gz", "2026-01-01T00:00:00", public_score=""),
            _raw("b.tar.gz", "2026-01-02T00:00:00", public_score=""),
        ])
        assert submit.best_of(unscored) is None

    def test_unscored_records_ignored_among_scored_peers(self):
        """A mix of scored and not-yet-scored records still picks a real best."""
        mixed = submit.parse_submissions([
            _META_RANCHER,
            _raw("neuropilot.tar.gz", "2026-08-17T00:00:00", public_score=""),
        ])
        assert submit.best_of(mixed)["strategy"] == "meta_rancher"


class TestEvictedBy:
    def test_older_live_submission_is_evicted(self):
        """Reproduces the incident: neuropilot evicts meta_rancher, the older of the pair."""
        submissions = submit.parse_submissions([_META_RANCHER, _RANCH_HANDS])
        evicted = submit.evicted_by("neuropilot", submissions)
        assert evicted["strategy"] == "meta_rancher"

    def test_none_returned_when_fewer_than_two_are_live(self):
        """Submitting a 1st or 2nd-ever agent evicts nothing."""
        submissions = submit.parse_submissions([_META_RANCHER])
        assert submit.evicted_by("neuropilot", submissions) is None

    def test_none_returned_when_resubmitting_the_strategy_that_would_age_out(self):
        """Resubmitting the same strategy that's about to age out loses no distinct agent."""
        submissions = submit.parse_submissions([_META_RANCHER, _RANCH_HANDS])
        assert submit.evicted_by("meta_rancher", submissions) is None


class TestSlotsReport:
    def test_live_pair_and_scores_listed(self):
        """--slots reports the current live pair by name and score."""
        submissions = submit.parse_submissions([_META_RANCHER, _RANCH_HANDS])
        report = submit.slots_report(submissions)
        assert "meta_rancher 561.8" in report
        assert "ranch_hands 509.5" in report

    def test_score_drift_caveat_included(self):
        """ADR-0007: scores drift ~100 points across identical resubmits; say so."""
        report = submit.slots_report(submit.parse_submissions([_META_RANCHER, _RANCH_HANDS]))
        assert "ADR-0007" in report

    def test_no_live_submissions_yet_handled(self):
        """A brand-new competition has no live submissions; must not crash."""
        report = submit.slots_report([])
        assert "no live submissions" in report


class TestSubmissionPreview:
    def test_warning_included_when_evicting_the_best_live_agent(self):
        """The exact incident: submitting neuropilot would evict meta_rancher, the best live agent."""
        submissions = submit.parse_submissions([_META_RANCHER, _RANCH_HANDS])
        text, evicts_best = submit.submission_preview("neuropilot", submissions)
        assert evicts_best is True
        assert "WARNING" in text
        assert "meta_rancher" in text
        assert "561.8" in text

    def test_no_warning_when_the_evicted_agent_is_not_the_best(self):
        """Evicting the *lower*-scored live agent is normal churn, not worth a warning."""
        # ranch_hands (509.5) is older here, so it's the one that ages out; meta_rancher (561.8) stays.
        older_ranch_hands = _raw("ranch_hands.tar.gz", "2026-08-13T13:20:38.627000", public_score="509.5")
        newer_meta_rancher = _raw("meta_rancher.tar.gz", "2026-08-13T13:21:38.590000", public_score="561.8")
        submissions = submit.parse_submissions([older_ranch_hands, newer_meta_rancher])
        text, evicts_best = submit.submission_preview("neuropilot", submissions)
        assert evicts_best is False
        assert "WARNING" not in text

    def test_no_warning_when_resubmitting_the_strategy_that_would_age_out(self):
        """Resubmitting meta_rancher itself is exactly how the incident was fixed; no warning."""
        submissions = submit.parse_submissions([_META_RANCHER, _RANCH_HANDS])
        text, evicts_best = submit.submission_preview("meta_rancher", submissions)
        assert evicts_best is False
        assert "WARNING" not in text

    def test_live_now_and_after_both_shown(self):
        """The preflight preview shows the pair before and after the submission."""
        submissions = submit.parse_submissions([_META_RANCHER, _RANCH_HANDS])
        text, _ = submit.submission_preview("neuropilot", submissions)
        assert "live slots now" in text
        assert "live slots after" in text
        assert "neuropilot" in text


class TestConfirmOrAbort:
    def test_proceeds_silently_when_nothing_is_evicted(self):
        """No eviction risk: never prompt, never require --yes."""
        calls = []
        submit._confirm_or_abort(
            "report text", evicts_best=False, assume_yes=False, isatty=False,
            input_fn=lambda prompt: calls.append(prompt) or "n",
        )
        assert calls == []  # never prompted

    def test_proceeds_when_assume_yes_set_despite_a_warning(self):
        """--yes bypasses the prompt even when the warning fires."""
        calls = []
        submit._confirm_or_abort(
            "report text", evicts_best=True, assume_yes=True, isatty=False,
            input_fn=lambda prompt: calls.append(prompt) or "n",
        )
        assert calls == []  # --yes means we never touch stdin

    def test_refuses_without_blocking_when_noninteractive_and_evicting_best(self):
        """The core non-interactive-safety requirement: never hang on stdin.

        Without a TTY and without --yes, refuse immediately rather than call
        input() — a non-interactive run (cron, script) would otherwise hang
        forever on a prompt nothing will ever answer.
        """
        calls = []

        def never_call(prompt):
            calls.append(prompt)
            return "y"

        with pytest.raises(SystemExit, match="--yes"):
            submit._confirm_or_abort(
                "report text", evicts_best=True, assume_yes=False, isatty=False,
                input_fn=never_call,
            )
        assert calls == []  # input() must never be invoked non-interactively

    def test_proceeds_when_interactive_and_answer_is_y(self):
        """Interactive confirmation: 'y' proceeds."""
        submit._confirm_or_abort(
            "report text", evicts_best=True, assume_yes=False, isatty=True,
            input_fn=lambda prompt: "y",
        )  # must not raise

    def test_aborts_when_interactive_and_answer_is_not_y(self):
        """Interactive confirmation: anything but 'y' (including blank/Enter) aborts."""
        with pytest.raises(SystemExit):
            submit._confirm_or_abort(
                "report text", evicts_best=True, assume_yes=False, isatty=True,
                input_fn=lambda prompt: "",
            )


# --- run(): slot-check integration ---

def test_run_skips_the_slot_check_entirely_on_dry_run():
    """A --dry-run never submits, so it must not fetch submissions or prompt either."""
    calls = []
    submit.run(
        "dairy_hands", message="m", out="/tmp/d.tar.gz", dry_run=True,
        build_fn=lambda s, o: None, smoke_fn=lambda o: True,
        submissions_fn=lambda: calls.append("fetched") or [],
    )
    assert calls == []


def test_run_aborts_before_building_when_confirmation_is_refused():
    """A refused confirmation must stop before the (slow) build, not after."""
    build_calls = []
    with pytest.raises(SystemExit):
        submit.run(
            "neuropilot", message="m", out="/tmp/n.tar.gz",
            build_fn=lambda s, o: build_calls.append((s, o)),
            smoke_fn=lambda o: True,
            submissions_fn=lambda: [_META_RANCHER, _RANCH_HANDS],
            assume_yes=False, isatty_fn=lambda: False,
        )
    assert build_calls == []  # aborted before the build ever ran


def test_run_proceeds_past_a_warning_with_assume_yes():
    """--yes lets a legitimate eviction (e.g. resubmitting to fix the incident) through."""
    rec = {}
    submit.run(
        "meta_rancher", message="m", out="/tmp/m.tar.gz",
        build_fn=lambda s, o: rec.setdefault("build", True),
        smoke_fn=lambda o: True,
        submissions_fn=lambda: [_META_RANCHER, _RANCH_HANDS],
        runner=_ok_runner(rec), assume_yes=True, isatty_fn=lambda: False,
    )
    assert rec["build"] is True
    assert "submit" in rec


def test_run_proceeds_without_prompting_when_nothing_would_be_evicted():
    """No live submissions yet (or <2 live): no warning, no gate, no prompt needed."""
    rec = {}
    submit.run(
        "dairy_hands", message="m", out="/tmp/d.tar.gz",
        build_fn=lambda s, o: rec.setdefault("build", True),
        smoke_fn=lambda o: True,
        submissions_fn=lambda: [],
        runner=_ok_runner(rec),
        isatty_fn=lambda: False,
    )
    assert rec["build"] is True
    assert "submit" in rec
