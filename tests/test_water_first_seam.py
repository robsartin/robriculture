"""The carry_limit and water_first seams on the frozen benchmark (#341): off
by default; on, a ready melon is watered before it is cut, and a worker banks
at the given carry."""

from __future__ import annotations

from strategies import field_rival as fr


def _melon(planted, day, yield_units, watered=False):
    return {"kind": "PLANT", "crop": "MELON", "planted_day": planted, "yield_units": yield_units,
            "watered_today": watered, "fertilized_until_day": -1}


def _straw(planted, yield_units, watered=False):
    return {"kind": "PLANT", "crop": "STRAWBERRY", "planted_day": planted, "yield_units": yield_units,
            "watered_today": watered, "fertilized_until_day": -1}


def test_plot_action_waters_a_ready_unwatered_melon_below_full_yield_only_when_asked():
    ready = _melon(0, 10, 5)
    assert fr.plot_action(ready, "MELON", 10, 5) == ["HARVEST"]                       # frozen: harvest first
    assert fr.plot_action(ready, "MELON", 10, 5, water_first=True) == ["WATER"]
    assert fr.plot_action(_melon(0, 10, 5, watered=True), "MELON", 10, 5, water_first=True) == ["HARVEST"]
    assert fr.plot_action(_melon(0, 10, 6), "MELON", 10, 5, water_first=True) == ["HARVEST"]       # already full
    assert fr.plot_action(_melon(0, 13, 5), "MELON", 13, 5, water_first=True) == ["HARVEST"]       # past max_yield_day
    assert fr.plot_action(_melon(0, 9, 4), "MELON", 9, 5, water_first=True) == ["WATER"]           # not ready: frozen waters anyway
    assert fr.plot_action(_straw(0, 3), "STRAWBERRY", 12, 5, water_first=True) == ["HARVEST"]      # ongoing: frozen
    for tile in (None, "LOCKED", {"kind": "WEED"}):
        assert fr.plot_action(tile, "MELON", 10, 5, water_first=True) == fr.plot_action(tile, "MELON", 10, 5)


def _cluster_board(tiles_by_xy):
    board = [[None for _ in range(10)] for _ in range(10)]
    for (x, y), t in tiles_by_xy.items():
        board[y][x] = t
    return board


def test_crop_worker_banks_at_the_given_carry():
    cluster = [(1, 1)]
    board = _cluster_board({(1, 1): _melon(0, 10, 6, watered=True)})
    pos = [1, 1]
    heavy = {"MELON": 6}
    assert fr.crop_worker_action(cluster, board, pos, heavy, "MELON", 10, 5) != ["HARVEST"]                  # frozen: 6 banks
    assert fr.crop_worker_action(cluster, board, pos, heavy, "MELON", 10, 5, carry=18) == ["HARVEST"]
    assert fr.crop_worker_action(cluster, board, pos, {"MELON": 18}, "MELON", 10, 5, carry=18) != ["HARVEST"]


def test_crop_worker_passes_water_first_through():
    cluster = [(1, 1)]
    board = _cluster_board({(1, 1): _melon(0, 10, 5)})
    pos = [1, 1]
    assert fr.crop_worker_action(cluster, board, pos, {}, "MELON", 10, 5) == ["HARVEST"]
    assert fr.crop_worker_action(cluster, board, pos, {}, "MELON", 10, 5, water_first=True) == ["WATER"]


def test_the_hooks_return_none_on_the_benchmark_and_are_seams():
    from harness.sheep_bench import _seam_names
    s = fr.FieldRivalStrategy()
    assert s.carry_limit() is None and s.water_first() is None
    names = _seam_names()
    assert {"carry_limit", "water_first"} <= set(names) and len(names) == 20


def test_act_passes_the_hooks_to_the_crop_workers(monkeypatch):
    from kaggisim.state import parse
    from kaggle_environments import make
    seen = []
    real = fr.crop_worker_action
    def spy(*a, **k):
        seen.append((k.get("carry"), k.get("water_first")))
        return real(*a, **k)
    monkeypatch.setattr(fr, "crop_worker_action", spy)
    env = make("kaggriculture", configuration={"seed": 2522, "episodeSteps": 3})
    obs = parse(env.reset()[0].observation)
    fr.FieldRivalStrategy().act(obs)
    assert seen and all(c == fr.CARRY_LIMIT and w is False for c, w in seen)
    seen.clear()
    on = type("On", (fr.FieldRivalStrategy,), {"carry_limit": lambda self: 18, "water_first": lambda self: True})()
    out = on.act(obs)
    assert set(out) >= {"farmer", "hands", "market"}
    assert seen and all(c == 18 and w is True for c, w in seen)


def test_the_stub_switches_both_off():
    from harness import feed_bench
    off = feed_bench.off_class()()
    assert off.carry_limit() is None and off.water_first() is None
