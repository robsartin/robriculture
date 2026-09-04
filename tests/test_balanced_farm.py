"""Unit tests for the balanced-farm contender (issue #193, ADR-0007).

#187 established that livestock cannot be bolted onto the champion: the two
businesses compete for one crew, and our crop line is three times the field's
(62 planted tiles on 8 hands, against the field's 20 planted plus 8 animals on
11). So the question under test is not "should we keep animals" but whether the
whole farm *shape* is wrong.

`field_rival` is our own code, calibrated in #181 to the archetype measured from
63 real ladder replays. Over 8 seeds it beats the submitted champion **5 games
to 3** while earning slightly less per game — and the ladder scores wins and ties
only, margin discarded (ADR-0003). This contender puts that shape forward as a
candidate instead of an opponent.

It deliberately starts behaviourally identical to `field_rival`, because that is
the control the question needs: it isolates "is the shape better" from "can we
tune it". `field_rival` itself stays frozen — it is the only anchor calibrated to
the field that beats us (#181), and editing it would move the measuring stick
under the thing being measured.
"""

from __future__ import annotations

from strategies import balanced_farm as bf
from strategies import field_rival as fr


def test_it_is_a_contender_not_a_benchmark():
    # The whole point: `field_rival` can never be promoted or submitted
    # (ADR-0005). This one can be.
    assert bf.STRATEGY.benchmark is False
    assert bf.STRATEGY.name == "balanced_farm"


def test_the_benchmark_it_is_built_on_stays_a_benchmark():
    # Guard against the tempting shortcut of flipping the flag on field_rival,
    # which would silently remove the only field-calibrated anchor we have.
    assert fr.STRATEGY.benchmark is True
    assert fr.STRATEGY.name == "field_rival"


def test_it_is_registered_under_its_own_name():
    from strategies import REGISTRY, load
    assert "balanced_farm" in REGISTRY
    assert load("balanced_farm") is bf.STRATEGY


def test_it_plays_the_measured_field_shape_not_the_champions():
    # The shape is the hypothesis, so pin the numbers it inherits.
    assert bf.STRATEGY.TARGET_PLANTED_RANGE == (15, 30)
    assert sum(fr.CROP_CAP.values()) <= 32
    assert fr.animal_target(16) >= 8


def test_it_decides_identically_to_the_calibrated_shape():
    # Started as a behavioural copy on purpose: this run answers "is the field's
    # shape better than ours", not "can we out-tune the field". Any divergence
    # would confound the two.
    obs = _opening_observation()
    assert bf.STRATEGY().act(obs) == fr.STRATEGY().act(obs)


def _opening_observation():
    tiles = [[None] * 10 for _ in range(10)]
    for y in range(10):
        for x in range(10):
            if not (x < 5 and y < 5):
                tiles[y][x] = "LOCKED"
    return {
        "player": 0, "day": 0, "hour": 0,
        "farms": [{"money": 3000.0, "tiles": tiles, "hands": [],
                   "unlocked_quadrants": ["NW"], "farmer": [4, 4]},
                  {"money": 3000.0, "tiles": tiles, "hands": [],
                   "unlocked_quadrants": ["NW"], "farmer": [4, 4]}],
        "market": {"prices": {}, "inventory": {}},
        "private": {"shed": {}, "seeds": {}, "inventories": [{}]},
    }
