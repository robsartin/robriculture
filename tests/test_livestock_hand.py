"""Unit tests for the livestock_hand experiment (issue #45, ADR-0007).

These exercise the *pure decision helpers* — the melon/worker remap that frees
one worker, and the two-animal (cow + sheep) tending state machine — so the
single technique under test (reallocate one worker from melon to a livestock
cluster) is validated without a full 720-turn game. The full-game no-crash guard
lives in test_no_crash.py (auto-included via the REGISTRY).

The regression pinned hardest here is the LOCKED shed-tile bug that sank the
first cut: three of the four shed-access corners sit on LOCKED tiles where every
tile op (PICKUP included) silently no-ops, so the livestock hand must draw wheat
only from the unlocked NW corner (4, 4) or it never feeds its animals.
"""

from __future__ import annotations

from strategies import livestock_hand as lh


# --- Crew remap: 9 melon tiles (weakest dropped) + one livestock worker ---

def test_melon_crew_dropped_to_nine_distinct_nw_tiles():
    assert len(lh.MELON_PLOTS) == 9
    assert len(set(lh.MELON_PLOTS)) == 9
    assert all(0 <= x < 5 and 0 <= y < 5 for x, y in lh.MELON_PLOTS)


def test_dropped_plot_is_the_champions_last_tile():
    from strategies import catch_hands as ch

    assert lh.MELON_PLOTS == ch.PLOTS[:-1]
    assert ch.PLOTS[-1] not in lh.MELON_PLOTS  # the weakest 10th tile is gone


def test_farmer_keeps_shed_plot_and_worker_one_is_livestock():
    # Worker 0 (farmer) keeps (4,4); worker 1 is the dedicated livestock hand.
    assert lh.melon_plot_for(0) == lh.MELON_PLOTS[0] == (4, 4)
    assert lh.melon_plot_for(1) is None


def test_remaining_workers_cover_the_other_eight_melon_tiles():
    covered = {lh.melon_plot_for(i) for i in range(2, 10)}
    assert covered == set(lh.MELON_PLOTS[1:])  # all 8 non-farmer melon tiles


def test_cluster_tiles_are_free_and_not_melon_plots():
    assert lh.COW_TILE not in lh.MELON_PLOTS
    assert lh.SHEEP_TILE not in lh.MELON_PLOTS
    assert lh.COW_TILE != lh.SHEEP_TILE


# --- The LOCKED shed-tile regression: only (4,4) is a valid pickup spot ---

def test_only_the_nw_corner_counts_as_at_shed():
    assert lh._at_shed((4, 4)) is True
    # The other three shed-access corners are on LOCKED tiles — pickups no-op
    # there, so treating them as "at shed" is the bug that starved the animals.
    for locked in [(5, 4), (4, 5), (5, 5)]:
        assert lh._at_shed(locked) is False


# --- animal_chore: the per-animal setup + maintenance state machine ---

def _board():
    return [[None for _ in range(10)] for _ in range(10)]


def test_chore_builds_pasture_when_standing_on_empty_cluster_tile():
    tiles = _board()
    assert lh.animal_chore("COW", lh.COW_TILE, tiles, {}, {}) == ["BUILD_PASTURE"]


def test_chore_walks_to_cluster_when_pasture_missing():
    tiles = _board()
    act = lh.animal_chore("COW", (4, 4), tiles, {}, {})
    assert act in (["WEST"], ["NORTH"])  # stepping toward (2,2)


def test_chore_picks_up_bought_animal_only_at_nw_corner():
    tiles = _board()
    x, y = lh.COW_TILE
    tiles[y][x] = {"kind": "PASTURE"}  # pasture built, animal waiting in shed
    shed = {"COW": 1}
    # Standing on a LOCKED shed corner: must walk to (4,4), not pick up there.
    assert lh.animal_chore("COW", (5, 4), tiles, {}, shed) != ["PICKUP", "COW", 1]
    # Standing on the real NW corner: pick it up.
    assert lh.animal_chore("COW", (4, 4), tiles, {}, shed) == ["PICKUP", "COW", 1]


def test_chore_places_held_animal_on_its_pasture():
    tiles = _board()
    x, y = lh.SHEEP_TILE
    tiles[y][x] = {"kind": "PASTURE"}
    assert lh.animal_chore("SHEEP", lh.SHEEP_TILE, tiles, {"SHEEP": 1}, {}) == [
        "PLACE",
        "SHEEP",
    ]


def _placed(**over):
    base = {
        "kind": "PASTURE",
        "animal": "COW",
        "yield_units": 0,
        "fed_today": False,
        "cared_today": False,
    }
    base.update(over)
    return base


def test_chore_harvests_a_yielding_animal_first():
    tiles = _board()
    x, y = lh.COW_TILE
    tiles[y][x] = _placed(yield_units=3)
    assert lh.animal_chore("COW", lh.COW_TILE, tiles, {}, {}) == ["HARVEST"]


def test_chore_feeds_when_holding_wheat():
    tiles = _board()
    x, y = lh.COW_TILE
    tiles[y][x] = _placed()
    assert lh.animal_chore("COW", lh.COW_TILE, tiles, {"WHEAT": 2}, {}) == ["FEED"]


