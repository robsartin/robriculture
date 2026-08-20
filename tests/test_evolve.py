"""Neuroevolution harness (Phase 2, #66)."""
from __future__ import annotations
import json
import random
import pytest
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
    """No sibling opponents at all (sample_k <= 0 and an empty/disabled
    Hall-of-Fame) is neutral, not a zero — not specific to generation 0.

    Scoring the absent pool as 0.0 would drag every such genome down by a
    constant and make it incomparable to generations with a nonempty pool.
    """
    assert ev.blended_fitness(0.8, None, 0.75) == 0.8


def test_blended_fitness_full_anchor_weight_ignores_the_pool():
    """anchor_weight 1.0 makes the sibling pool contribute nothing."""
    assert ev.blended_fitness(0.6, 0.9, 1.0) == 0.6


def test_default_anchors_excludes_spoiler_when_pool_is_built():
    """spoiler is a labelled adversarial stress test (#78), not a fitness-defining anchor."""
    assert "spoiler" not in ev.DEFAULT_ANCHORS


def test_evolve_fitness_is_dominated_by_the_anchors():
    """The #70 regression guard: beating siblings must NOT be able to mask
    losing to every anchor. This is the exact failure that pinned fitness at
    0.5833 while the agent went 0-for-5 against the real field.

    #107 sharpens this further: `best_fitness` is now the ANCHOR-only share
    (0.10, the true state), not the blend (0.20, which the sibling-tie term
    inflates). The blend is still available under `best_fitness_blended` for
    inspection, but it must never be what a cross-generation comparison — or
    a reader of the saved artifact — sees as "the fitness".
    """
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
    # anchor share 0.10, sibling share 0.50 -> blend 0.75*0.10 + 0.25*0.50 = 0.20
    assert result["best_fitness"] == pytest.approx(0.1)
    assert result["best_fitness_blended"] == pytest.approx(0.2)


def test_evolve_history_reports_anchor_share_unmoved_by_sibling_drift():
    """#104: the printed 'best' is a blend that deflates as the sibling pool
    converges, even when the agent's real (anchor) performance holds steady —
    so the anchor-only figure must be reported too, and must not move when
    only the sibling term does.

    The stub scores every anchor match (opponent tagged "anchor") at a fixed
    0.8 share regardless of generation, while sibling matches (untagged
    population-vs-population, keyed off the generation-derived seed) decay
    from 0.9 to 0.5 as if the population were converging. If evolve() reports
    an anchor figure that is really just plumbing the blend, or recomputing
    something sibling-influenced, it will move; the real anchor share cannot.
    """
    def rewards(a, b, seed=None):
        if getattr(b, "tag", "") == "anchor":
            return (0.8, 0.2)                      # anchor share always 0.8
        gen = (seed - 50000) // 7919
        target = {0: 0.9, 1: 0.7, 2: 0.5}.get(gen, 0.5)
        return (target, 1.0 - target)               # sibling share decays

    result = ev.evolve(generations=3, pop_size=2, games=1, sigma=0.1, sample_k=1,
                       hof_cap=0, anchor_names=(), seed=0, rewards_fn=rewards,
                       anchor_weight=0.75, anchor_agents_override=[_tagged("anchor")])
    history = result["history"]

    anchors = [h["anchor"] for h in history]
    blended = [h["best"] for h in history]
    assert anchors == pytest.approx([0.8, 0.8, 0.8])          # unmoved by sibling drift
    assert blended == pytest.approx([0.825, 0.775, 0.725])    # blend still falls as siblings converge


def test_evolve_selects_the_later_higher_anchor_genome_not_generation_zeros():
    """#107: the DEFECT ITSELF. Cross-generation selection must track anchor
    share, not the blend.

    Scripted so the blend is HIGHEST at generation 0 (a saturated 1.0 sibling
    share masks a low 0.10 anchor share) and FALLS in later generations even
    as anchor share climbs to 0.35 — the exact shape #104 measured in a real
    run (population converging while the agent keeps improving). The buggy
    `gen_best_f > best_fit` comparison latches onto generation 0 forever and
    never lets go, because nothing ever blends higher again. The fix must
    instead track the rising anchor share and end up with generation 2's
    figures, both anchor and blend.
    """
    anchor_by_gen = {0: 0.10, 1: 0.20, 2: 0.35}
    sibling_by_gen = {0: 1.00, 1: 0.50, 2: 0.00}

    def rewards(a, b, seed=None):
        if getattr(b, "tag", "") == "anchor":
            gen = seed // 7919
            share = anchor_by_gen[gen]
        else:
            gen = (seed - 50000) // 7919
            share = sibling_by_gen[gen]
        return (share, 1.0 - share)

    result = ev.evolve(generations=3, pop_size=4, games=1, sigma=0.05, sample_k=1,
                       hof_cap=0, anchor_names=(), seed=0, rewards_fn=rewards,
                       anchor_weight=0.75, anchor_agents_override=[_tagged("anchor")])

    blended = [h["best"] for h in result["history"]]
    anchors = [h["anchor"] for h in result["history"]]
    assert blended == pytest.approx([0.325, 0.275, 0.2625])   # falls as gen 0's sibling boost fades
    assert anchors == pytest.approx([0.10, 0.20, 0.35])       # true progress: rises every generation

    # Generation 0 has the run's highest blend, so the buggy `>` comparison
    # would have kept generation 0's genome for the whole run.
    assert max(blended) == blended[0]

    # The fix: best_fitness tracks the rising anchor share, landing on
    # generation 2 — the fittest genome the search actually found — not
    # generation 0's inflated blend of 0.325.
    assert result["best_fitness"] == pytest.approx(0.35)
    assert result["best_fitness_blended"] == pytest.approx(0.2625)   # gen 2's own blend


