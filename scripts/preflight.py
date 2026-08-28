"""Assert the machinery is sound before trusting a measurement or pushing.

Every check here exists because its absence produced a wrong result in this
repo, not because it seemed prudent:

* **Pinned deps.** A local venv drifted to `kaggle-environments` 1.32.7 against
  a 1.32.4 pin. Every claim-check compares `kaggisim/` to *whatever* is
  installed and says nothing about which version that is, so the drift was
  invisible: the checks failed locally, passed in CI, and "fixing" `economy.py`
  to satisfy one broke the other. A whole session of numbers was measured
  against the wrong simulator -- the champion read 0.5222 on the drifted sim
  and 0.3325 on the pinned one (#133).
* **Clean tree.** A rejected experiment was "discarded" with `git branch -D`,
  but the work had never been committed, so the branch was empty and the
  rejected code stayed in the working tree on `main`. The next measurement ran
  against it (#129).
* **Expected branch.** A 14-hour run was reading `strategies/` from the working
  tree when a branch switch changed the file underneath it (#127).
* **No stale runs.** Long experiments hold the tree and the CPU; starting a
  measurement beside one gives a contended, unreproducible number.

Usage::

    python -m scripts.preflight              # fast checks, seconds
    python -m scripts.preflight --branch 141-foo
    python -m scripts.preflight --tests      # + the full suite (~4.5 min)

Exit code is 0 only when everything asserted passed, so it composes:
`python -m scripts.preflight --tests && git push`.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQUIREMENTS = ROOT / "requirements.txt"

#: Long-running experiment entrypoints. A measurement started beside one of
#: these is contended and not reproducible.
EXPERIMENT_MARKERS = ("multi_seed", "harness.evolve", "spawn_main")


def parse_pins(text: str) -> dict:
    """`{package: version}` for every `==` pin in a requirements file.

    Comments and non-pinned requirements are ignored -- a `>=` is not a pin,
    and treating it as one would make the check assert something false.
    """
    pins = {}
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        m = re.match(r"^([A-Za-z0-9._-]+)\s*==\s*([\w.]+)$", line)
        if m:
            pins[m.group(1).lower()] = m.group(2)
    return pins


def pin_mismatches(pins: dict, installed: dict) -> list:
    """`(package, pinned, installed_or_None)` for every pin that is not met."""
    out = []
    for package, want in sorted(pins.items()):
        got = installed.get(package)
        if got != want:
            out.append((package, want, got))
    return out


def dirty_paths(status_porcelain: str) -> list:
    """Paths git reports as modified, staged or untracked."""
    return [line[3:].strip() for line in status_porcelain.splitlines() if line.strip()]


def stale_runs(ps_output: str, markers=EXPERIMENT_MARKERS) -> list:
    """Command lines that look like a long experiment still running."""
    hits = []
    for line in ps_output.splitlines():
        if any(m in line for m in markers) and "preflight" not in line:
            hits.append(line.strip()[:110])
    return hits


def _installed_versions(packages) -> dict:  # pragma: no cover - reads the env
    from importlib.metadata import PackageNotFoundError, version
    out = {}
    for name in packages:
        try:
            out[name] = version(name)
        except PackageNotFoundError:
            out[name] = None
    return out


def _run(cmd) -> str:  # pragma: no cover - shells out
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True).stdout


def main(argv=None):  # pragma: no cover - CLI
    ap = argparse.ArgumentParser(description="verify the machinery before trusting a result (#142)")
    ap.add_argument("--branch", help="fail unless this branch is checked out")
    ap.add_argument("--tests", action="store_true", help="also run the full suite (~4.5 min)")
    ap.add_argument("--allow-dirty", action="store_true",
                    help="permit uncommitted changes (use only mid-edit, never before a measurement)")
    args = ap.parse_args(argv)

    failures = []

    pins = parse_pins(REQUIREMENTS.read_text())
    bad = pin_mismatches(pins, _installed_versions(pins))
    if bad:
        for package, want, got in bad:
            print(f"FAIL  {package}: pinned {want}, installed {got or 'MISSING'}")
        print("      -> pip install -r requirements.txt")
        print("      -> do NOT edit kaggisim/ to match a drifted install (#133)")
        failures.append("pins")
    else:
        print(f"ok    {len(pins)} pinned dependencies match")

    dirty = dirty_paths(_run(["git", "status", "--porcelain"]))
    if dirty and not args.allow_dirty:
        print(f"FAIL  working tree has {len(dirty)} uncommitted path(s):")
        for path in dirty[:8]:
            print(f"        {path}")
        print("      -> a 'discarded' branch that was never committed leaves its "
              "code here, and the next measurement runs against it (#129)")
        failures.append("tree")
    else:
        print("ok    working tree clean" + (" (--allow-dirty)" if dirty else ""))

    branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"]).strip()
    if args.branch and branch != args.branch:
        print(f"FAIL  on branch {branch!r}, expected {args.branch!r}")
        failures.append("branch")
    else:
        note = "  <- experiments must not run here" if branch == "main" and args.branch is None else ""
        print(f"ok    branch {branch}{note}")

    running = stale_runs(_run(["ps", "-eo", "args"]))
    if running:
        print(f"FAIL  {len(running)} long experiment(s) still running:")
        for line in running[:4]:
            print(f"        {line}")
        print("      -> a measurement started beside one is contended and not reproducible")
        failures.append("stale")
    else:
        print("ok    no long experiment running")

    if args.tests:
        print("      running the full suite ...")
        proc = subprocess.run(["python", "-m", "pytest", "-q"], cwd=ROOT,
                              capture_output=True, text=True,
                              env={**__import__("os").environ, "ROBRICULTURE_STRICT": "1"})
        tail = [ln for ln in proc.stdout.splitlines() if ln.strip()][-1:]
        if proc.returncode != 0:
            print(f"FAIL  suite red: {tail[0] if tail else 'see output'}")
            failures.append("tests")
        else:
            print(f"ok    {tail[0] if tail else 'suite green'}")

    print()
    if failures:
        print(f"PREFLIGHT FAILED ({', '.join(failures)}) — do not trust a measurement or push from here")
        return 1
    print("PREFLIGHT OK")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