def test_chore_fetches_wheat_from_nw_corner_when_unfed_and_dry():
    tiles = _board()
    x, y = lh.COW_TILE
    tiles[y][x] = _placed()
    shed = {"WHEAT": 4}
    # No wheat carried: at the cluster it must head back toward the shed (4,4).
    act = lh.animal_chore("COW", lh.COW_TILE, tiles, {}, shed)
    assert act in (["EAST"], ["SOUTH"])  # stepping toward (4,4)
    # At the NW corner it draws wheat (capped at the carry amount).
    assert lh.animal_chore("COW", (4, 4), tiles, {}, shed) == [
        "PICKUP",
        "WHEAT",
        lh.WHEAT_CARRY,
    ]


def test_chore_cares_only_when_fed_and_standing_on_the_animal():
    tiles = _board()
    x, y = lh.COW_TILE
    tiles[y][x] = _placed(fed_today=True)
    assert lh.animal_chore("COW", lh.COW_TILE, tiles, {}, {}) == ["CARE"]


def test_chore_returns_none_when_fully_tended():
    tiles = _board()
    x, y = lh.COW_TILE
    tiles[y][x] = _placed(fed_today=True, cared_today=True)
    assert lh.animal_chore("COW", lh.COW_TILE, tiles, {}, {}) is None


# --- livestock_action: cow first, then sheep; never None ---

def test_livestock_action_ignores_sheep_until_cow_line_is_live():
    tiles = _board()
    # want_sheep False: only the cow is pursued (pasture-building toward (2,2)).
    act = lh.livestock_action((4, 4), tiles, {}, {}, want_sheep=False)
    assert act in (["WEST"], ["NORTH"])


def test_livestock_action_proactively_tops_up_wheat_at_dawn():
    tiles = _board()
    cx, cy = lh.COW_TILE
    tiles[cy][cx] = _placed(fed_today=True, cared_today=True)  # cow needs nothing
    # Standing at the NW corner with a placed animal and no wheat -> grab feed
    # before walking out, so one cluster trip can both harvest and feed.
    assert lh.livestock_action((4, 4), tiles, {}, {"WHEAT": 4}, want_sheep=True) == [
        "PICKUP",
        "WHEAT",
        lh.WHEAT_CARRY,
    ]


def test_livestock_action_never_returns_none():
    tiles = _board()
    cx, cy = lh.COW_TILE
    sx, sy = lh.SHEEP_TILE
    tiles[cy][cx] = _placed(fed_today=True, cared_today=True)
    tiles[sy][sx] = _placed(animal="SHEEP", fed_today=True, cared_today=True)
    act = lh.livestock_action(lh.COW_TILE, tiles, {}, {}, want_sheep=True)
    assert isinstance(act, list) and act  # a concrete action (idle PASS toward cluster)


# --- act(): end-to-end shape and market ordering ---

def _fresh_obs(hour=0, day=0, money=3000, hands=None, shed=None, tiles=None):
    board = tiles or [[None for _ in range(10)] for _ in range(10)]
    n = 1 + len(hands or [])
    return {
        "player": 0,
        "day": day,
        "hour": hour,
        "farms": [
            {"money": money, "tiles": board, "farmer": [4, 4], "hands": hands or []},
            {"money": money, "tiles": _board(), "farmer": [4, 4], "hands": []},
        ],
        "market": {"inventory": {}, "prices": {}},
        "town": {"unlocked_shops": []},
        "private": {"shed": shed or {}, "seeds": {}, "inventories": [{} for _ in range(n)]},
    }


def test_act_hires_and_returns_valid_shape_at_dawn():
    action = lh.LivestockHandStrategy().act(_fresh_obs(hour=0))
    assert action["farmer"][0] in {"PLANT", "PASS", "WATER"}
    hires = [o for o in action["market"] if o[0] == "HIRE"]
    assert len(hires) == lh.MAX_HANDS
    assert len(action["market"]) <= 10


def test_act_sells_milk_and_wool_from_the_shed():
    obs = _fresh_obs(hour=5, shed={"MILK": 3, "WOOL": 2, "MELON": 6})
    market = lh.LivestockHandStrategy().act(obs)["market"]
    assert ["SELL", "MILK", 3] in market
    assert ["SELL", "WOOL", 2] in market
    assert ["SELL", "MELON", 6] in market


def test_act_never_sells_wheat_feed():
    obs = _fresh_obs(hour=5, shed={"WHEAT": 6})
    market = lh.LivestockHandStrategy().act(obs)["market"]
    assert all(o[1] != "WHEAT" or o[0] != "SELL" for o in market)


def test_act_buys_cow_before_sheep_when_flush():
    obs = _fresh_obs(hour=5, money=3000)
    market = lh.LivestockHandStrategy().act(obs)["market"]
    assert ["BUY_ANIMAL", "COW", 1] in market
    assert ["BUY_ANIMAL", "SHEEP", 1] not in market  # sheep waits for the cow line


def test_act_buys_sheep_once_the_cow_is_placed():
    tiles = _board()
    cx, cy = lh.COW_TILE
    tiles[cy][cx] = _placed(fed_today=True, cared_today=True)
    obs = _fresh_obs(hour=5, money=3000, tiles=tiles)
    market = lh.LivestockHandStrategy().act(obs)["market"]
    assert ["BUY_ANIMAL", "SHEEP", 1] in market
    assert ["BUY_ANIMAL", "COW", 1] not in market  # cow already exists
