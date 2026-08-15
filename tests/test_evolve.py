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


def _tagged(tag):
    """Return a stub agent with a tag."""
    def agent(obs): return {"farmer": ["PASS"], "hands": [], "market": []}
    agent.tag = tag
    return agent


def _stub_rewards(a, b, seed=None):
    """Deterministic rewards: an agent tagged "win" scores 300 to the other's 100."""
    if getattr(a, "tag", "") == "win":
        return (300.0, 100.0)
    if getattr(b, "tag", "") == "win":
        return (100.0, 300.0)
    return (100.0, 100.0)


def test_opponent_record_counts_ties_as_half_win_rate():
    """Evenly-matched agents draw every game: win-rate and share both 0.5."""
    rec = ev.opponent_record(_tagged(""), _tagged(""), games=4, seed_base=0,
                             rewards_fn=_stub_rewards)
    assert rec["t"] == 4 and rec["w"] == 0 and rec["l"] == 0
    assert rec["win_rate"] == 0.5
    assert rec["share"] == 0.5


def test_opponent_record_all_wins_is_win_rate_one():
    """Winning every game reports win_rate 1.0 and a share above 0.5."""
    rec = ev.opponent_record(_tagged("win"), _tagged(""), games=2, seed_base=0,
                             rewards_fn=_stub_rewards)
    assert rec["w"] == 2 and rec["win_rate"] == 1.0
    assert rec["share"] == 0.75          # 300 / (300 + 100)


def test_opponent_record_all_losses_is_win_rate_zero():
    """Losing every game reports win_rate 0.0 — but a share that is still graded."""
    rec = ev.opponent_record(_tagged(""), _tagged("win"), games=4, seed_base=0,
                             rewards_fn=_stub_rewards)
    assert rec["l"] == 4 and rec["win_rate"] == 0.0
    assert rec["share"] == 0.25          # 100 / (100 + 300) — the gradient #70 needs


def test_opponent_record_alternates_sides_to_cancel_first_player_advantage():
    """A sim where seat A always wins must score 0.5, not 1.0, if sides alternate."""
    def first_player_wins(a, b, seed=None):
        return (300.0, 100.0)

    rec = ev.opponent_record(_tagged(""), _tagged(""), games=4, seed_base=0,
                             rewards_fn=first_player_wins)
    assert rec["win_rate"] == 0.5
    assert rec["share"] == 0.5


def test_opponent_record_zero_games_falls_back_to_half():
    """No games played is not evidence of anything — report the neutral 0.5."""
    rec = ev.opponent_record(_tagged(""), _tagged(""), games=0, seed_base=0,
                             rewards_fn=_stub_rewards)
    assert rec["games"] == 0
    assert rec["win_rate"] == 0.5 and rec["share"] == 0.5


def test_opponent_record_win_loss_counts_agree_with_share():
    """The record and the share are derived from the same rewards, so they agree."""
    rec = ev.opponent_record(_tagged("win"), _tagged(""), games=4, seed_base=0,
                             rewards_fn=_stub_rewards)
    assert rec["w"] + rec["t"] + rec["l"] == rec["games"] == 4
    assert rec["share"] > 0.5 and rec["win_rate"] == 1.0


def test_match_share_averages_across_opponents():
    """Fitness weights every opponent equally, regardless of pool size."""
    opps = [_tagged("win"), _tagged("")]     # shares 0.25 and 0.50
    assert ev.match_share(_tagged(""), opps, games=2, seed_base=0,
                          rewards_fn=_stub_rewards) == 0.375


def test_match_share_no_opponents_falls_back_to_half():
    """An empty pool is neutral, not a loss — generation 0 has no Hall-of-Fame."""
    assert ev.match_share(_tagged(""), [], games=4, seed_base=0,
                          rewards_fn=_stub_rewards) == 0.5


def test_blended_fitness_weights_anchors_more_heavily():
    """Anchors are the real field, so they dominate: 0.75 anchor / 0.25 sibling."""
    assert ev.blended_fitness(0.8, 0.4, 0.75) == 0.75 * 0.8 + 0.25 * 0.4


