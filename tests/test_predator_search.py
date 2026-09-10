"""The predator search (#199): seeds, population, fitness and the checkpoint,
against a stub rewards function. No games."""

from __future__ import annotations

import json
import random

from harness import predator as ps
from strategies import predator as pr


def _predator_share(genome_share):
    """A rewards stub: the predator (whichever seat) scores `genome_share`
    of 1000 and the champion the rest -- told apart by the wrapped strategy."""
    def rewards(agent_a, agent_b, seed):
        a = getattr(agent_a, "predator", None)
        b = getattr(agent_b, "predator", None)
        if a is not None:
            return (round(1000 * a), round(1000 * (1 - a)))
        return (round(1000 * (1 - b)), round(1000 * b))
    return rewards


def _fake_make_agent(monkeypatch, share_of):
    """make_agent stub: the callable carries the genome's share for the stub above."""
    def make_agent(strategy):
        def agent(obs):
            return {}
        if isinstance(strategy, pr.PredatorStrategy):
            agent.predator = share_of(strategy.schedule)
        return agent
    monkeypatch.setattr(ps, "make_agent", make_agent)


def test_generation_seeds_are_the_declared_range():
    assert ps.SEED_BASE == 10000 and ps.SEED_STRIDE == 100
    assert ps.generation_seeds(0, 4) == (10000, 10001, 10002, 10003)
    assert ps.generation_seeds(39, 4) == (13900, 13901, 13902, 13903)


def test_initial_population_is_frozen_then_mutants_then_random():
    rng = random.Random(0)
    pop = ps.initial_population(16, 0.15, rng)
    assert len(pop) == 16 and pop[0] == list(pr.FROZEN)
    assert all(len(g) == pr.GENOME_LEN and all(0.0 <= u <= 1.0 for u in g) for g in pop)
    # 7 mutants of FROZEN (close to it), 8 random (not). At sigma=0.15 the
    # mutants' summed abs-diff from FROZEN clusters well under 4 (gaussian
    # noise per component), while random genomes' clusters well over 6; the
    # original `0.15 * 4 * GENOME_LEN == 15.6` bound was loose enough that
    # random genomes counted as "close" too (observed for rng seed 0), so
    # this is tightened to `0.15 * 1.25 * GENOME_LEN` (~4.9), which sits
    # cleanly in the gap between the two clusters.
    close = [sum(abs(a - b) for a, b in zip(g, pr.FROZEN)) < 0.15 * 1.25 * pr.GENOME_LEN for g in pop[1:]]
    assert sum(close[:7]) == 7 and sum(close[7:]) < 8


def test_clamp_keeps_genomes_in_unit_range():
    assert ps.clamp([-0.5, 0.3, 1.7]) == [0.0, 0.3, 1.0]


def test_evaluate_alternates_seats_and_reports_share_and_win_rate(monkeypatch):
    _fake_make_agent(monkeypatch, lambda s: 0.75)
    seats = []
    def rewards(a, b, seed):
        seats.append("pred_first" if hasattr(a, "predator") else "champ_first")
        return _predator_share(None)(a, b, seed)
    r = ps.evaluate(list(pr.FROZEN), lambda: (lambda obs: {}), (1, 2, 3, 4), rewards)
    assert seats == ["pred_first", "champ_first", "pred_first", "champ_first"]
    assert r["fitness"] == 0.75 and r["win_rate"] == 1.0 and (r["wins"], r["ties"], r["games"]) == (4, 0, 4)


def test_search_keeps_elites_evaluates_the_reference_and_checkpoints_each_generation(tmp_path, monkeypatch):
    # fitness = the schedule's melon cap / 24: the search should climb toward cap_melon 24
    _fake_make_agent(monkeypatch, lambda s: s.cap_melon / 24)
    out = tmp_path / "ck.json"
    logged = []
    final = ps.search(generations=3, pop_size=6, games=2, sigma=0.3, seed=1, champion="lean_feed",
                      out=str(out), rewards_fn=_predator_share(None), log=logged.append)
    data = json.loads(out.read_text())
    meta = data["meta"]
    assert meta["generations_completed"] == 3 and len(meta["history"]) == 3
    assert meta["seeds"] == [10200, 10201]
    assert meta["reference"]["fitness"] == 12 / 24 and "win_rate" in meta["reference"]
    assert meta["fitness"] >= meta["reference"]["fitness"]
    assert meta["schedule"]["cap_melon"] == pr.decode(data["genome"]).cap_melon
    assert meta["settings"] == {"generations": 3, "pop": 6, "games": 2, "sigma": 0.3, "seed": 1,
                                "champion": "lean_feed"}
    assert final["meta"]["fitness"] == meta["fitness"]
    # elitism: each generation's best never falls below the previous one's on the stub
    bests = [h["best"]["fitness"] for h in meta["history"]]
    assert bests == sorted(bests)
    assert len(logged) >= 3


def test_search_uses_the_champion_by_name(monkeypatch):
    seen = []
    def load(name):
        seen.append(name)
        return lambda: object()
    monkeypatch.setattr(ps, "load", load)
    _fake_make_agent(monkeypatch, lambda s: 0.5)
    ps.search(generations=1, pop_size=2, games=1, sigma=0.1, seed=0, champion="lean_feed",
              out=None, rewards_fn=_predator_share(None), log=lambda *_: None)
    assert seen and set(seen) == {"lean_feed"}
