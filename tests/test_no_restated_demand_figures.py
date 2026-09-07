"""Regression guard: no strategy docstring restates a season-demand figure (#231).

#228 found `strategies/rival_aware.py` and `strategies/cows_from_day_8.py` both
claiming milk has "570 season demand" -- a number transcribed from #146's
re-spec table (itself a reconstruction) that #228 measured to be wrong: the
real per-seed draw is shop-driven and ranges 66-354, never 570. The fix is to
state the mechanism and cite the measurement (#228) instead of a hard-coded
figure, per the no-restating rule in CLAUDE.md ("Single source for values").

This guard is cheap and specific: it does not know what the right number is,
only that no file under `strategies/` should hard-code a number right next to
the phrase "season demand" ever again -- the next drift would otherwise sit
silently until someone re-measures it.
"""

from __future__ import annotations

import re
from pathlib import Path

STRATEGIES_DIR = Path(__file__).resolve().parent.parent / "strategies"

# Matches a number directly preceding "season demand" (case-insensitive),
# e.g. "570 season demand" -- the exact shape of the restated figure #228 found.
_RESTATED_DEMAND_FIGURE = re.compile(r"\d[\d,]*\s+season demand", re.IGNORECASE)


def test_no_strategy_file_restates_a_season_demand_figure():
    offenders = []
    for path in sorted(STRATEGIES_DIR.glob("*.py")):
        text = path.read_text()
        if _RESTATED_DEMAND_FIGURE.search(text):
            offenders.append(path.name)
    assert not offenders, (
        f"season-demand figure hard-coded in {offenders}; state the mechanism "
        "and cite the measuring issue instead (see #228, #231)"
    )
