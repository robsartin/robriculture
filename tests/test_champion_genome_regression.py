"""Behavioural regression guard for the baked champion genome (#110).

`strategies/champion_genome.json` ships fixed weights evolved against a
*specific* build of `neuropilot`'s controller (gate thresholds, purchase
curves, reserve constants...). Any change to that controller can silently
alter what the same shipped weights do — it has happened twice, once caught
by luck (#97) and once missed for weeks (#100). Nothing forced a
re-benchmark; remembering to run one is not a control.

This test freezes the *shipped* genome's actions on a handful of fixed,
synthetic single-turn observations, built by hand exactly like the ones in
`test_neuropilot.py`. It drives `strategies/champion_genome.json` straight
through `NeuroPilotStrategy.act` — no sim, no `genome_bench`, no 720-turn
game, no RNG, no wall-clock — so it runs in well under a second and is
byte-for-byte deterministic (ADR-0005). It is NOT a claim that the genome
plays *well*; only that it plays the *same way* it did the last time
someone looked.

One scenario (`land_reserve_below` / `land_reserve_above`) is deliberately
pinned either side of the exact money threshold at which the shipped
genome's decoded `livestock_pace` currently triggers a `BUY_LAND` order
under `_land_order`'s reserve formula (see `strategies/neuropilot.py`).
That threshold is a function of the controller's `_LAND_RESERVE` constant
(and whatever gate/curve replaces it later) — this is the exact shape of
change that caused #100, so the boundary scenario exists specifically to
catch it.

**Re-blessing — updating `GOLDEN_ACTIONS` below:**

Legitimate reasons to update it:
  - A new champion genome was promoted (`strategies/champion_genome.json`
    changed, its `meta.share`/`meta.issue` updated by a real
    `genome_bench` run per CLAUDE.md's experiment loop). Re-run the
    scenarios in `_SCENARIOS` against the new genome (e.g. paste this
    file's `_SCENARIOS` + `_ACT` into a REPL, or add a throwaway
    `print(_ACT(name))` loop) and replace `GOLDEN_ACTIONS` with the fresh
    output. The genome changing is expected and welcome — this test must
    never fight a real promotion.

NOT legitimate — this is the failure mode #100 describes, stop and read
`strategies/champion_genome.json`'s `meta.share`/`meta.win_rate` first:
  - The genome is unchanged (`strategies/champion_genome.json` untouched)
    but a controller edit (a gate, a curve, a reserve constant) turned this
    suite red. Before touching `GOLDEN_ACTIONS`, re-benchmark the baked
    genome under the new code:
    `python -m harness.genome_bench --genome strategies/champion_genome.json --games 4`
    and compare its `share` against the recorded `meta.share`. If it
    dropped, the controller change degraded the shipped agent — fix the
    controller (or re-bake a genome that recovers the share) rather than
    editing this file to make it green again.
"""
from __future__ import annotations

from strategies import neuropilot as np


def _obs(day=0, hour=0, money=3000, farmer=(4, 4), hands=(), tiles=None,
         shed=None, unlocked=("NW",), prices=None, opp_money=3000, seeds=None):
    """A minimal, fully-synthetic single-turn observation (mirrors the
    `_obs` helper in `test_neuropilot.py`)."""
    board = tiles or [[None] * 10 for _ in range(10)]
    hands = list(hands)
    return {
        "player": 0, "day": day, "hour": hour,
        "farms": [
            {"money": money, "tiles": board, "farmer": list(farmer),
             "hands": [list(h) for h in hands], "unlocked_quadrants": list(unlocked)},
            {"money": opp_money, "tiles": [[None] * 10 for _ in range(10)],
             "farmer": [4, 4], "hands": []},
        ],
        "market": {"inventory": {}, "prices": prices or {}},
        "town": {"unlocked_shops": []},
        "private": {"shed": shed or {}, "seeds": seeds or {},
                    "inventories": [{} for _ in range(1 + len(hands))]},
    }


def _mid_game_board():
    board = [[None] * 10 for _ in range(10)]
    board[4][4] = {"kind": "PLANT", "crop": "MELON", "planted_day": 30,
                    "yield_units": 5, "watered_today": True}
    board[4][3] = {"kind": "WEED"}
    board[0][5] = {"animal": "COW", "fed_today": False}
    return board