def test_within_generation_selection_still_ranks_by_the_blend():
    """#107 changes CROSS-generation selection only. WITHIN a generation the
    sibling-pressure blend must still decide the winner (ADR-0008) — that
    comparison is apples-to-apples, since every genome in a generation faces
    the same pool.

    Genome A has the higher blend (0.4) but the LOWER anchor share (0.2);
    genome B has the lower blend (0.3375) but the HIGHER anchor share (0.45).
    If within-generation ranking were ever switched to anchor-only, B would
    win instead of A, and the recorded 'anchor' history entry would jump to
    0.45. It must stay 0.2 — A's anchor share — proving A, not B, was picked.
    """
    import harness.evolve as E
    pop_a = [0.0] * ev.GENOME_LEN
    pop_b = [1.0] * ev.GENOME_LEN
    orig_init = E.initial_population
    orig_agent = E.genome_agent
    E.initial_population = lambda size, seed: [pop_a, pop_b]
    E.genome_agent = lambda g: _tagged("A" if g[0] == 0.0 else "B")
    try:
        def rewards(a, b, seed=None):
            mine = getattr(a, "tag", "")
            if getattr(b, "tag", "") == "anchor":
                share = 0.20 if mine == "A" else 0.45
            else:
                share = 1.00 if mine == "A" else 0.00
            return (share, 1.0 - share)

        result = ev.evolve(generations=1, pop_size=2, games=1, sigma=0.0, sample_k=1,
                           hof_cap=0, anchor_names=(), seed=0, rewards_fn=rewards,
                           anchor_weight=0.75, anchor_agents_override=[_tagged("anchor")])
    finally:
        E.initial_population = orig_init
        E.genome_agent = orig_agent

    assert result["history"][0]["best"] == pytest.approx(0.4)      # A's blend won the sort
    assert result["history"][0]["anchor"] == pytest.approx(0.20)   # A's anchor, not B's 0.45
    assert result["best_genome"] == pop_a


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
        assert set(out) == {"best_genome", "best_fitness", "best_fitness_blended", "history"}
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


def test_seeded_population_keeps_the_seed_verbatim():
    """Element 0 is the seed itself, so a run can never score below its starting point."""
    seed_g = [0.5] * ev.GENOME_LEN
    pop = ev.seeded_population(seed_g, size=4, sigma=0.1, rng=random.Random(3))
    assert len(pop) == 4
    assert pop[0] == seed_g
    assert all(g != seed_g for g in pop[1:])          # the rest are mutants


def test_seeded_population_is_deterministic_for_a_seeded_rng():
    """ADR-0005: the same rng seed reproduces the same population exactly."""
    seed_g = [0.5] * ev.GENOME_LEN
    a = ev.seeded_population(seed_g, size=4, sigma=0.1, rng=random.Random(3))
    b = ev.seeded_population(seed_g, size=4, sigma=0.1, rng=random.Random(3))
    assert a == b


def test_evolve_starts_from_the_seed_genome_when_given_one():
    """A seeded run begins at the champion, not at random noise."""
    def rewards(a, b, seed=None):
        return (100.0, 100.0)

    seed_g = [0.5] * ev.GENOME_LEN
    out = ev.evolve(generations=1, pop_size=4, games=2, sigma=0.0, sample_k=1,
                    hof_cap=1, anchor_names=(), seed=1, rewards_fn=rewards,
                    anchor_agents_override=[_tagged("")], seed_genome=seed_g)
    # sigma 0 makes every mutant identical to the seed, so the winner must be it.
    assert out["best_genome"] == seed_g


