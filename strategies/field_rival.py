"""Calibrated sparring opponent — the ladder field, not a candidate (issue #181).

Measured, not guessed. Profiled from 63 downloaded ladder replays, the 43
opponents that actually beat the submitted champion converge on one shape
(medians, sampled mid-day):

    day   melon  straw  wheat  planted  animals  hands  quads
      4      11      0      3       18        3      6      1
      8      12      3      0       20        4      7      1
     12       3     13      1       26        8      9      2
     16       2     15      4       27       10     10      3
     24       0     14      5       22       11     10      3   reward 66,640

The 20 opponents the champion beats never exceed 6 melon or 4 strawberry and
median 35,607 — the two populations separate cleanly on crop mix alone.

This strategy exists to make the benchmark able to express that shape. The five
`DEFAULT_ANCHORS` are swept 20/20 by the champion and **not one of them plants a
single strawberry**, so every paired experiment recorded in this repository was
scored against a saturated instrument (#181).

It is flagged ``benchmark = True``: never packaged by ``scripts/submit.py``
(ADR-0005) and never eligible for promotion (``harness.promotion.top_contender``).
"""

from __future__ import annotations

from kaggisim.strategy import Strategy
from strategies import hired_hands as hh

CROPS = hh.CROPS
SEASON_DAYS = hh.SEASON_DAYS

#: Day the measured field swings off melon and into strawberry. In the replays
#: melon is still 12 tiles at day 8 and down to 3 by day 12, while strawberry
#: goes 3 -> 13 over the same span, so the crossover sits at day 10.
PIVOT_DAY = 10


def crop_for_day(day: int, season_days: int = SEASON_DAYS):
    """The crop this farm plants on `day`, or ``None`` past the horizon.

    Melon before the pivot, strawberry after — the measured field's whole crop
    story. The horizon gate is the champion's own (`hired_hands.plantable`), so a
    seed is never spent on a plant that cannot reach first yield in time.
    """
    crop = "MELON" if day < PIVOT_DAY else "STRAWBERRY"
    return crop if hh.plantable(crop, day, season_days) else None


#: Crew cap. The measured field tops out at 10 hands (11 workers with the
#: farmer); the escalating fib wage makes a wider crew self-defeating (#33).
MAX_HANDS = 10

#: The measured ramps, as ``(from_day, target)`` breakpoints read straight off
#: the replay medians in the module docstring. A step table rather than a curve
#: fit: the numbers are a measurement, and a reader can check them against the
#: table above line by line.
HAND_RAMP = ((0, 6), (8, 7), (12, 9), (16, 10))
LAND_RAMP = ((0, 1), (12, 2), (16, 3))
ANIMAL_RAMP = ((0, 1), (4, 3), (8, 4), (12, 8), (16, 10), (24, 11))


def _ramp(table, day: int) -> int:
    """Value of a step table on `day` — the last breakpoint at or before it."""
    value = table[0][1]
    for from_day, target in table:
        if day >= from_day:
            value = target
    return value


def hire_target(day: int) -> int:
    """Hands to have working on `day` (6 -> 10 over the season)."""
    return _ramp(HAND_RAMP, day)


def land_target(day: int) -> int:
    """Quadrants to own on `day` (NW only, then NE by day 12, SW by day 16)."""
    return _ramp(LAND_RAMP, day)


def animal_target(day: int) -> int:
    """Livestock head to be running on `day` (1 -> 11 over the season)."""
    return _ramp(ANIMAL_RAMP, day)


#: Board is 10x10 split into four 5x5 quadrants; NW starts unlocked and the rest
#: are bought in the sim's fixed LAND_ORDER (NE, SW, SE). We never reach SE.
BOARD = 10
OWNED_QUADRANTS = ("NW", "NE", "SW")

#: The shed sits at the board centre and each quadrant touches it at exactly one
#: tile. NW's is (4, 4) -- the farmer's spawn and the only shed access we have
#: until day 12, which is why the early layout is packed tight around it.
SHED_ACCESS = {"NW": (4, 4), "NE": (5, 4), "SW": (4, 5), "SE": (5, 5)}

#: Two of the eleven workers run the livestock line; the rest tend crop clusters.
#: Indices 1 and 2 so the ramp's earliest hands are the herders -- the herd has
#: to be established before the crop area outgrows one quadrant.
LIVESTOCK_WORKERS = (1, 2)