#: Fixed synthetic observations covering the controller's main branches:
#: an untouched turn-0 board (hire + first seed buy), a mid-game board with
#: a harvestable plant, a weed, a hungry animal, fertilizer in the shed and
#: a full 5-worker crew (fertilize/sell/animal-buy/movement), and a pinned
#: pair either side of the current land-purchase reserve threshold.
_SCENARIOS = {
    "early_game": _obs(day=0, hour=0, money=3000, unlocked=("NW",)),
    "mid_game_full_crew": _obs(
        day=50, hour=3, money=15000, farmer=(4, 4),
        hands=[(0, 0), (1, 1), (2, 2), (3, 3)],
        tiles=_mid_game_board(), shed={"MELON": 10, "WHEAT": 5, "FERTILIZER": 2},
        unlocked=("NW", "NE"), seeds={"MELON": 3},
    ),
    "land_reserve_below": _obs(
        day=10, hour=6, money=42000, unlocked=("NW",),
        hands=[(4, 4)] * 5, shed={"MELON": 20, "WHEAT": 10},
    ),
    "land_reserve_above": _obs(
        day=10, hour=6, money=43500, unlocked=("NW",),
        hands=[(4, 4)] * 5, shed={"MELON": 20, "WHEAT": 10},
    ),
}

#: Recorded actions of `strategies/champion_genome.json` on `_SCENARIOS`,
#: captured directly from `NeuroPilotStrategy(genome=<baked genome>).act`.
#: See the module docstring for when/how to regenerate this.
GOLDEN_ACTIONS = {
    "early_game": {
        "farmer": ["PASS"], "hands": [],
        "market": [["HIRE"]] * 9 + [["BUY_SEED", "MELON", 1]],
    },
    "mid_game_full_crew": {
        "farmer": ["PICKUP", "FERTILIZER", 1],
        "hands": [["EAST"], ["EAST"], ["SOUTH"], ["PASS"]],
        "market": [
            ["SELL", "FERTILIZER", 2], ["SELL", "MELON", 10], ["SELL", "WHEAT", 5],
            ["BUY_ANIMAL", "COW", 1], ["BUY_ANIMAL", "COW", 1], ["BUY_ANIMAL", "COW", 1],
            ["BUY_ANIMAL", "COW", 1], ["BUY_ANIMAL", "COW", 1], ["BUY_ANIMAL", "COW", 1],
            ["BUY_ANIMAL", "COW", 1],
        ],
    },
    "land_reserve_below": {
        "farmer": ["PASS"],
        "hands": [["WEST"], ["NORTH"], ["WEST"], ["WEST"], ["NORTH"]],
        "market": [["SELL", "MELON", 20], ["SELL", "WHEAT", 10], ["BUY_SEED", "MELON", 6]],
    },
    "land_reserve_above": {
        "farmer": ["PASS"],
        "hands": [["WEST"], ["NORTH"], ["WEST"], ["WEST"], ["NORTH"]],
        "market": [["SELL", "MELON", 20], ["SELL", "WHEAT", 10],
                   ["BUY_SEED", "MELON", 6], ["BUY_LAND"]],
    },
}


def _act(scenario_name):
    """Run the shipped `strategies/champion_genome.json` genome on one scenario."""
    genome = np.load_champion_genome(np._LOCAL_GENOME)
    assert genome is not None, "strategies/champion_genome.json failed to load"
    strategy = np.NeuroPilotStrategy(genome=genome)
    return strategy.act(_SCENARIOS[scenario_name])


def test_matches_golden_actions_when_early_game():
    """Turn-0 board: the baked genome's hire/first-seed-buy behaviour is unchanged."""
    assert _act("early_game") == GOLDEN_ACTIONS["early_game"]


def test_matches_golden_actions_when_mid_game_full_crew():
    """Mid-game board with a full crew: fertilize/sell/buy-animal/move behaviour is unchanged."""
    assert _act("mid_game_full_crew") == GOLDEN_ACTIONS["mid_game_full_crew"]


def test_no_buy_land_when_money_just_below_reserve_threshold():
    """Just under the current land-purchase reserve threshold, the genome does not buy land."""
    result = _act("land_reserve_below")
    assert result == GOLDEN_ACTIONS["land_reserve_below"]
    assert ["BUY_LAND"] not in result["market"]


def test_buys_land_when_money_at_reserve_threshold():
    """At/above the current land-purchase reserve threshold, the genome buys land.

    This scenario is the one #100 would have caught: it and
    `test_no_buy_land_when_money_just_below_reserve_threshold` are pinned
    either side of `_land_order`'s current reserve threshold for the shipped
    genome. Loosening or recalibrating that reserve (as #97 and #100 each
    did) shifts the threshold and flips one of these two assertions.
    """
    result = _act("land_reserve_above")
    assert result == GOLDEN_ACTIONS["land_reserve_above"]
    assert ["BUY_LAND"] in result["market"]