def test_load_genome_round_trips_a_saved_artifact(tmp_path):
    """A genome written by save_genome loads back identically."""
    p = tmp_path / "g.json"
    g = [0.25] * ev.GENOME_LEN
    ev.save_genome(str(p), g, {"fitness": 0.5})
    assert ev.load_genome(str(p)) == g


def test_load_genome_rejects_a_wrong_length_genome(tmp_path):
    """Fail loudly, never silently fall back to random weights.

    A silent fallback is exactly what shipped a submission running on random
    weights before the Phase 4 fix — the failure must be impossible to miss.
    """
    p = tmp_path / "short.json"
    ev.save_genome(str(p), [0.1, 0.2, 0.3], {})
    with pytest.raises(ValueError, match="length"):
        ev.load_genome(str(p))


def test_load_genome_rejects_a_missing_file(tmp_path):
    """A typo'd path must stop the run, not quietly start from noise."""
    with pytest.raises(ValueError, match="seed genome"):
        ev.load_genome(str(tmp_path / "nope.json"))


def test_checkpoint_genome_writes_a_loadable_artifact(tmp_path):
    """A checkpoint is a real genome artifact, loadable mid-run."""
    p = tmp_path / "ckpt.json"
    g = [0.25] * ev.GENOME_LEN
    assert ev.checkpoint_genome(str(p), g, 0.42, [{"gen": 0, "best": 0.42}]) is True
    assert ev.load_genome(str(p)) == g


def test_checkpoint_genome_records_progress_in_meta(tmp_path):
    """The checkpoint carries fitness and generations-so-far, so an interrupted
    run is interpretable without the console output."""
    p = tmp_path / "ckpt.json"
    ev.checkpoint_genome(str(p), [0.25] * ev.GENOME_LEN, 0.42,
                         [{"gen": 0, "best": 0.4}, {"gen": 1, "best": 0.42}])
    meta = json.loads(p.read_text())["meta"]
    assert meta["fitness"] == 0.42
    assert meta["generations_completed"] == 2
    assert meta["checkpoint"] is True


def test_checkpoint_genome_carries_the_run_settings(tmp_path):
    """An interrupted run's checkpoint is the ONLY surviving artifact, so it must
    record the same settings the final save_genome() call does — not just
    progress — or it isn't reproducible (ADR-0005, #70)."""
    p = tmp_path / "ckpt.json"
    settings = {"seed": 7, "anchor_weight": 0.6, "pop": 20}
    ev.checkpoint_genome(str(p), [0.25] * ev.GENOME_LEN, 0.42,
                         [{"gen": 0, "best": 0.42}], settings=settings)
    meta = json.loads(p.read_text())["meta"]
    assert meta["seed"] == 7
    assert meta["anchor_weight"] == 0.6
    assert meta["pop"] == 20
    # checkpoint-specific fields still win over the run settings.
    assert meta["fitness"] == 0.42
    assert meta["generations_completed"] == 1
    assert meta["checkpoint"] is True


def test_checkpoint_genome_survives_a_write_failure(tmp_path):
    """A disk hiccup must not kill an 8-hour run — warn and carry on."""
    blocker = tmp_path / "not_a_dir"
    blocker.write_text("i am a file, not a directory")
    bad = blocker / "sub" / "ckpt.json"
    assert ev.checkpoint_genome(str(bad), [0.25] * ev.GENOME_LEN, 0.1, []) is False


def test_evolve_checkpoints_once_per_generation():
    """Every generation persists the best-so-far, so an interrupt loses at most one."""
    calls = []

    def rewards(a, b, seed=None):
        return (100.0, 100.0)

    ev.evolve(generations=3, pop_size=4, games=2, sigma=0.1, sample_k=1, hof_cap=1,
              anchor_names=(), seed=1, rewards_fn=rewards,
              anchor_agents_override=[_tagged("")],
              checkpoint_fn=lambda g, f, h: calls.append((f, len(h))))
    assert len(calls) == 3
    assert [n for _, n in calls] == [1, 2, 3]


def test_checkpoint_genome_survives_a_non_serializable_value(tmp_path):
    """json.dump raises TypeError (not OSError) on a bad value; that must not
    escape either — the same #70 guarantee, for a different failure mode."""
    p = tmp_path / "ckpt.json"
    bad_history = [{"gen": 0, "best": object()}]
    assert ev.checkpoint_genome(str(p), [0.25] * ev.GENOME_LEN, 0.1, bad_history) is False


