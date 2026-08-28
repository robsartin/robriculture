"""Pre-measurement machinery checks (#142).

Each test names the incident its check exists to prevent. The pure functions
are tested against fixed strings, so the suite never shells out to git or ps.
"""
from __future__ import annotations

from scripts.preflight import dirty_paths, parse_pins, pin_mismatches, stale_runs


def test_parse_pins_reads_exact_pins_and_ignores_comments():
    """Only `==` is a pin. A `>=` requirement fixes nothing, and treating it as
    a pin would make the check assert something false."""
    text = ("# comment\n"
            "kaggle-environments==1.32.4  # trailing note\n"
            "kaggle>=1.6.0\n"
            "numpy==2.4.4\n")
    assert parse_pins(text) == {"kaggle-environments": "1.32.4", "numpy": "2.4.4"}


def test_parse_pins_ignores_a_commented_out_pin():
    """A commented line is not in force; reporting it would fail every run."""
    assert parse_pins("# kaggle-environments==1.32.4\n") == {}


def test_pin_mismatch_catches_the_133_drift():
    """The incident: a local venv on 1.32.7 against a 1.32.4 pin. Every
    claim-check compares kaggisim/ to whatever is installed, so the drift was
    invisible and a session of numbers was measured on the wrong simulator."""
    bad = pin_mismatches({"kaggle-environments": "1.32.4"},
                         {"kaggle-environments": "1.32.7"})
    assert bad == [("kaggle-environments", "1.32.4", "1.32.7")]


def test_pin_mismatch_reports_a_missing_package():
    """Absent is not the same as wrong, and the message must distinguish them
    -- one needs installing, the other downgrading."""
    assert pin_mismatches({"scipy": "1.18.0"}, {"scipy": None}) == [("scipy", "1.18.0", None)]


def test_pin_mismatch_is_empty_when_everything_matches():
    """Non-vacuity guard: the check must be able to pass, or it is just noise."""
    assert pin_mismatches({"numpy": "2.4.4"}, {"numpy": "2.4.4"}) == []


def test_dirty_paths_catches_the_129_leftover():
    """The incident: a rejected experiment was 'discarded' with git branch -D,
    but the work was never committed, so the branch was empty and the rejected
    code stayed in the tree. The next measurement ran against it."""
    status = " M strategies/neuropilot.py\n M tests/test_neuropilot.py\n"
    assert dirty_paths(status) == ["strategies/neuropilot.py", "tests/test_neuropilot.py"]


def test_dirty_paths_sees_untracked_files_too():
    """An untracked new module is just as capable of changing a measurement as
    a modified one."""
    assert dirty_paths("?? harness/experimental.py\n") == ["harness/experimental.py"]


def test_dirty_paths_is_empty_on_a_clean_tree():
    assert dirty_paths("") == []


def test_stale_runs_catches_a_live_experiment():
    """The incident: a 14-hour run was reading strategies/ from the working
    tree when a branch switch changed the file underneath it."""
    ps = ("/usr/bin/python -m harness.multi_seed --seeds 10\n"
          "/usr/bin/python -c import sys\n")
    hits = stale_runs(ps)
    assert len(hits) == 1 and "multi_seed" in hits[0]


def test_stale_runs_ignores_preflight_itself():
    """Otherwise the check reports itself and can never pass."""
    assert stale_runs("python -m scripts.preflight --tests\n") == []


def test_stale_runs_is_empty_when_nothing_is_running():
    assert stale_runs("bash\nvim notes.md\n") == []
