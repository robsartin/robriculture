"""Regenerate `GOLDEN_ACTIONS` for the champion-genome guard (#115).

Re-blessing used to be manual transcription out of a REPL. That was tolerable
at four scenarios; it is not at ten, and friction is how guards get deleted or
quietly hand-edited. This prints a ready-to-paste block computed by actually
running each scenario through the baked genome, so a golden can never be a
value somebody reasoned their way to.

    python -m scripts.regen_goldens            # print the block
    python -m scripts.regen_goldens --check    # exit 1 if any golden is stale

**When re-blessing is legitimate** (the distinction the guard's own docstring
draws, and the one that matters):

  - `strategies/champion_genome.json` actually changed via a promotion backed
    by a real `genome_bench` run. Regenerate freely.
  - The genome is UNCHANGED and a controller edit turned the guard red. That
    is the #100 trap. Re-benchmark the shipped genome first, record the number,
    and only then decide -- a drop means the controller change degraded the
    agent, and the fix is the controller, not this file.

This script deliberately does not write the test file. Pasting is a moment of
review, and the whole point of the guard is that the moment happens.
"""
from __future__ import annotations

import argparse
import pprint
import sys


def golden_block(scenarios, act) -> str:  # pragma: no cover - formatting only
    """Render `GOLDEN_ACTIONS` for `scenarios`, computed via `act(name)`."""
    fresh = {name: act(name) for name in scenarios}
    body = pprint.pformat(fresh, width=88, sort_dicts=False, indent=4)
    return f"GOLDEN_ACTIONS = {body}\n"


def stale_scenarios(scenarios, act, current) -> list:
    """Names whose recomputed actions differ from `current` -- pure, testable."""
    return [name for name in scenarios if act(name) != current.get(name)]


def main(argv=None):  # pragma: no cover - CLI
    ap = argparse.ArgumentParser(description="regenerate the champion-genome goldens (#115)")
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if any golden is stale, printing which; changes nothing")
    args = ap.parse_args(argv)

    from tests import test_champion_genome_regression as guard

    stale = stale_scenarios(guard._SCENARIOS, guard._act, guard.GOLDEN_ACTIONS)
    if args.check:
        if stale:
            print("stale goldens: " + ", ".join(stale), file=sys.stderr)
            return 1
        print(f"all {len(guard._SCENARIOS)} goldens current")
        return 0

    if stale:
        print(f"# {len(stale)} scenario(s) moved: {', '.join(stale)}", file=sys.stderr)
    else:
        print("# no scenario moved; block below matches the file", file=sys.stderr)
    print(golden_block(guard._SCENARIOS, guard._act))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