def test_evolve_checkpoints_best_so_far_not_current_generation_best():
    """A generation that regresses must not overwrite a better earlier checkpoint.

    pop_size=1 and hof_cap=0 keep the population's single genome unchanged across
    generations, and the sole opponent pool is empty until the anchor supplies it —
    so the only thing that varies per generation is the seed evolve derives as
    `seed + gen * 7919`. The stub reward keys off that seed to make generation 1
    collapse (share 0.1) and generation 2 only partially recover (share 0.5), both
    well below generation 0's 0.9. A checkpoint that tracked the current
    generation's best (the #70 regression this guards against) would record
    [0.9, 0.1, 0.5]; tracking best-so-far must record [0.9, 0.9, 0.9].
    """
    calls = []

    def rewards(a, b, seed=None):
        if seed < 7919:
            return (900.0, 100.0)          # generation 0: dominant
        if seed < 15838:
            return (100.0, 900.0)          # generation 1: collapses
        return (100.0, 100.0)              # generation 2: partial recovery, still < gen 0

    ev.evolve(generations=3, pop_size=1, games=1, sigma=0.1, sample_k=1, hof_cap=0,
              anchor_names=(), seed=1, rewards_fn=rewards,
              anchor_agents_override=[_tagged("anchor")],
              checkpoint_fn=lambda g, f, h: calls.append(f))
    assert len(calls) == 3
    assert calls == [0.9, 0.9, 0.9]


def _recording_rewards(calls):
    """Return a rewards_fn that appends (seed, agent_a, agent_b) per call and
    reports a flat tie, so the test can inspect exactly what evolve() called
    without any share/fitness computation muddying the seeds."""
    def rewards(a, b, seed=None):
        calls.append((seed, a, b))
        return (100.0, 100.0)
    return rewards


def test_two_genomes_in_the_same_generation_play_identical_maps_when_paired():
    """#72: dropping the per-genome `+ i` offset means every genome in a
    generation is scored on the same seeds (common random numbers) — a paired
    comparison. Before the fix, genome i's seed base was shifted by i, so no
    two genomes in a population ever played the same map and truncation
    selection was partly ranking on map luck rather than genome quality."""
    calls = []
    ev.evolve(generations=1, pop_size=2, games=3, sigma=0.1, sample_k=0, hof_cap=0,
              anchor_names=(), seed=1, rewards_fn=_recording_rewards(calls),
              anchor_agents_override=[_tagged("anchor")])
    seeds = [seed for seed, _, _ in calls]
    assert len(seeds) == 6                     # pop_size(2) * games(3), one anchor
    genome0_seeds, genome1_seeds = seeds[:3], seeds[3:]
    assert genome0_seeds == genome1_seeds


def test_opponent_record_calls_rewards_fn_once_per_game_with_distinct_seeds():
    """The genuinely load-bearing property: one rewards_fn call per game, each
    on a distinct seed. A regression to `oi * games` instead of `oi * 100000`,
    or to dropping the per-game `+ g`, would collapse `--games 4` into replaying
    a single map four times and silently inflating confidence four-fold. A
    regression to two rewards_fn calls per game (the #70 single-pass gap) would
    fail the call-count assertion here."""
    calls = []
    ev.opponent_record(_tagged(""), _tagged(""), games=4, seed_base=10,
                       rewards_fn=_recording_rewards(calls))
    seeds = [seed for seed, _, _ in calls]
    assert len(seeds) == 4                     # call count == games
    assert seeds == [10, 11, 12, 13]            # distinct seeds within one opponent


def test_match_share_offsets_each_opponent_by_100000():
    """Each opponent's seed base is shifted by `oi * 100000` so opponents never
    replay each other's maps. A regression to `oi * games` would collide the
    moment two opponents shared a seed_base close enough together."""
    calls = []
    ev.match_share(_tagged(""), [_tagged("o0"), _tagged("o1")], games=2, seed_base=5,
                   rewards_fn=_recording_rewards(calls))
    seeds = [seed for seed, _, _ in calls]
    assert seeds == [5, 6, 100005, 100006]


def test_evolve_offsets_the_sibling_pool_seeds_by_50000_from_the_anchor_seeds():
    """The sibling-pool match is seeded 50000 above the anchor match so anchors
    and Hall-of-Fame/siblings never replay identical games. sample_k=1 with
    pop_size=2 gives genome 0 exactly one sibling opponent: genome 1."""
    calls = []
    ev.evolve(generations=1, pop_size=2, games=1, sigma=0.1, sample_k=1, hof_cap=0,
              anchor_names=(), seed=1, rewards_fn=_recording_rewards(calls),
              anchor_agents_override=[_tagged("anchor")])
    seeds = [seed for seed, _, _ in calls]
    # genome 0: one anchor game (seed 1), one sibling game (seed 1 + 50000);
    # genome 1: identical seeds, since the generation's base is now paired (#72).
    assert seeds == [1, 50001, 1, 50001]
