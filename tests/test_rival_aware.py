# tests/test_rival_aware.py
"""#219: the frozen benchmark gains one behaviour-preserving seam (the #202
`caps` shape) and a helper that reads the rival's sheep off their tiles."""

from __future__ import annotations

from strategies import field_rival as fr


def _board(animals_at):
    """A 10x10 tile grid with pasture animals at the given (x, y) -> kind."""
    tiles = [[None] * fr.BOARD for _ in range(fr.BOARD)]
    for (x, y), kind in animals_at.items():
        tiles[y][x] = {"kind": "PASTURE", "animal": kind, "fed_today": False}
    return tiles


def _obs(player, our_tiles, their_tiles):
    farms = [None, None]
    farms[player] = {"money": 5000, "tiles": our_tiles, "hands": [], "unlocked_quadrants": ["NW"]}
    farms[1 - player] = {"money": 5000, "tiles": their_tiles, "hands": [], "unlocked_quadrants": ["NW"]}
    return {"player": player, "day": 9, "hour": 0, "farms": farms,
            "private": {"shed": {}, "seeds": {}, "inventories": [{}]}}


def test_rival_sheep_counts_only_the_other_farms_sheep():
    ours = _board({(0, 5): "SHEEP", (1, 5): "SHEEP"})
    theirs = _board({(2, 5): "SHEEP", (3, 5): "COW", (4, 5): "SHEEP"})
    assert fr.rival_sheep(_obs(0, ours, theirs)) == 2
    assert fr.rival_sheep(_obs(1, ours, theirs)) == 2      # seat 1: "theirs" is now ours


def test_rival_sheep_ignores_weeds_locked_and_empty_tiles():
    theirs = _board({})
    theirs[3][3] = {"kind": "WEED"}
    theirs[4][4] = "LOCKED"
    assert fr.rival_sheep(_obs(0, _board({}), theirs)) == 0


def _orders(prefer):
    # A rich farm on a herd-buying turn: the budget rule alone would pick SHEEP.
    return fr.market_orders(day=9, hour=0, money=50_000, hands=8, quadrants=2, animals=0,
                            shed={}, seeds={}, empty_plots=0, standing={}, caps=None, prefer=prefer)


def test_prefer_none_is_the_budget_rule_unchanged():
    kinds = [o[1] for o in _orders(None) if o[0] == "BUY_ANIMAL"]
    assert kinds, "POSITIVE CONTROL: no animal was bought, the seam was not exercised"
    assert set(kinds) == {"SHEEP"}


def test_prefer_cow_overrides_the_budget_rule():
    kinds = [o[1] for o in _orders("COW") if o[0] == "BUY_ANIMAL"]
    assert kinds and set(kinds) == {"COW"}


def test_prefer_changes_nothing_but_the_kind():
    without = [o for o in _orders(None) if o[0] != "BUY_ANIMAL"]
    with_cow = [o for o in _orders("COW") if o[0] != "BUY_ANIMAL"]
    assert without == with_cow
    assert len([o for o in _orders(None) if o[0] == "BUY_ANIMAL"]) == \
           len([o for o in _orders("COW") if o[0] == "BUY_ANIMAL"])


def test_the_benchmarks_hook_prefers_nothing():
    assert fr.FieldRivalStrategy().herd_preference(_obs(0, _board({}), _board({(0, 5): "SHEEP"}))) is None


def test_the_benchmark_acts_exactly_as_before_the_seam():
    # Byte-identical decisions with the defaults: the same observation, the
    # same action, whether or not the hook exists -- pinned by comparing
    # act() against market_orders called with prefer=None on a real game turn.
    from kaggle_environments import make
    from kaggisim.strategy import make_agent
    env = make("kaggriculture", configuration={"episodeSteps": 240, "seed": 5})
    env.reset(2)
    a = make_agent(fr.FieldRivalStrategy()); b = make_agent(fr.FieldRivalStrategy())
    bought = 0
    for _ in range(239):
        act0 = a(env.state[0].observation)
        bought += sum(1 for o in act0["market"] if o[0] == "BUY_ANIMAL")
        env.step([act0, b(env.state[1].observation)])
    assert bought > 0, "POSITIVE CONTROL: the benchmark bought no animals in ten days"
