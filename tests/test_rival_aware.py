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


def test_prefer_changes_only_the_kind_when_the_budget_is_not_binding():
    # money=50_000 is the non-binding regime: the reserve floor is never
    # reached, so forcing the kind changes which animal is bought but not how
    # many. On a budget-bound turn the count itself changes too -- see
    # test_a_cheaper_animal_buys_more_head_on_a_budget_bound_turn below.
    without = [o for o in _orders(None) if o[0] != "BUY_ANIMAL"]
    with_cow = [o for o in _orders("COW") if o[0] != "BUY_ANIMAL"]
    assert without == with_cow
    assert len([o for o in _orders(None) if o[0] == "BUY_ANIMAL"]) == \
           len([o for o in _orders("COW") if o[0] == "BUY_ANIMAL"])


def test_a_cheaper_animal_buys_more_head_on_a_budget_bound_turn():
    # #219 whole-branch review, Important 1: forcing the cheaper animal also
    # buys MORE head once the reserve floor binds -- a second, coupled effect
    # of the seam that the identity/mechanism/quiet controls never exercise
    # (none of them is budget-bound at this ramp target). Verified by hand as
    # a pure market_orders call: at money=2100 the baseline (budget rule) buys
    # one sheep before the reserve stops it; forcing COW buys two, because
    # each head costs less against the same CAPITAL_RESERVE floor.
    kwargs = dict(day=12, hour=3, money=2100, hands=8, quadrants=3, animals=0,
                  shed={}, seeds={}, empty_plots=0, standing={}, caps=None)
    baseline = [o[1] for o in fr.market_orders(prefer=None, **kwargs) if o[0] == "BUY_ANIMAL"]
    forced = [o[1] for o in fr.market_orders(prefer="COW", **kwargs) if o[0] == "BUY_ANIMAL"]
    assert baseline == ["SHEEP"]
    assert forced == ["COW", "COW"]


def test_the_benchmarks_hook_prefers_nothing():
    assert fr.FieldRivalStrategy().herd_preference(_obs(0, _board({}), _board({(0, 5): "SHEEP"}))) is None


def test_a_full_game_still_buys_animals_with_the_seam_in_place():
    # Positive control: the benchmark still buys animals over a full game
    # once the herd_preference seam exists. Not an identity pin -- identity
    # is pinned by test_prefer_none_is_the_budget_rule_unchanged above and
    # the frozen pins in tests/test_field_rival.py.
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


from strategies import rival_aware as ra


def test_the_threshold_is_declared():
    assert ra.SHEEP_THRESHOLD == 2 and ra.RivalAwareStrategy.THRESHOLD == 2


def test_prefers_cows_once_the_rival_shows_two_sheep():
    s = ra.RivalAwareStrategy()
    one = _obs(0, _board({}), _board({(0, 5): "SHEEP"}))
    two = _obs(0, _board({}), _board({(0, 5): "SHEEP", (1, 5): "SHEEP"}))
    cows = _obs(0, _board({}), _board({(0, 5): "COW", (1, 5): "COW", (2, 5): "COW"}))
    assert s.herd_preference(one) is None
    assert s.herd_preference(two) == "COW"
    assert s.herd_preference(cows) is None


def test_it_is_a_registered_contender_built_on_dense_farm():
    from strategies import REGISTRY, load
    from strategies.dense_farm import DenseFarmStrategy
    assert "rival_aware" in REGISTRY and load("rival_aware") is ra.RivalAwareStrategy
    assert issubclass(ra.RivalAwareStrategy, DenseFarmStrategy)
    assert ra.RivalAwareStrategy.benchmark is False
    assert ra.RivalAwareStrategy.CAPS == DenseFarmStrategy.CAPS


def test_identity_control_threshold_off_is_dense_farm_to_the_value():
    # Spec control 1: with the threshold unreachable the contender IS dense_farm
    # on a full seeded game, both seats' rewards equal to the value.
    from kaggle_environments import make
    from kaggisim.strategy import make_agent
    from strategies import load

    class Off(ra.RivalAwareStrategy):
        THRESHOLD = 10 ** 9

    def rewards(ours):
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": 21})
        env.run([make_agent(ours), make_agent(load("dense_farm")())])
        return [s.reward or 0 for s in env.steps[-1]]

    base = rewards(load("dense_farm")())
    assert base[0] > 0, "POSITIVE CONTROL: no money moved"
    assert rewards(Off()) == base
