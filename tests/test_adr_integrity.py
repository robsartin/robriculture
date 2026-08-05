"""ADR-honesty checks: keep the ADR set internally consistent.

These are pure file/parsing checks over ``docs/adr/`` — no simulator import, no
network, stdlib only — so they run fast anywhere and gate every push/PR (#3).

Each check is a small helper that takes an ADR directory and returns a list of
human-readable problems (empty == clean). That shape lets every check be proven
two ways: it must report *nothing* for the real ``docs/adr/`` (the ADRs are
well-formed today) and it must *catch* a deliberately-broken copy of the same
docs in a tmp fixture.

What we verify:
  1. Index integrity   — the README index and the NNNN-*.md files are in exact
                          correspondence (no orphan files, no dangling rows).
  2. Status consistency — each ADR's own Status matches its index row's Status.
  3. Structural lint    — each ADR has the required sections and a valid Status.
  4. Superseded pointers— any "Superseded by ADR-NNNN" points at a file present.

TODO(#3 stretch): claim checks — assert concrete facts an ADR transcribes from
code (e.g. ADR-0002 economy constants vs ``kaggisim/economy.py``) still match.
Left for a future ticket; deliberately not implemented here.

Run:  pytest -q tests/test_adr_integrity.py
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest

ADR_DIR = Path(__file__).resolve().parent.parent / "docs" / "adr"
TEMPLATE = "0000-template.md"

# A file is an ADR (not the template) iff its name is NNNN-<slug>.md, NNNN != 0000.
_ADR_NAME = re.compile(r"^(\d{4})-.+\.md$")
_STATUS_LINE = re.compile(r"^- \*\*Status:\*\*\s*(.+?)\s*$", re.MULTILINE)
_META_LINE = r"^- \*\*{label}:\*\*\s*\S"
_SECTION = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
# Index rows look like:  | [0002](0002-foo.md) | Title | Status |
_INDEX_ROW = re.compile(
    r"^\|\s*\[(\d{4})\]\(([^)]+)\)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*$",
    re.MULTILINE,
)
_SUPERSEDED = re.compile(r"^Superseded by ADR-(\d{4})$")

REQUIRED_META = ("Status", "Date", "Deciders")
REQUIRED_SECTIONS = ("Context", "Decision", "Consequences", "Alternatives")
SIMPLE_STATUSES = ("Proposed", "Accepted", "Deprecated")


# --- parsing helpers ---------------------------------------------------------

def _adr_files(adr_dir: Path) -> list[Path]:
    """Every real ADR file (NNNN-*.md), excluding the 0000 template, sorted."""
    return sorted(
        p
        for p in adr_dir.glob("*.md")
        if _ADR_NAME.match(p.name) and p.name != TEMPLATE
    )


def _file_status(text: str) -> str | None:
    m = _STATUS_LINE.search(text)
    return m.group(1) if m else None


def _index_rows(adr_dir: Path) -> list[tuple[str, str, str]]:
    """Parse the README index table -> list of (filename, title, status)."""
    readme = (adr_dir / "README.md").read_text(encoding="utf-8")
    return [(m.group(2), m.group(3), m.group(4)) for m in _INDEX_ROW.finditer(readme)]


def _status_is_valid(status: str) -> bool:
    if status in SIMPLE_STATUSES:
        return True
    return bool(_SUPERSEDED.match(status))


# --- checks (each returns a list of problems; empty == clean) ----------------

def check_index_integrity(adr_dir: Path) -> list[str]:
    """Files and index rows must be in exact correspondence, both directions."""
    problems: list[str] = []
    files = {p.name for p in _adr_files(adr_dir)}
    rows = _index_rows(adr_dir)
    indexed = {fname for fname, _title, _status in rows}

    for missing in sorted(files - indexed):
        problems.append(f"ADR file {missing!r} is not listed in README index")
    for dangling in sorted(indexed - files):
        problems.append(f"README index row points at missing file {dangling!r}")
    for fname, _title, _status in rows:
        if not (adr_dir / fname).exists():
            problems.append(f"README index row target does not exist: {fname!r}")
    return problems


def check_status_consistency(adr_dir: Path) -> list[str]:
    """Each ADR's own Status line must match the Status in its index row."""
    problems: list[str] = []
    index_status = {fname: status for fname, _title, status in _index_rows(adr_dir)}
    for path in _adr_files(adr_dir):
        file_status = _file_status(path.read_text(encoding="utf-8"))
        row_status = index_status.get(path.name)
        if row_status is None:
            continue  # index-integrity check owns the "missing row" report
        if file_status != row_status:
            problems.append(
                f"{path.name}: Status {file_status!r} in file "
                f"!= {row_status!r} in README index"
            )
    return problems


