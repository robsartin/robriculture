"""Claim check: the installed sim must be the version `requirements.txt` pins (#133).

Every other claim-check in this repo compares `kaggisim/` against *whatever*
`kaggle_environments` happens to be importable, and says nothing about which
version that is. When a local venv drifted to 1.32.7 while the pin said 1.32.4,
that produced a genuinely confusing three-way disagreement: the claim-checks
failed locally, passed in CI, and "fixing" `economy.py` to satisfy one broke the
other -- with the assertion message exactly inverted between them.

    local : AssertionError: TOMATO.below_func is 'linear', sim is 'hinge'
    CI    : AssertionError: TOMATO.below_func is 'hinge',  sim is 'linear'

Worse, it silently invalidated a session's worth of measurements: the champion
benchmarked at 0.5222 on the drifted sim and 0.3325 on the pinned one. Nothing
warned that those numbers came from different simulators.

This test turns that into one line. It is deliberately about the *environment*,
not the code -- it fails when the venv needs syncing, and the fix is
`pip install -r requirements.txt`, never an edit to `kaggisim/`.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REQUIREMENTS = Path(__file__).resolve().parent.parent / "requirements.txt"
PACKAGE = "kaggle-environments"


def pinned_version(text: str) -> str | None:
    """The `==` pin for the sim in a requirements file, or None if unpinned.

    Pure and unit-tested: parsing is the part worth pinning, since a silently
    unparsed line would make this whole guard vacuous.
    """
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        m = re.match(rf"^{re.escape(PACKAGE)}\s*==\s*([\w.]+)$", line)
        if m:
            return m.group(1)
    return None


def installed_version() -> str:
    from importlib.metadata import version
    return version(PACKAGE)


def test_pinned_version_is_parsed_from_requirements():
    """The parser finds the pin, ignoring comments and unrelated packages."""
    text = "# a comment\nnumpy==2.4.4\nkaggle-environments==1.32.4  # trailing note\n"
    assert pinned_version(text) == "1.32.4"


def test_pinned_version_is_none_when_the_sim_is_unpinned():
    """A `>=` or absent requirement is not a pin, and must not read as one --
    otherwise the guard below would compare against a version nobody fixed."""
    assert pinned_version("kaggle-environments>=1.32.4\n") is None
    assert pinned_version("numpy==2.4.4\n") is None


def test_a_commented_out_pin_does_not_count():
    """The whole line is a comment; there is no pin in force."""
    assert pinned_version("# kaggle-environments==1.32.4\n") is None


def test_installed_sim_matches_the_requirements_pin():
    """The environment check itself.

    If this fails, the venv is out of sync -- run `pip install -r
    requirements.txt`. Do NOT change `kaggisim/` to match a drifted install;
    that is what #133 did, and CI rejected it with the assertion inverted.
    """
    pin = pinned_version(REQUIREMENTS.read_text())
    if pin is None:
        pytest.skip("kaggle-environments is not pinned in requirements.txt")
    assert installed_version() == pin, (
        f"installed kaggle-environments is {installed_version()}, "
        f"requirements.txt pins {pin}. Run `pip install -r requirements.txt`. "
        "Do not edit kaggisim/ to match a drifted install -- the other "
        "claim-checks compare against whatever is installed, so they will "
        "happily agree with the wrong simulator (#133)."
    )
