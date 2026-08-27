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

**What this guard does and does not catch (mutation-tested, #115).**

Measured by perturbing a constant and checking whether any scenario moves.
Stated rather than assumed, because a guard that is trusted beyond its reach
is worse than one whose limits are written down:

    _LAND_RESERVE 800 -> 80        CAUGHT   (the #100 regression)
    TRAVEL_COST 0.05 -> 0          CAUGHT
    SELL_MARGIN_DAYS 1 -> 4        CAUGHT   (#115: plantable-window arithmetic)
    _MELON -> WHEAT                CAUGHT   (#115: crop choice)
    _ANIMAL_KINDS emptied          CAUGHT   (#115: animal dispatch)
    FERTILIZER made sellable again CAUGHT   (#120's fix)
    ANIMAL_JOB_SCALE x10           not caught -- and correctly so

The last one is a limit worth understanding rather than a hole to plug. The
shipped genome decodes `livestock_labor_share` to roughly 0.01, so an animal
job is worth about 0.02 against a crop job's 1.0. Multiplying the scale by ten
lifts it to 0.556 -- still losing every assignment it competes for, so no
action anywhere changes. A *behavioural* guard cannot fail on a change that
alters no behaviour, and should not pretend to. Detection begins where the
animal job's value crosses 1.0 (around x25 here), which is exactly the point
where the change starts to matter. See #121 for why that knob sits so low.

**Re-blessing — updating `GOLDEN_ACTIONS` below:**

Legitimate reasons to update it:
  - A new champion genome was promoted (`strategies/champion_genome.json`
    changed, its `meta.share`/`meta.issue` updated by a real
    `genome_bench` run per CLAUDE.md's experiment loop). Re-run the
    scenarios in `_SCENARIOS` against the new genome (e.g. paste this
    file's `_SCENARIOS` + `_act` into a REPL, or -- easier, and the
    supported route since #115 -- run
    `python -m scripts.regen_goldens` and paste the block it prints;
    `--check` reports which scenarios are stale without changing anything)
    and replace `GOLDEN_ACTIONS` with the fresh output. The genome changing is expected and welcome — this test must
    never fight a real promotion.

  - #120 (2026-08-24) fixed a three-part fertilizer defect: enumeration
    asked whether the fertilize job existed using a hardcoded EMPTY
    inventory, the buy-order guard inspected only `inventories[0]`, and
    `_sell_orders` liquidated the shed's supply before any worker could
    reach it. FERTILIZER is now excluded from selling, so the two scenarios
    holding shed fertilizer (`mid_game_full_crew`, `scattered_second_quadrant`)
    no longer emit a `SELL FERTILIZER` order. That is the ONLY difference —
    farmer and hand actions are byte-identical in both. Re-benchmarked
    BEFORE re-blessing, per the rule below: share 0.5242 / win-rate 0.8
    against 0.5222 / 0.8 before the fix. Instrumented over 719 turns, the
    round trip went from 25 bought / 25 sold / 1 applied to 3 / 0 / 3.

  - #127 (2026-08-27) promoted a genome that beats every anchor (share
    0.7018, win-rate 1.0). Six goldens moved, which is expected when the
    genome changes. The `land_reserve_below` / `land_reserve_above` bracket
    was RE-CALIBRATED rather than loosened: the new genome's decoded reserve
    threshold moved from $23,846 to **$11,258**, so the old $23,000/$24,700
    pair sat entirely above it and both sides bought land, bracketing nothing.
    Moving those two `money` inputs is legitimate precisely because the
    scenario's stated purpose is to straddle the threshold -- freezing the old
    values would keep the fixture and lose what it tests. Verified afterwards
    that re-blessing did not hollow the guard out: #115's mutation suite still
    catches all six probes, plus `_CROP_LADDER -> melon only`.

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

  - #71 reinterpreted two knobs (`livestock_labor_share` -> animal-job
    weight, `fertilize_pref` -> fertilize-job weight) and replaced the
    worker-index plot mapping with job assignment. The shipped weights are
    unchanged but are now read differently, so the actions moved by design.
    Re-benchmarked before re-blessing: share 0.3390 against a 0.3760
    baseline. This drop is expected, not a regression: these weights were
    evolved against the OLD knob meanings, so some drop is the honest
    consequence of reinterpreting them; it is well above the ~0.20
    collapse band that would indicate a wiring bug, and #71's own fresh
    evolution run is the real test of the new mechanism.

  - #71's own multi-seed evolution run (10 seeds x 25 generations)
    produced a new champion: seed 7's genome, promoted 2026-08-24 with a
    verified `genome_bench --games 4` share of 0.5222 (win_rate 0.8000),
    up from the prior champion's 0.3760/0.0. `GOLDEN_ACTIONS` below was
    regenerated by running `_SCENARIOS` through the new genome. As a
    side effect, the new genome's decoded land-purchase reserve moved
    from roughly $42-43k (the prior champion) to about $23,846 (binary
    search confirmed: no `BUY_LAND` at $23,846, `BUY_LAND` at $23,847).
    `land_reserve_below`/`land_reserve_above`'s `money` inputs in
    `_SCENARIOS` were re-pinned from $42,000/$43,500 to $23,000/$24,700
    to keep bracketing the *current* threshold with roughly the same
    margin as before. Changing those two `money` values is legitimate
    specifically because the scenario pair's stated purpose is to
    bracket wherever the threshold currently sits -- freezing the old
    dollar amounts would have preserved the letter of the fixture while
    destroying what it tests (both sides would silently buy land and
    the pair would stop bracketing anything). Both boundary assertions
    (`BUY_LAND` absent below, present above) are intact and re-verified
    against the new genome.
"""
from __future__ import annotations

from strategies import neuropilot as np


def _obs(day=0, hour=0, money=3000, farmer=(4, 4), hands=(), tiles=None,
         shed=None, unlocked=("NW",), prices=None, opp_money=3000, seeds=None,
         inventories=None):
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
                    "inventories": inventories or [{} for _ in range(1 + len(hands))]},
    }


def _mid_game_board():
    board = [[None] * 10 for _ in range(10)]
    board[4][4] = {"kind": "PLANT", "crop": "MELON", "planted_day": 30,
                    "yield_units": 5, "watered_today": True}
    board[4][3] = {"kind": "WEED"}
    board[0][5] = {"animal": "COW", "fed_today": False}
    return board


#: The cow tiles, so scenarios can place workers directly ON them. A worker
#: *walking toward* an animal tile emits the same step whether it was
#: dispatched through `_animal_job_action` or mis-routed down the crop path,
#: so an approach-only scenario cannot discriminate -- mutation testing caught
#: exactly that and the scenario was rebuilt to stand workers on the tiles.
_COW_TILES = [pos for pos, kind in np.ANIMAL_TILES if kind == "COW"]


def _all_idle_crop_board():
    """Every non-animal tile in NW *and* NE a watered live plant -- i.e. no
    crop work left anywhere the crew can reach (#115).

    Crop jobs are only enumerated for tiles that want something done, so this
    leaves the crew nothing to farm. That matters because an animal job is
    worth roughly 0.02 to the shipped genome against a crop job's 1.0, so it
    only ever wins an assignment once no crop job remains -- and unlocking NE
    to own the cow tiles otherwise hands the crew 16 fresh, empty, plantable
    NE tiles, which outrank the herd every time. Idling those too is what
    makes animal dispatch reachable at all.
    """
    board = [[None] * 10 for _ in range(10)]
    animal_positions = {pos for pos, _ in np.ANIMAL_TILES}
    for y in range(5):
        for x in range(10):
            if (x, y) not in animal_positions:
                board[y][x] = {"kind": "PLANT", "crop": "MELON",
                               "planted_day": 1, "watered_today": True}
    return board


def _one_unfertilized_plant_board():
    """A single live, unfertilized plant on the shed tile (#115/#120).

    The fertilize path was unreachable for the whole of #71 and no scenario
    here could see it: four of the five never land on a duty day, and the one
    that does has an empty board with nothing to fertilize.
    """
    board = [[None] * 10 for _ in range(10)]
    x, y = 4, 4
    board[y][x] = {"kind": "PLANT", "crop": "MELON", "planted_day": 1,
                   "watered_today": True}
    return board


def _scattered_board():
    """Work spread across NW *and* NE, none of it on `SHED_TILE` (4, 4):
    a harvest-ready melon and a hungry cow (both #71 job kinds) plus a weed,
    with every other tile still bare and plantable (mid-season)."""
    board = [[None] * 10 for _ in range(10)]
    board[2][1] = {"kind": "PLANT", "crop": "MELON", "planted_day": 3,
                    "yield_units": 6, "watered_today": True}
    board[1][8] = {"kind": "WEED"}
    board[0][7] = {"animal": "COW", "fed_today": False}
    return board


#: Fixed synthetic observations covering the controller's main branches:
#: an untouched turn-0 board (hire + first seed buy), a mid-game board with
#: a harvestable plant, a weed, a hungry animal, fertilizer in the shed and
#: a full 5-worker crew (fertilize/sell/animal-buy/movement), a pinned pair
#: either side of the current land-purchase reserve threshold, and a
#: mid-season crew scattered across NW *and* NE (#71 review: two of the
#: other four scenarios -- `land_reserve_below` and `land_reserve_above` --
#: put every worker on `SHED_TILE`, where the new job-assignment mechanism
#: happens to reproduce the old worker-index -> plot mapping exactly; this
#: one and `mid_game_full_crew` are the only two that can actually detect a
#: future rewrite of that mechanism).
_SCENARIOS = {
    "early_game": _obs(day=0, hour=0, money=3000, unlocked=("NW",)),
    "mid_game_full_crew": _obs(
        day=50, hour=3, money=15000, farmer=(4, 4),
        hands=[(0, 0), (1, 1), (2, 2), (3, 3)],
        tiles=_mid_game_board(), shed={"MELON": 10, "WHEAT": 5, "FERTILIZER": 2},
        unlocked=("NW", "NE"), seeds={"MELON": 3},
    ),
    "land_reserve_below": _obs(
        day=10, hour=6, money=10500, unlocked=("NW",),
        hands=[(4, 4)] * 5, shed={"MELON": 20, "WHEAT": 10},
    ),
    "land_reserve_above": _obs(
        day=10, hour=6, money=12000, unlocked=("NW",),
        hands=[(4, 4)] * 5, shed={"MELON": 20, "WHEAT": 10},
    ),
    # --- #115: the production loop the guard could not see -------------------
    #
    # Before these, NO scenario placed a worker on an empty plantable tile, so
    # the PLANT branch of `_plot_action` and the melon-vs-wheat decision in
    # `_crop_for` were never exercised -- the thing the agent spends most of
    # its turns doing. The fertilize path was unreachable in all five (four
    # never land on a duty day; the one that does has an empty board), and
    # mutation testing during #71's final review showed animal pricing and
    # dispatch were invisible too: `ANIMAL_JOB_SCALE` raised 10x and
    # `_ANIMAL_KINDS` emptied both went undetected.
    "plant_melon_window": _obs(
        day=18, hour=4, money=8000, hands=[(3, 4)], unlocked=("NW",),
        seeds={"MELON": 5, "WHEAT": 5},
    ),
    # The pair above/below the melon plantable window (melon 0-18, wheat 0-26),
    # working the same way the land-reserve pair does: one day apart, either
    # side of the boundary, so a change to the window arithmetic or to the
    # crop-choice fallback cannot pass unnoticed.
    "plant_wheat_after_melon_window": _obs(
        day=19, hour=4, money=8000, hands=[(3, 4)], unlocked=("NW",),
        seeds={"MELON": 5, "WHEAT": 5},
    ),
    # A worker already carrying a unit, standing on an unfertilized live plant,
    # on a duty day. This is the only scenario that reaches `acts.fertilize()`
    # -- a line that was uncovered for the whole of #71 and #120.
    "fertilize_held_unit": _obs(
        day=0, hour=4, money=6000, tiles=_one_unfertilized_plant_board(),
        unlocked=("NW",), shed={}, inventories=[{"FERTILIZER": 1}],
    ),
    # Every NW tile idle, so no crop job exists and the crew must fall through
    # to animal work despite an animal job being worth ~0.02 against a crop
    # job's 1.0. Without this, nothing pins animal enumeration or dispatch.
    "animal_work_when_crops_idle": _obs(
        day=8, hour=4, money=9000, tiles=_all_idle_crop_board(),
        farmer=_COW_TILES[0], hands=_COW_TILES[1:5],
        unlocked=("NW", "NE"), shed={},
    ),
    "scattered_second_quadrant": _obs(
        day=15, hour=4, money=6000, farmer=(4, 4),
        hands=[(1, 2), (8, 1), (3, 8), (6, 3)],
        tiles=_scattered_board(), shed={"MELON": 8, "WHEAT": 4, "FERTILIZER": 1},
        unlocked=("NW", "NE"), seeds={"MELON": 2, "WHEAT": 2},
    ),
}

#: Recorded actions of `strategies/champion_genome.json` on `_SCENARIOS`,
#: captured directly from `NeuroPilotStrategy(genome=<baked genome>).act`.
#: See the module docstring for when/how to regenerate this.
GOLDEN_ACTIONS = {   'early_game': {   'farmer': ['PASS'],
                      'hands': [],
                      'market': [   ['HIRE'],
                                    ['HIRE'],
                                    ['HIRE'],
                                    ['HIRE'],
                                    ['HIRE'],
                                    ['HIRE'],
                                    ['HIRE'],
                                    ['HIRE'],
                                    ['HIRE'],
                                    ['BUY_SEED', 'STRAWBERRY', 1]]},
    'mid_game_full_crew': {   'farmer': ['PICKUP', 'FERTILIZER', 1],
                              'hands': [['EAST'], ['EAST'], ['EAST'], ['EAST']],
                              'market': [['SELL', 'MELON', 10], ['SELL', 'WHEAT', 5]]},
    'land_reserve_below': {'farmer': ['PASS'],
                        'hands': [['WEST'], ['NORTH'], ['WEST'], ['WEST'], ['NORTH']],
                        'market': [['SELL', 'MELON', 20],
                                   ['SELL', 'WHEAT', 10],
                                   ['BUY_SEED', 'MELON', 6]]},
    'land_reserve_above': {   'farmer': ['PASS'],
                              'hands': [   ['WEST'],
                                           ['NORTH'],
                                           ['WEST'],
                                           ['WEST'],
                                           ['NORTH']],
                              'market': [   ['SELL', 'MELON', 20],
                                            ['SELL', 'WHEAT', 10],
                                            ['BUY_SEED', 'MELON', 6],
                                            ['BUY_LAND']]},
    'plant_melon_window': {   'farmer': ['PASS'],
                              'hands': [['PASS']],
                              'market': [['BUY_SEED', 'STRAWBERRY', 2]]},
    'plant_wheat_after_melon_window': {   'farmer': ['PLANT', 'WHEAT'],
                                          'hands': [['PLANT', 'WHEAT']],
                                          'market': []},
    'fertilize_held_unit': {'farmer': ['FERTILIZE'], 'hands': [], 'market': []},
    'animal_work_when_crops_idle': {   'farmer': ['BUILD_PASTURE'],
                                       'hands': [   ['BUILD_PASTURE'],
                                                    ['BUILD_PASTURE'],
                                                    ['BUILD_PASTURE'],
                                                    ['BUILD_PASTURE']],
                                       'market': [['BUY_PRODUCT', 'FERTILIZER', 1]]},
    'scattered_second_quadrant': {   'farmer': ['PLANT', 'MELON'],
                                     'hands': [   ['HARVEST'],
                                                  ['DIG'],
                                                  ['NORTH'],
                                                  ['PLANT', 'MELON']],
                                     'market': [   ['SELL', 'MELON', 8],
                                                   ['SELL', 'WHEAT', 4],
                                                   ['BUY_SEED', 'MELON', 1]]}}



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
    """Mid-game board with a full crew: harvest/sell/move-east/buy-land behaviour is unchanged."""
    assert _act("mid_game_full_crew") == GOLDEN_ACTIONS["mid_game_full_crew"]


def test_no_buy_land_when_money_just_below_reserve_threshold():
    """Just under the current land-purchase reserve threshold, the genome does not buy land.

    The #71 promotion (2026-08-24, share 0.5222) evolved a genome whose
    decoded land-purchase reserve moved to roughly $23,846 (down from the
    prior champion's ~$42-43k). `land_reserve_below`'s money value was
    re-calibrated from $42,000 to $23,000 to keep this scenario pinned just
    under the *new* threshold -- see the module docstring's re-blessing
    note for why re-pinning the bracket, not deleting the assertion, is the
    correct response here.
    """
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


def test_matches_golden_actions_when_scattered_second_quadrant():
    """Mid-season crew scattered across NW *and* NE (none on `SHED_TILE`):
    harvest/dig/plant/move/animal-approach behaviour is unchanged.

    Unlike `land_reserve_below`/`land_reserve_above` (every worker on
    `SHED_TILE`, where the #71 job-assignment mechanism happens to reproduce
    the old worker-index -> plot mapping exactly), and `early_game` (no
    hands at all), scattered workers plus a second owned quadrant is the
    shape of state that can actually tell the #71 mechanism apart from a
    future rewrite of it.
    """
    assert _act("scattered_second_quadrant") == GOLDEN_ACTIONS["scattered_second_quadrant"]


# --- #115: tests for the production loop the guard could not previously see ---

def test_matches_golden_actions_when_planting_inside_the_melon_window():
    """A worker on an empty, plantable tile at the last day melon can still
    mature (day 18 of a 30-day season).

    Pins the `PLANT` branch of `_plot_action` and the melon side of
    `_crop_for`'s decision -- neither of which any scenario reached before,
    despite planting being what the agent spends most of its turns doing.
    Pairs with the wheat test below, one day apart, exactly as the
    land-reserve pair brackets its threshold.
    """
    assert _act("plant_melon_window") == GOLDEN_ACTIONS["plant_melon_window"]


def test_matches_golden_actions_when_past_the_melon_window():
    """One day past melon's last plantable day, the same worker plants wheat.

    The other half of the bracket. A change to the plantable-window
    arithmetic, to `SELL_MARGIN_DAYS`, or to the crop-choice fallback moves
    one of these two and cannot pass unnoticed.
    """
    assert _act("plant_wheat_after_melon_window") == GOLDEN_ACTIONS["plant_wheat_after_melon_window"]


def test_matches_golden_actions_when_applying_a_held_fertilizer_unit():
    """A worker already carrying a unit, on an unfertilized live plant, on a
    duty day.

    This is the only scenario that reaches `acts.fertilize()`. That line was
    uncovered through all of #71 and #120 -- which is precisely how a
    three-part defect (enumeration asking with an empty inventory, the buy
    guard checking only `inventories[0]`, and `_sell_orders` liquidating the
    supply) survived a green suite while the agent bought 25 units, sold 25,
    and applied 1.
    """
    assert _act("fertilize_held_unit") == GOLDEN_ACTIONS["fertilize_held_unit"]


def test_matches_golden_actions_when_only_animal_work_remains():
    """Every NW tile idle, NE owned, animal tiles bare: the crew falls through
    to animal work.

    An animal job is worth roughly 0.02 to this genome against a crop job's
    1.0, so it only ever wins an assignment once no crop job is left. That
    makes this the only scenario that exercises animal enumeration and
    dispatch at all. Mutation testing during #71's final review found the
    guard blind here: `ANIMAL_JOB_SCALE` raised 10x and `_ANIMAL_KINDS`
    emptied both went undetected.
    """
    assert _act("animal_work_when_crops_idle") == GOLDEN_ACTIONS["animal_work_when_crops_idle"]
