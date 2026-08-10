"""Unit tests for ranch_balanced — two-front income robustness (experiment #53).

`ranch_balanced` is `ranch_hands` with its single dominant melon crop crew
**re-partitioned into two roughly-equal income fronts**: a smaller melon crew and
a dedicated continuous-WHEAT crew, on top of the same cow + sheep livestock hand.
The hypothesis (issue #53): coins from two roughly-equal markets are structurally
harder for a single-market spoiler to exploit than a melon-dominant line.

These exercise the *pure decision helpers* — the expected-income balance model
that sizes the split, the crop-plot partition / assignment, the continuous-wheat
tile loop, and the act() shape — so the rebalance is validated without spinning up
a full 720-turn game. The full-game no-crash guard lives in test_no_crash.py; the
"is it actually better?" question is the promotion gate (recorded in the issue/PR).
"""

from __future__ import annotations

from strategies import ranch_balanced as rb
from strategies import ranch_hands as rh


# --- Income balance model: melon is <= ~55% of expected income (two fronts) ---

def test_melon_is_at_most_55_percent_of_expected_income():
    # The defining property of the experiment: melon no longer dominates income.
    assert rb.melon_income_share() <= 0.55


def test_two_fronts_are_roughly_equal_not_melon_abandoned():
    # "Rebalanced", not "melon dropped": the two fronts are of comparable size, so
    # melon's share sits in a balanced band rather than collapsing to a trickle.
    assert 0.45 <= rb.melon_income_share() <= 0.55


def test_rebalance_cuts_melon_share_well_below_the_single_front_line():
    # ranch_hands runs 9 melon plots + the same livestock; its melon share is the
    # single-front baseline. The rebalance must move melon materially below it.
    single_front = rb.melon_income(len(rh.MELON_PLOTS)) / (
        rb.melon_income(len(rh.MELON_PLOTS)) + rb.livestock_income()
    )
    assert single_front > 0.8  # the melon-dominant line we are de-risking
    assert rb.melon_income_share() < single_front - 0.2


def test_crop_plots_partition_the_ranch_crop_crew():
    # The two fronts exactly cover ranch_hands' 9 crop tiles, without overlap.
    assert len(rb.MELON_PLOTS) == 4
    assert len(rb.WHEAT_PLOTS) == 5
    assert set(rb.MELON_PLOTS).isdisjoint(rb.WHEAT_PLOTS)
    assert set(rb.MELON_PLOTS) | set(rb.WHEAT_PLOTS) == set(rh.MELON_PLOTS)


def test_crop_plots_never_collide_with_the_animal_cluster():
    crop = set(rb.MELON_PLOTS) | set(rb.WHEAT_PLOTS)
    assert rb.COW_TILE not in crop
    assert rb.SHEEP_TILE not in crop


# --- crop_plot_for: worker 1 is the livestock hand; others get a (tile, crop) ---

def test_farmer_keeps_a_melon_plot():
    tile, crop = rb.crop_plot_for(0)
    assert crop == "MELON"
    assert tile == rb.MELON_PLOTS[0]


def test_worker_one_is_the_livestock_hand():
    assert rb.crop_plot_for(1) is None


def test_second_worker_takes_the_second_crop_plot():
    assert rb.crop_plot_for(2) == rb.CROP_PLOTS[1]


def test_a_later_worker_lands_on_a_wheat_plot():
    # Workers past the melon block fall onto the wheat front.
    _, crop = rb.crop_plot_for(6)
    assert crop == "WHEAT"


def test_indices_past_the_crew_clamp_to_the_last_crop_plot():
    assert rb.crop_plot_for(20) == rb.CROP_PLOTS[-1]


# --- _wheat_decide: the continuous-wheat tile loop (plant / water / harvest) ---

def test_wheat_plot_plants_wheat_when_empty_early():
    assert rb._wheat_decide(None, day=0, hour=0) == ["PLANT", "WHEAT"]


def test_wheat_plot_waters_a_standing_unwatered_plant():
    tile = {"kind": "PLANT", "crop": "WHEAT", "planted_day": 0, "watered_today": False}
    assert rb._wheat_decide(tile, day=1, hour=0) == ["WATER"]


def test_wheat_plot_harvests_at_full_maturity():
    # Wheat matures at max_day 4; watered and holding yield => harvest.
    tile = {
        "kind": "PLANT", "crop": "WHEAT", "planted_day": 0,
        "watered_today": True, "yield_units": 4,
    }
    assert rb._wheat_decide(tile, day=4, hour=0) == ["HARVEST"]


def test_wheat_plot_digs_a_weed():
    assert rb._wheat_decide({"kind": "WEED"}, day=1, hour=0) == ["DIG"]


def test_wheat_plot_does_not_plant_once_it_cannot_mature():
    # day 27 + max_day 4 = 31 > final day 29: no wheat can fill out, so plant nothing.
    assert rb._wheat_decide(None, day=27, hour=0) == ["PASS"]


def test_wheat_plot_does_not_plant_on_the_last_hour_of_the_day():
    # A plant left unwatered on its birth night dies; never plant at the last turn.
    last = rb.TURNS_PER_DAY - 1
    assert rb._wheat_decide(None, day=0, hour=last) == ["PASS"]


# --- act(): end-to-end shape on a fresh board ---

def _empty_board():
    return [[None for _ in range(10)] for _ in range(10)]


def _fresh_obs(hour=0, day=0, money=3000, hands=None):
    board = _empty_board()
    n_inv = 1 + len(hands or [])
    return {
        "player": 0,
        "day": day,
        "hour": hour,
        "farms": [
            {"money": money, "tiles": board, "farmer": [4, 4], "hands": hands or []},
            {"money": money, "tiles": _empty_board(), "farmer": [4, 4], "hands": []},
        ],
        "market": {"inventory": {}, "prices": {}},
        "town": {"unlocked_shops": []},
        "private": {"shed": {}, "seeds": {}, "inventories": [{} for _ in range(n_inv)]},
    }


def test_act_hires_crew_and_returns_valid_shape_at_dawn():
    action = rb.RanchBalancedStrategy().act(_fresh_obs(hour=0))
    assert isinstance(action["farmer"], list) and action["farmer"]
    assert action["hands"] == []  # no hands exist yet at hour 0
    hire_orders = [o for o in action["market"] if o[0] == "HIRE"]
    assert len(hire_orders) >= 1
    assert len(action["market"]) <= 10


def test_act_emits_one_action_per_existing_hand():
    hands = [[5, 4], [4, 5], [5, 5]]
    action = rb.RanchBalancedStrategy().act(_fresh_obs(hour=3, hands=hands))
    assert len(action["hands"]) == len(hands)


def test_act_sells_melon_but_withholds_the_wheat_feed_buffer():
    obs = _fresh_obs(hour=5)
    obs["private"]["shed"] = {"MELON": 12, "WHEAT": 10}
    action = rb.RanchBalancedStrategy().act(obs)
    assert ["SELL", "MELON", 12] in action["market"]
    assert ["SELL", "WHEAT", 10 - rb.WHEAT_BUFFER] in action["market"]


def test_act_restocks_both_melon_and_wheat_seed_for_the_two_fronts():
    # A staffed crew on an empty board should buy seed for BOTH fronts so arriving
    # hands can plant either crop without stalling.
    hands = [[4, 4]] * 8  # a full crop crew present
    obs = _fresh_obs(hour=3, day=0, hands=hands)
    action = rb.RanchBalancedStrategy().act(obs)
    seeds = {o[1] for o in action["market"] if o[0] == "BUY_SEED"}
    assert "MELON" in seeds
    assert "WHEAT" in seeds