#: Tiles per crop worker. Watering is only needed every other day (a plant dies
#: at ``consecutive_unwatered >= 2``), so three tiles fit comfortably inside one
#: worker's 24-turn day without the walk eating the schedule.
CLUSTER = 3


def quadrant_of(x: int, y: int) -> str:
    """The sim's own quadrant rule (`_quadrant_of`), mirrored for planning."""
    half = BOARD // 2
    return ("N" if y < half else "S") + ("W" if x < half else "E")


def _walk_cost(tile) -> int:
    """Manhattan steps from `tile` to its own quadrant's shed-access tile.

    Every trip a worker makes is to or from the shed, so this is the honest
    ordering key: it puts the tiles a worker can service quickly first.
    """
    x, y = tile
    sx, sy = SHED_ACCESS[quadrant_of(x, y)]
    return abs(x - sx) + abs(y - sy)


def _quadrant_tiles(quadrant: str):
    """Every tile of one quadrant, nearest-to-shed first."""
    tiles = [(x, y) for y in range(BOARD) for x in range(BOARD)
             if quadrant_of(x, y) == quadrant]
    return sorted(tiles, key=lambda t: (_walk_cost(t), t))


#: The five NW tiles closest to the shed become pasture: the livestock workers
#: round-trip to the shed for feed wheat every other day, so their walk is the
#: one that has to be short. Everything the herd needs before the day-12 land
#: buy (4 head) fits here; the rest of the block follows into NE.
PASTURE_TILES = tuple(_quadrant_tiles("NW")[1:6] + _quadrant_tiles("NE")[1:8])

#: Crop land is everything else we will ever own, nearest-to-shed first, NW
#: exhausted before NE and NE before SW -- which matches the measured field:
#: ~20 planted inside one quadrant by day 8, jumping to 26 when NE opens.
CROP_TILES = tuple(
    t for q in OWNED_QUADRANTS for t in _quadrant_tiles(q) if t not in PASTURE_TILES
)


def _crop_slot(worker: int):
    """Crop-cluster slot for a worker index, or ``None`` for the herders."""
    if worker in LIVESTOCK_WORKERS:
        return None
    return worker if worker < LIVESTOCK_WORKERS[0] else worker - len(LIVESTOCK_WORKERS)


def crop_cluster(worker: int):
    """The tiles worker `worker` is responsible for -- ``()`` for a herder."""
    slot = _crop_slot(worker)
    if slot is None:
        return ()
    return CROP_TILES[slot * CLUSTER:(slot + 1) * CLUSTER]


TURNS_PER_DAY = hh.TURNS_PER_DAY


def plot_action(tile, crop, day: int, hour: int):
    """The action for a worker standing on one of its crop tiles.

    Harvest before water before plant: a ready tile is money already earned, and
    an ongoing crop (strawberry) keeps offering HARVEST every time it regrows.
    Planting is refused on the final turn of the day -- a new plant carries
    ``consecutive_unwatered = 1`` and dies at 2, so it could never be watered.
    """
    if tile == "LOCKED":
        return ["PASS"]
    if isinstance(tile, dict) and tile.get("kind") == "WEED":
        return ["DIG"]
    if tile is None:
        if crop and hour < TURNS_PER_DAY - 1:
            return ["PLANT", crop]
        return ["PASS"]
    if hh._is_live_plant(tile):
        if hh.harvest_ready(tile, day):
            return ["HARVEST"]
        if not tile.get("watered_today", False):
            return ["WATER"]
    return ["PASS"]


def nearest_shed(pos):
    """The shed-access tile a worker at `pos` can reach fastest.

    All four are usable from day one: the sim resolves shed operations before
    its LOCKED guard and allows movement onto locked tiles, precisely so a hand
    spawned on a locked access tile is never stranded.
    """
    return min(SHED_ACCESS.values(),
               key=lambda t: (abs(t[0] - pos[0]) + abs(t[1] - pos[1]), t))


class FieldRivalStrategy(Strategy):
    name = "field_rival"
    benchmark = True

    def act(self, obs) -> dict:
        return {"farmer": ["PASS"], "hands": [], "market": []}


STRATEGY = FieldRivalStrategy
