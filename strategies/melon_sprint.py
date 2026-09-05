"""Melon is a race, not an allocation problem (issue #205).

Melon's whole-season town demand is **30 units** (#195) and it carries the
steepest glut curve in the table -- ``sq/3.60``, so 1 unit clears at 250, 100 at
150 and 200 at the $1 floor. The first units are where all the money is, and the
season only ever absorbs 30 of them. #178 read the win/loss split as an
allocation problem; this reads it as a race.

Every melon experiment before this one cut **quantity**: #175 capped it, #179
cut it conditionally, #161 sold early and kept planting. None moved **timing**.

What the replay actually showed
-------------------------------
`dense_farm` (live) and `field_rival` (the frozen benchmark) both open their
melon on **day 10, hour 12 -- the same turn**, in lockstep, splitting the top of
the curve. Day 10 is already the physical floor: melon's ``first_yield_day`` is
10, so a tile planted at dawn on day 0 cannot be harvested sooner. The race is
therefore not about the day at all. It is about the **hour**, and the thing
losing it is ``CARRY_LIMIT = 6``:

    a melon tile yields 5 units, so a worker that harvests one is UNDER the
    limit and goes back to watering and planting.

Measured on seed 100: the farmer harvested at hour 0 and carried those five
melon for eleven hours before banking them. Nothing can be sold out of a
worker's pocket.

The change under test
---------------------
Two rules on top of the champion, both pure timing. The crop line, the caps, the
herd and the pivot are `dense_farm`'s, untouched.

1. **Melon in hand goes to the shed now** -- ignoring the carry limit, which is
   sized for the shed's 100-item cap and for crops whose price does not collapse
   while you walk.
2. **No melon after the opening window, at any price.** The cap already binds on
   day 0, so this is a guarantee rather than a change -- until a melon dies to a
   weed mid-window, which frees a tile the champion would replant into a SECOND
   batch maturing on day 15, into a market it has already floored.

`field_rival` is untouched -- not threaded, not parameterised, not imported for
anything but its geometry. The whole sprint is a post-pass over the actions the
champion already chose, which is why this module can be read in one sitting and
why the benchmark cannot move underneath it.
"""

from __future__ import annotations

from strategies import dense_farm as df
from strategies import field_rival as fr
from strategies import hired_hands as hh

#: The crop the sprint is about. Melon alone: it is the only product whose
#: season demand (30) is smaller than one farm's single batch (~90 units).
SPRINT_CROP = "MELON"

#: Days the opening window stays open, declared in #205 before any measurement.
#: 1 means day 0 only -- so every melon tile matures on the same day and the
#: batch really is one batch.
MELON_WINDOW_DAYS = 1


def bank_first(action, pos, inv):
    """`action`, unless the worker is holding melon -- then bank it now.

    A harvest the worker is already standing on is kept: it costs no extra trip
    and rides back on the same walk, so refusing it would trade price for units
    the worker had already earned. Everything else yields to the walk.
    """
    if not (inv or {}).get(SPRINT_CROP, 0):
        return action
    if action and action[0] == "HARVEST":
        return action
    shed = fr.nearest_shed(pos)
    if [pos[0], pos[1]] == [shed[0], shed[1]]:
        return ["DROP"]
    return hh.step_toward(pos, shed)


def melon_window_closed(action, day):
    """`action`, unless it plants melon past the opening window -- then PASS.

    The hard stop the hypothesis needs. A melon planted on day 5 is a second
    batch landing on day 15, into a market this farm has already walked to the
    floor -- worth less than the seed and, worse, indistinguishable in the
    season total from the first batch that made the money.
    """
    if day >= MELON_WINDOW_DAYS and action and action[0] == "PLANT" \
            and len(action) > 1 and action[1] == SPRINT_CROP:
        return ["PASS"]
    return action


def sprint_action(action, pos, inv, day):
    """Both rules, gate first: a plant that is refused frees the same turn for
    the walk, and a worker holding melon should spend it walking."""
    return bank_first(melon_window_closed(action, day), pos, inv)


class MelonSprintStrategy(df.DenseFarmStrategy):
    """`dense_farm`, with melon run to market the turn it is picked."""

    name = "melon_sprint"
    benchmark = False

    def act(self, obs) -> dict:
        plan = super().act(obs)
        me = obs["farms"][obs["player"]]
        day = obs.get("day", 0)
        inventories = (obs.get("private") or {}).get("inventories") or []
        positions = [me["farmer"], *(me.get("hands") or [])]
        units = [plan["farmer"], *plan["hands"]]
        sprinted = [
            sprint_action(action, positions[i], inventories[i] if i < len(inventories) else {}, day)
            for i, action in enumerate(units)
        ]
        return {"farmer": sprinted[0], "hands": sprinted[1:], "market": plan["market"]}


STRATEGY = MelonSprintStrategy
