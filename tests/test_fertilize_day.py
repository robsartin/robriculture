"""The fertilizer seams take the day (#282): ignored on the benchmark, passed by act."""

from __future__ import annotations

import inspect

from strategies import field_rival as fr


def test_both_seams_accept_a_day_and_still_return_none_on_the_benchmark():
    s = fr.FieldRivalStrategy()
    for name in ("fertilizer_stock", "fertilize_crops"):
        params = inspect.signature(getattr(fr.FieldRivalStrategy, name)).parameters
        assert list(params) == ["self", "day"] and params["day"].default is None, name
        assert getattr(s, name)() is None and getattr(s, name)(6) is None and getattr(s, name)(day=12) is None


def test_act_passes_the_observations_day_to_both_seams():
    seen = {}

    class Probe(fr.FieldRivalStrategy):
        def fertilizer_stock(self, day=None):
            seen["stock"] = day
            return None

        def fertilize_crops(self, day=None):
            seen["crops"] = day
            return None

    from kaggisim.state import parse
    from kaggle_environments import make
    env = make("kaggriculture", configuration={"seed": 1088, "episodeSteps": 3})
    obs = parse(env.reset()[0].observation)
    Probe().act(obs)
    assert seen == {"stock": obs.get("day", 0), "crops": obs.get("day", 0)}


def test_the_old_fertilized_contender_follows_the_arity():
    from strategies.fertilized import FertilizedStrategy
    f = FertilizedStrategy()
    assert f.fertilizer_stock(0) == 24 and f.fertilize_crops(day=3) == ("STRAWBERRY", "MELON")


def test_feed_benchs_identity_stub_follows_the_arity():
    from harness import feed_bench as fdb
    off = fdb.off_class()()
    assert off.fertilizer_stock(6) is None and off.fertilize_crops(6) is None