def test_blended_fitness_ignores_an_empty_sibling_pool():
    """Generation 0 has no Hall-of-Fame; a missing pool is neutral, not a zero.

    Scoring the absent pool as 0.0 would drag every gen-0 genome down by a
    constant and make gen 0 incomparable to later generations.
    """
    assert ev.blended_fitness(0.8, None, 0.75) == 0.8


def test_blended_fitness_full_anchor_weight_ignores_the_pool():
    """anchor_weight 1.0 makes the sibling pool contribute nothing."""
    assert ev.blended_fitness(0.6, 0.9, 1.0) == 0.6


def test_evolve_fitness_is_dominated_by_the_anchors():
    """The #70 regression guard: beating siblings must NOT be able to mask
    losing to every anchor. This is the exact failure that pinned fitness at
    0.5833 while the agent went 0-for-5 against the real field."""
    def rewards(a, b, seed=None):
        # Every neuropilot genome loses badly to the lone anchor and ties siblings.
        if getattr(a, "tag", "") == "anchor":
            return (900.0, 100.0)
        if getattr(b, "tag", "") == "anchor":
            return (100.0, 900.0)
        return (100.0, 100.0)

    result = ev.evolve(generations=2, pop_size=4, games=2, sigma=0.1, sample_k=2,
                       hof_cap=2, anchor_names=(), seed=1, rewards_fn=rewards,
                       anchor_weight=0.75, anchor_agents_override=[_tagged("anchor")])
    # anchor share 0.10, sibling share 0.50 -> 0.75*0.10 + 0.25*0.50 = 0.20
    assert result["best_fitness"] == 0.2


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


def test_update_hof_cap_zero_disables():
    hof = ev.update_hof([], [[1.0]*ev.GENOME_LEN, [2.0]*ev.GENOME_LEN], cap=0)
    assert hof == []


def test_evolve_is_deterministic_and_reports_history():
    # Stub: reward tracks the genome mean, so mutation toward higher weights wins; no real games.
    def stub(a, b, seed=None):
        return (getattr(a, "_score", 0.0) + 1.0, getattr(b, "_score", 0.0) + 1.0)
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
                       hof_cap=2, anchor_names=[], seed=1, rewards_fn=stub,
                       anchor_agents_override=[_tagged("")])
        assert set(out) == {"best_genome", "best_fitness", "history"}
        assert len(out["history"]) == 3
        out2 = E.evolve(generations=3, pop_size=6, games=1, sigma=0.2, sample_k=2,
                        hof_cap=2, anchor_names=[], seed=1, rewards_fn=stub,
                        anchor_agents_override=[_tagged("")])
        assert out2["best_fitness"] == out["best_fitness"]     # deterministic
    finally:
        E.genome_agent = orig


def test_save_genome_round_trips(tmp_path):
    """save_genome writes a JSON with genome and meta; reads back losslessly."""
    import json
    p = tmp_path / "g.json"
    ev.save_genome(str(p), [0.1, 0.2], {"fitness": 0.7})
    d = json.loads(p.read_text())
    assert d["genome"] == [0.1, 0.2] and d["meta"]["fitness"] == 0.7


def test_share_is_half_when_scores_are_equal():
    """A tie in reward is a 0.5 share — the same value a tied game scores."""
    assert ev.share(100.0, 100.0) == 0.5


def test_share_is_half_when_both_scores_are_zero():
    """Degenerate both-zero games must not divide by zero."""
    assert ev.share(0, 0) == 0.5
    assert ev.share(None, None) == 0.5


def test_share_clamps_negative_scores_to_zero():
    """A negative reward is floored at 0 so share stays inside [0, 1]."""
    assert ev.share(-50.0, 50.0) == 0.0
    assert ev.share(50.0, -50.0) == 1.0


def test_share_is_one_when_opponent_scores_nothing():
    """Outscoring an opponent who earned nothing is a full share."""
    assert ev.share(20000.0, 0.0) == 1.0


def test_share_is_proportional_between_the_extremes():
    """The champion's real 20570-vs-59136 game lands at its reward proportion."""
    assert ev.share(20570.0, 59136.0) == 20570.0 / (20570.0 + 59136.0)
