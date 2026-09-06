"""The #225 experiment's declared constants and its one new pure helper.

The counting and verdict logic is `harness.rival_bench`'s, imported rather
than copied -- this file pins only what #225 adds: the declared constants and
the milk/wool realisation table (recorded, not gated).
"""

from __future__ import annotations

from harness import clock_bench as cb
from harness import rival_bench as rb


def test_the_declared_constants():
    assert cb.CONTENDER == "cows_from_day_8" and cb.CHAMPION == "rival_aware"
    assert cb.REFERENCE == "dense_farm"
    assert cb.SEEDS == tuple(range(600, 616))
    assert cb.CHAMPION_BAR == 0.60 and cb.ANCHOR_BAR == 0.90
    assert cb.CONTROL_SEED == 600


def test_the_seeds_are_fresh_against_every_range_already_spent():
    # 100-115, 200-215, 300-331, 400-415 and 500-515 are all used by earlier
    # experiments; a criterion re-run on a spent range is a re-used measurement.
    spent = set(range(100, 116)) | set(range(200, 216)) | set(range(300, 332)) \
        | set(range(400, 416)) | set(range(500, 516))
    assert not spent & set(cb.SEEDS)


def test_the_verdict_logic_is_rival_benchs_not_a_copy():
    assert cb.criterion is rb.criterion
    assert cb.format_rows is rb.format_rows
    assert cb.animal_buys is rb.animal_buys and cb.mechanism_fired is rb.mechanism_fired


def _analysis(milk_units=40, milk_pct=1.74):
    return {"items": {
        "MILK": {"units": milk_units, "revenue": 1, "mean_price": 160 * milk_pct,
                 "base": 160, "pct_of_base": milk_pct, "late_pct_of_base": 1.5},
        "WOOL": {"units": 12, "revenue": 1, "mean_price": 240.0, "base": 200,
                 "pct_of_base": 1.2, "late_pct_of_base": 0.9},
    }}


def test_realisation_rows_reads_one_row_per_item():
    rows = cb.realisation_rows(_analysis(), "cows_from_day_8", 600)
    assert [r["item"] for r in rows] == ["MILK", "WOOL"]
    milk = rows[0]
    assert milk["agent"] == "cows_from_day_8" and milk["seed"] == 600
    assert milk["units"] == 40 and milk["base"] == 160
    assert milk["pct_of_base"] == 1.74 and milk["late_pct_of_base"] == 1.5


def test_realisation_rows_reports_an_unsold_item_as_zero_rather_than_missing():
    # A season that sold no wool must still produce a WOOL row -- an absent row
    # would read as "not measured" where the honest reading is "sold none".
    rows = cb.realisation_rows({"items": {}}, "rival_aware", 601)
    assert [r["item"] for r in rows] == ["MILK", "WOOL"]
    assert all(r["units"] == 0 and r["pct_of_base"] == 0.0 for r in rows)


def test_format_realisation_has_a_header_and_one_line_per_row():
    rows = cb.realisation_rows(_analysis(), "cows_from_day_8", 600)
    text = cb.format_realisation(rows)
    lines = [ln for ln in text.splitlines() if ln.strip()]
    assert len(lines) == 3
    assert "MILK" in lines[1] and "174.0%" in lines[1] and "40" in lines[1]
    assert "WOOL" in lines[2]
