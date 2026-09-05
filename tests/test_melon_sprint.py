"""Unit tests for the melon sprint (issue #205, ADR-0007).

Melon's whole-season town demand is 30 units and its glut curve is the steepest
in the table (`sq/3.60`), so the first units sold are where all the money is.
Measured on a real `dense_farm` vs `field_rival` replay, both farms open their
melon at **day 10, hour 12** -- the same turn, in lockstep, splitting the top of
the curve between them.

The reason is not the harvest date. It is `CARRY_LIMIT = 6`: a melon tile yields
5 units, so a worker that harvests one is *under* the limit and goes back to
watering and planting. The farmer in that replay harvested at hour 0 and sat on
five melon until hour 11.

So the change under test is a pure timing rule -- hold melon, bank it now --
plus the hard stop the issue asks for: no melon after the opening window, at any
price. The crop line, the caps and the herd are `dense_farm`'s, unchanged.
"""

from __future__ import annotations

from strategies import dense_farm as df
from strategies import field_rival as fr
from strategies import melon_sprint as ms


SHED = fr.SHED_ACCESS["NW"]          # (4, 4) -- the farmer's spawn


# --- the rule: melon in hand goes to the shed now ---

def test_a_worker_holding_melon_walks_to_the_shed_instead_of_tending():
    # The whole hypothesis: being first. A worker that keeps tending while it
    # holds melon is a worker whose melon is not on the market.
    away = (1, 1)
    assert ms.bank_first(["WATER"], away, {"MELON": 5}) == fr.hh.step_toward(away, SHED)


def test_a_worker_holding_melon_at_the_shed_drops_it():
    assert ms.bank_first(["WATER"], SHED, {"MELON": 5}) == ["DROP"]


def test_a_worker_holding_melon_still_takes_a_harvest_it_is_standing_on():
    # A harvest under the worker's feet costs no trip, and the load rides back
    # on the same walk. Refusing it would trade price for units it already had.
    assert ms.bank_first(["HARVEST"], (1, 1), {"MELON": 5}) == ["HARVEST"]


def test_a_worker_carrying_no_melon_is_left_alone():
    # The sprint is a melon rule. Wheat, wool and fertilizer keep the champion's
    # full-load banking, which is what the shed's 100-item cap is sized for.
    assert ms.bank_first(["WATER"], (1, 1), {"WHEAT": 8}) == ["WATER"]
    assert ms.bank_first(["WATER"], (1, 1), {}) == ["WATER"]


# --- the hard stop: no melon after the opening window ---

def test_melon_is_refused_after_the_opening_window():
    # "No melon after the first batch, at any price." A melon planted on day 5
    # is a SECOND batch landing on day 15, into a market this farm has already
    # floored -- which is exactly what every previous melon experiment did.
    assert ms.melon_window_closed(["PLANT", "MELON"], 5) == ["PASS"]
    assert ms.melon_window_closed(["PLANT", "MELON"], ms.MELON_WINDOW_DAYS) == ["PASS"]


def test_melon_is_allowed_inside_the_opening_window():
    assert ms.melon_window_closed(["PLANT", "MELON"], 0) == ["PLANT", "MELON"]


def test_the_stop_touches_nothing_but_melon():
    assert ms.melon_window_closed(["PLANT", "STRAWBERRY"], 12) == ["PLANT", "STRAWBERRY"]
    assert ms.melon_window_closed(["PLANT", "WHEAT"], 20) == ["PLANT", "WHEAT"]
    assert ms.melon_window_closed(["HARVEST"], 20) == ["HARVEST"]


def test_the_window_is_the_one_batch_the_issue_declared():
    # Declared before measuring: day 0 only, so every melon tile matures on the
    # same day and the batch is one batch.
    assert ms.MELON_WINDOW_DAYS == 1
    assert ms.SPRINT_CROP == "MELON"


# --- the two rules compose in the order that keeps the harvest ---

def test_the_sprint_banks_and_gates_in_one_pass():
    away = (1, 1)
    assert ms.sprint_action(["WATER"], away, {"MELON": 5}, 10) == fr.hh.step_toward(away, SHED)
    assert ms.sprint_action(["PLANT", "MELON"], away, {}, 5) == ["PASS"]
    assert ms.sprint_action(["WATER"], away, {}, 5) == ["WATER"]


# --- the crop line is the champion's, unchanged ---

def test_it_inherits_the_champions_caps_and_crop_line():
    # The issue's change is a timing change ON TOP of the live agent, not a new
    # farm. If the caps move, this is #175 and #179 again.
    assert ms.STRATEGY.CAPS == df.STRATEGY.CAPS == {"MELON": 18, "STRAWBERRY": 22, "WHEAT": 8}
    assert issubclass(ms.MelonSprintStrategy, df.DenseFarmStrategy)


def test_it_is_a_contender_and_leaves_the_benchmark_alone():
    assert ms.STRATEGY.benchmark is False
    assert ms.STRATEGY.name == "melon_sprint"
    assert fr.STRATEGY.benchmark is True
    assert fr.CROP_CAP == {"MELON": 12, "STRAWBERRY": 15, "WHEAT": 5}
