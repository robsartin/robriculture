"""The build step assembles a self-contained submission tarball.

We test `build` directly (no game run — that's the separate smoke test) so the
packaging logic is covered without the cost of a full episode.
"""

from __future__ import annotations

import tarfile

import pytest

from build.package import build


def test_build_creates_a_self_contained_tarball(tmp_path):
    out = tmp_path / "lean.tar.gz"
    build("lean", str(out))
    assert out.exists()
    with tarfile.open(out) as tar:
        names = tar.getnames()
    assert "main.py" in names
    assert any(n == "kaggisim" or n.startswith("kaggisim/") for n in names)
    assert any(n == "strategies" or n.startswith("strategies/") for n in names)


def test_build_rejects_unknown_strategy(tmp_path):
    with pytest.raises(SystemExit):
        build("not_a_strategy", str(tmp_path / "x.tar.gz"))
