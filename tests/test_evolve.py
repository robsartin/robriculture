"""Neuroevolution harness (Phase 2, #66)."""
from __future__ import annotations
import random
from harness import evolve as ev


def test_initial_population_shape_and_determinism():
    pop = ev.initial_population(5, seed=1)
    assert len(pop) == 5
    assert all(len(g) == ev.GENOME_LEN for g in pop)
    assert ev.initial_population(5, seed=1) == pop            # deterministic
    assert ev.initial_population(5, seed=2) != pop            # seed matters


def test_mutate_preserves_length_changes_weights_deterministically():
    g = [0.0] * ev.GENOME_LEN
    m1 = ev.mutate(g, sigma=0.1, rng=random.Random(7))
    assert len(m1) == ev.GENOME_LEN and m1 != g
    assert m1 == ev.mutate(g, sigma=0.1, rng=random.Random(7))  # same rng seed => same


def test_mutate_sigma_zero_is_a_noop():
    g = [0.3] * ev.GENOME_LEN
    assert ev.mutate(g, sigma=0.0, rng=random.Random(1)) == g


def test_select_elites_returns_top_k_by_fitness():
    scored = [(["a"], 0.2), (["b"], 0.9), (["c"], 0.5)]
    assert ev.select_elites(scored, 2) == [["b"], ["c"]]


def test_next_generation_keeps_elites_and_refills_to_size():
    elites = [[0.0]*ev.GENOME_LEN, [1.0]*ev.GENOME_LEN]
    gen = ev.next_generation(elites, size=5, sigma=0.1, rng=random.Random(3))
    assert len(gen) == 5
    assert gen[0] in elites and gen[1] in elites               # elitism: elites carried verbatim


def _stub_play(a, b, seed=None):
    """Deterministic: agent tagged "win" beats everything; ties if both tagged "tie"."""
    if getattr(a, "tag", "") == "win": return 1
    if getattr(b, "tag", "") == "win": return -1
    return 0


def _tagged(tag):
    """Return a stub agent with a tag."""
    def agent(obs): return {"farmer": ["PASS"], "hands": [], "market": []}
    agent.tag = tag
    return agent


def test_match_winrate_counts_ties_as_half():
    """Ties contribute 0.5 to win-rate."""
    me = _tagged("")                                  # always ties vs a plain opp
    opp = [_tagged("")]
    assert ev.match_winrate(me, opp, games=4, seed_base=0, play_fn=_stub_play) == 0.5


def test_match_winrate_all_wins_is_one():
    """Win all games => 1.0 win-rate."""
    assert ev.match_winrate(_tagged("win"), [_tagged("")], games=2, seed_base=0, play_fn=_stub_play) == 1.0


def test_evaluate_population_returns_genome_fitness_pairs():
    """Evaluate population returns (genome, fitness) pairs."""
    pop = ev.initial_population(3, seed=1)
    scored = ev.evaluate_population(pop, [_tagged("")], games=2, seed_base=0, play_fn=_stub_play)
    assert len(scored) == 3
    assert all(g in pop and 0.0 <= f <= 1.0 for g, f in scored)


def test_build_opponents_includes_anchors_hof_and_a_pop_sample():
    rng = random.Random(0)
    pop = [_tagged(f"p{i}") for i in range(5)]
    opp = ev.build_opponents(pop, [_tagged("anchor")], [_tagged("hof")], sample_k=2, rng=rng)
    tags = [getattr(a, "tag", "") for a in opp]
    assert "anchor" in tags and "hof" in tags
    assert sum(t.startswith("p") for t in tags) == 2


def test_update_hof_keeps_best_and_caps():
    hof = ev.update_hof([], [[1.0]*ev.GENOME_LEN, [2.0]*ev.GENOME_LEN], cap=1)
    assert len(hof) == 1


def test_evolve_is_deterministic_and_reports_history():
    # Stub: fitness = mean of genome (so mutation toward higher weights wins); no real games.
    def stub(a, b, seed=None):
        return (getattr(a, "_score", 0) > getattr(b, "_score", 0)) - (getattr(a, "_score", 0) < getattr(b, "_score", 0))
    # Monkeypatch genome_agent to tag the agent with its genome mean for the stub.
    import harness.evolve as E
    orig = E.genome_agent
    def tagged_agent(g):
        ag = _tagged("")
        ag._score = sum(g) / len(g)
        return ag
    E.genome_agent = tagged_agent
    try:
        out = E.evolve(generations=3, pop_size=6, games=1, sigma=0.2, sample_k=2,
                       hof_cap=2, anchor_names=[], seed=1, play_fn=stub)
        assert set(out) == {"best_genome", "best_fitness", "history"}
        assert len(out["history"]) == 3
        out2 = E.evolve(generations=3, pop_size=6, games=1, sigma=0.2, sample_k=2,
                        hof_cap=2, anchor_names=[], seed=1, play_fn=stub)
        assert out2["best_fitness"] == out["best_fitness"]     # deterministic
    finally:
        E.genome_agent = orig
