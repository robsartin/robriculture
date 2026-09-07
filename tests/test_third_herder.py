"""#239: a third herder from day 8, on top of #237's pasture lead.

#237 VOIDed on its mechanism control but recorded the shape of the problem:
with pasture led ahead of the herd, the contender and the champion still
finished on the same 8 pasture tiles, the same 8 head placed and the same 4
head stuck in the shed. `LIVESTOCK_WORKERS` is two indices, and eight tiles is
what two herders can build and tend. This arm names a third, through the
`livestock_workers` seam on the frozen benchmark; the pasture lead of 3 and
#219's cow rule come from the bases unchanged.
"""

from __future__ import annotations

from strategies import field_rival as fr
from strategies import third_herder as th


def test_the_declared_constants():
    assert th.HERDER_DAY == 8
    assert th.ThirdHerderStrategy.HERDER_DAY == 8
    assert th.THIRD_HERDER == 6
    assert th.ThirdHerderStrategy.name == "third_herder"
    assert th.ThirdHerderStrategy.benchmark is False


def test_the_third_herder_starts_on_the_declared_day_and_not_before():
    s = th.ThirdHerderStrategy()
    assert s.livestock_workers(7) is None
    assert s.livestock_workers(8) == (1, 2, 6)
    for day in range(fr.SEASON_DAYS):
        expected = (1, 2, 6) if day >= th.HERDER_DAY else None
        assert s.livestock_workers(day) == expected, day


def test_it_keeps_the_benchmarks_two_herders_and_adds_to_them():
    # A third herder, not a different pair: the arm is one change.
    s = th.ThirdHerderStrategy()
    assert set(fr.LIVESTOCK_WORKERS) < set(s.livestock_workers(th.HERDER_DAY))


def test_the_third_herder_gives_up_its_own_cluster_and_nobody_elses():
    workers = th.ThirdHerderStrategy().livestock_workers(th.HERDER_DAY)
    assert fr.crop_cluster(th.THIRD_HERDER, workers) == ()
    for worker in range(1 + fr.MAX_HANDS):
        if worker in workers:
            continue
        assert fr.crop_cluster(worker, workers) == fr.crop_cluster(worker), worker


def test_it_is_a_registered_contender_built_on_the_pasture_lead():
    from strategies import REGISTRY, load
    from strategies.pasture_ahead import PastureAheadStrategy
    from strategies.rival_aware import RivalAwareStrategy
    assert "third_herder" in REGISTRY
    assert load("third_herder") is th.ThirdHerderStrategy
    assert issubclass(th.ThirdHerderStrategy, PastureAheadStrategy)
    # Inherited, not restated: the pasture lead of 3 (#237), #219's cow rule
    # and the crop caps all come from the bases unchanged.
    assert th.ThirdHerderStrategy.LEAD_TILES == PastureAheadStrategy.LEAD_TILES
    assert th.ThirdHerderStrategy.THRESHOLD == RivalAwareStrategy.THRESHOLD
    assert th.ThirdHerderStrategy.CAPS == RivalAwareStrategy.CAPS


def test_identity_control_every_hook_off_is_dense_farm_to_the_value():
    # Control (i), declared on #239: with all four seams returning None --
    # herd_preference, pasture_count, herd_target and livestock_workers -- the
    # arm IS `dense_farm` on a full seeded game, both seats' rewards equal to
    # the value. One assertion pins the whole seam stack, including #239's own.
    from kaggle_environments import make
    from kaggisim.strategy import make_agent
    from strategies import load

    class Off(th.ThirdHerderStrategy):
        def herd_preference(self, obs):
            return None

        def pasture_count(self, day, animals):
            return None

        def herd_target(self, day):
            return None

        def livestock_workers(self, day):
            return None

    def rewards(ours):
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": 816})
        env.run([make_agent(ours), make_agent(load("dense_farm")())])
        return [s.reward or 0 for s in env.steps[-1]]

    base = rewards(load("dense_farm")())
    assert base[0] > 0, "POSITIVE CONTROL: no money moved"
    assert rewards(Off()) == base