def check_structural_lint(adr_dir: Path) -> list[str]:
    """Each ADR has the required metadata, sections, and a valid Status value."""
    problems: list[str] = []
    for path in _adr_files(adr_dir):
        text = path.read_text(encoding="utf-8")

        for label in REQUIRED_META:
            if not re.search(_META_LINE.format(label=label), text, re.MULTILINE):
                problems.append(f"{path.name}: missing '{label}' metadata line")

        headers = _SECTION.findall(text)
        for section in REQUIRED_SECTIONS:
            if not any(h == section or h.startswith(section) for h in headers):
                problems.append(f"{path.name}: missing '## {section}' section")

        status = _file_status(text)
        if status is None:
            problems.append(f"{path.name}: no Status line")
        elif not _status_is_valid(status):
            problems.append(f"{path.name}: invalid Status value {status!r}")
    return problems


def check_superseded_pointers(adr_dir: Path) -> list[str]:
    """Any 'Superseded by ADR-NNNN' status must point at an existing ADR file."""
    problems: list[str] = []
    for path in _adr_files(adr_dir):
        status = _file_status(path.read_text(encoding="utf-8")) or ""
        m = _SUPERSEDED.match(status)
        if not m:
            continue
        target = m.group(1)
        if not list(adr_dir.glob(f"{target}-*.md")):
            problems.append(
                f"{path.name}: Status references ADR-{target}, which does not exist"
            )
    return problems


CHECKS = (
    check_index_integrity,
    check_status_consistency,
    check_structural_lint,
    check_superseded_pointers,
)


# --- fixtures ----------------------------------------------------------------

@pytest.fixture
def adr_copy(tmp_path: Path) -> Path:
    """A writable copy of the real docs/adr so tests can break it in isolation."""
    dst = tmp_path / "adr"
    shutil.copytree(ADR_DIR, dst)
    return dst


# --- the real docs must be clean (the green assertions) ----------------------

@pytest.mark.parametrize("check", CHECKS, ids=lambda c: c.__name__)
def test_real_docs_pass_every_check(check):
    assert check(ADR_DIR) == []


# --- each check must catch a deliberately-broken copy (the red-detection) -----

def test_index_integrity_catches_orphan_file(adr_copy):
    (adr_copy / "0099-orphan-not-in-index.md").write_text(
        "# ADR-0099: Orphan\n\n- **Status:** Accepted\n", encoding="utf-8"
    )
    problems = check_index_integrity(adr_copy)
    assert any("0099" in p for p in problems), problems


def test_index_integrity_catches_dangling_row(adr_copy):
    readme = adr_copy / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8")
        + "| [0098](0098-ghost.md) | Ghost | Accepted |\n",
        encoding="utf-8",
    )
    problems = check_index_integrity(adr_copy)
    assert any("0098-ghost.md" in p for p in problems), problems


def test_status_consistency_catches_mismatch(adr_copy):
    target = _adr_files(adr_copy)[0]
    text = target.read_text(encoding="utf-8")
    target.write_text(
        text.replace("- **Status:** Accepted", "- **Status:** Deprecated", 1),
        encoding="utf-8",
    )
    problems = check_status_consistency(adr_copy)
    assert any(target.name in p for p in problems), problems


def test_structural_lint_catches_missing_section(adr_copy):
    target = _adr_files(adr_copy)[0]
    text = target.read_text(encoding="utf-8")
    target.write_text(text.replace("## Consequences", "## Ramifications", 1), encoding="utf-8")
    problems = check_structural_lint(adr_copy)
    assert any("Consequences" in p and target.name in p for p in problems), problems


def test_structural_lint_catches_invalid_status(adr_copy):
    target = _adr_files(adr_copy)[0]
    text = target.read_text(encoding="utf-8")
    target.write_text(
        text.replace("- **Status:** Accepted", "- **Status:** Vibes", 1),
        encoding="utf-8",
    )
    problems = check_structural_lint(adr_copy)
    assert any("invalid Status" in p and target.name in p for p in problems), problems


def test_superseded_pointer_catches_missing_target(adr_copy):
    target = _adr_files(adr_copy)[0]
    text = target.read_text(encoding="utf-8")
    # Point at an ADR that certainly doesn't exist, in both file and index so the
    # only complaint left is the dangling supersede pointer.
    target.write_text(
        text.replace("- **Status:** Accepted", "- **Status:** Superseded by ADR-4242", 1),
        encoding="utf-8",
    )
    problems = check_superseded_pointers(adr_copy)
    assert any("4242" in p for p in problems), problems
