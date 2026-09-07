"""#234: the per-farm census read off one side's public tiles and private shed.

Pure readings only -- the live drive that calls them belongs to the one-off
#234 measurement, not to this module. Every case here is a tile shape the sim
actually produces: ``"LOCKED"``, ``None``, a ``WEED``/``PLANT``/``PASTURE``/
``COOP`` dict, and a pasture with and without an animal standing on it.
"""

from __future__ import annotations

from harness import farm_census as fc


def _plant(crop, day=0):
    return {"kind": "PLANT", "crop": crop, "planted_day": day}


def _animal(animal, kind="PASTURE"):
    return {"kind": kind, "animal": animal, "placed_day": 3}


# --- crops -------------------------------------------------------------------

def test_planted_by_crop_should_count_each_crop_when_tiles_carry_plants():
    tiles = [[_plant("WHEAT"), _plant("WHEAT"), _plant("STRAWBERRY")]]
    assert fc.planted_by_crop(tiles) == {"WHEAT": 2, "STRAWBERRY": 1}


def test_planted_by_crop_should_ignore_locked_empty_and_non_plant_tiles():
    # "LOCKED" is a bare string, an empty unlocked tile is None, and a weed and
    # a pasture are dicts with no crop -- none of them is a planted tile.
    tiles = [["LOCKED", None, {"kind": "WEED"}, _animal("COW")]]
    assert fc.planted_by_crop(tiles) == {}


# --- herd --------------------------------------------------------------------

def test_animals_placed_should_count_animals_standing_on_their_structures():
    tiles = [[_animal("COW"), _animal("COW"), _animal("SHEEP"),
              _animal("GOOSE", "COOP")]]
    assert fc.animals_placed(tiles) == {"COW": 2, "SHEEP": 1, "GOOSE": 1}


def test_animals_placed_should_not_count_an_empty_structure_as_a_head():
    # A pasture built but not yet stocked is capacity, not livestock (#232).
    tiles = [[{"kind": "PASTURE"}, {"kind": "COOP"}]]
    assert fc.animals_placed(tiles) == {}


def test_structure_counts_should_split_each_structure_into_total_and_free():
    tiles = [[{"kind": "PASTURE"}, _animal("COW"), {"kind": "COOP"}]]
    assert fc.structure_counts(tiles) == {
        "PASTURE": {"total": 2, "free": 1},
        "COOP": {"total": 1, "free": 1},
    }


def test_structure_counts_should_report_zeros_when_nothing_is_built():
    # A farm with no pasture must read 0/0, not an absent key: "no pasture
    # built" and "not measured" are different findings (#232's question).
    assert fc.structure_counts([[None, "LOCKED"]]) == {
        "PASTURE": {"total": 0, "free": 0},
        "COOP": {"total": 0, "free": 0},
    }


def test_animals_held_should_count_bought_but_unplaced_head_in_the_shed():
    # An animal only becomes livestock when a herder walks it out; until then
    # it is dead capital sitting in the shed (#232).
    shed = {"COW": 4, "SHEEP": 1, "MILK": 12, "WHEAT": 3}
    assert fc.animals_held(shed) == {"COW": 4, "SHEEP": 1}


# --- the whole census --------------------------------------------------------

def test_census_should_pair_the_public_farm_with_the_private_shed():
    farm = {
        "money": 5000.0,
        "unlocked_quadrants": ["NW", "NE"],
        "hands": [[0, 0], [1, 1], [2, 2]],
        "tiles": [[_plant("WHEAT"), _animal("COW"), {"kind": "PASTURE"},
                   {"kind": "WEED"}, None, "LOCKED"]],
    }
    private = {"shed": {"COW": 2, "MILK": 9}}
    assert fc.census(farm, private) == {
        "money": 5000.0,
        "quadrants": ["NW", "NE"],
        "hands": 3,
        "planted": {"WHEAT": 1},
        "planted_tiles": 1,
        "animals_placed": {"COW": 1},
        "head_placed": 1,
        "animals_held": {"COW": 2},
        "head_held": 2,
        "structures": {"PASTURE": {"total": 2, "free": 1},
                       "COOP": {"total": 0, "free": 0}},
        "weeds": 1,
        "empty": 1,
    }


def test_census_should_survive_a_farm_with_no_private_state_at_all():
    # The opponent's shed is not in our observation; a census of the public
    # side must still read, with the held count honestly zero.
    farm = {"money": 3000.0, "unlocked_quadrants": ["NW"], "hands": [],
            "tiles": [[None]]}
    out = fc.census(farm, None)
    assert out["animals_held"] == {} and out["head_held"] == 0
    assert out["hands"] == 0 and out["empty"] == 1
