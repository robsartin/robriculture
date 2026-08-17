"""Tests for the promotion harness (ADR-0007's strategy-experiment gate).

The promotion test decides whether a challenger strategy is *actually better*
than the current champion: run N seeded games, and promote only if the win-rate
clears a bar AND a binomial test rejects the 50% coin-flip null. These tests
cover the statistics and the game-tallying independently, using an injected
`play_fn` so most tests need no real (slow) games.
"""

from __future__ import annotations

import pytest

from harness import promotion
from harness.promotion import (
    Record,
    PromotionResult,
    binomial_p_value,
    run_match,
    round_robin_rank,
    designate_champion,
    save_champion,
    load_champion,
    promotion_test,
)


# --- binomial_p_value: one-sided P(X >= wins | n=decisive, p=0.5) ---

def test_binomial_all_wins_is_tiny():
    # Winning all 10 decisive games by chance: (1/2)^10.
    assert binomial_p_value(10, 10) == pytest.approx(1 / 1024)


def test_binomial_bare_majority_is_not_significant():
    # P(X >= 5 | 10, .5) = sum C(10,k), k=5..10 = 638, over 1024.
    assert binomial_p_value(5, 10) == pytest.approx(638 / 1024)


def test_binomial_no_decisive_games_is_no_evidence():
    assert binomial_p_value(0, 0) == 1.0


def test_binomial_more_wins_means_smaller_p():
    assert binomial_p_value(60, 100) < binomial_p_value(55, 100) < binomial_p_value(50, 100)


# --- Record: win-rate excludes ties; p-value via the binomial ---

def test_win_rate_excludes_ties():
    r = Record(wins=11, losses=9, ties=5)
    assert r.games == 25
    assert r.decisive == 20
    assert r.win_rate == pytest.approx(0.55)
    assert r.tie_rate == pytest.approx(0.2)


def test_win_rate_with_no_decisive_games_is_one_half():
    assert Record(wins=0, losses=0, ties=4).win_rate == 0.5


def test_record_p_value_matches_binomial():
    r = Record(wins=60, losses=40)
    assert r.p_value == pytest.approx(binomial_p_value(60, 100))


# --- PromotionResult.passed: bar AND significance, both required ---

def test_promotes_when_clearly_better():
    r = Record(wins=60, losses=40)
    res = PromotionResult(challenger="c", champion="m", record=r, bar=0.55, alpha=0.05)
    assert res.win_rate == pytest.approx(0.6)
    assert res.passed is True


def test_rejects_when_bar_met_but_not_significant():
    # 55/45: win-rate exactly meets the bar, but p ~ 0.18 -> not distinguishable.
    r = Record(wins=55, losses=45)
    res = PromotionResult(challenger="c", champion="m", record=r, bar=0.55, alpha=0.05)
    assert res.win_rate == pytest.approx(0.55)
    assert res.p_value > 0.05
    assert res.passed is False


def test_rejects_when_below_bar_even_if_significant():
    # A huge sample at 52% is significant vs 50 but still under a 55% bar.
    r = Record(wins=520, losses=480)
    res = PromotionResult(challenger="c", champion="m", record=r, bar=0.55, alpha=0.05)
    assert res.win_rate < 0.55
    assert res.passed is False


# --- run_match: seeded, alternates sides, tallies from the challenger's view ---

def test_run_match_alternates_sides_and_tallies():
    calls = []

    def fake_play(a, b, seed):
        calls.append((a, b, seed))
        return 1  # whoever is player A always wins

    rec = run_match("CHAL", "CHAMP", games=4, play_fn=fake_play)
    # Even games: challenger is A and wins. Odd games: champion is A, so the raw
    # result is negated -> challenger loses. So 2 wins, 2 losses.
    assert (rec.wins, rec.losses, rec.ties) == (2, 2, 0)
    assert len(calls) == 4
    assert calls[0][:2] == ("CHAL", "CHAMP")   # even game: challenger on side A
    assert calls[1][:2] == ("CHAMP", "CHAL")   # odd game: sides swapped


def test_run_match_uses_supplied_seeds():
    seen = []

    def fake_play(a, b, seed):
        seen.append(seed)
        return 0

    rec = run_match("C", "M", seeds=[7, 8, 9], play_fn=fake_play)
    assert seen == [7, 8, 9]
    assert rec.games == 3 and rec.ties == 3


def test_run_match_counts_ties():
    rec = run_match("C", "M", games=5, play_fn=lambda a, b, seed: 0)
    assert (rec.wins, rec.losses, rec.ties) == (0, 0, 5)


# --- round_robin_rank / designate_champion (fake play_fn, no real games) ---

def _strength_play(strength):
    def play(a, b, seed):
        return (strength[a] > strength[b]) - (strength[a] < strength[b])
    return play


def test_round_robin_rank_orders_by_win_rate():
    ranking = round_robin_rank(
        {"A": "A", "B": "B", "C": "C"},
        games=2,
        play_fn=_strength_play({"A": 3, "B": 2, "C": 1}),
    )
    assert [name for name, *_ in ranking] == ["A", "B", "C"]


def test_designate_champion_picks_the_strongest():
    champ = designate_champion(
        ["A", "B", "C"],
        games=2,
        play_fn=_strength_play({"A": 3, "B": 2, "C": 1}),
        build=lambda names: {n: n for n in names},
    )
    assert champ == "A"


# --- champion persistence ---

def test_save_and_load_champion(tmp_path):
    path = tmp_path / "champion.json"
    ranking = [("greedy", 0.7, 14, 20), ("lean", 0.3, 6, 20)]
    save_champion(path, "greedy", games=20, ranking=ranking)
    assert load_champion(path) == "greedy"


# --- integration smoke: real games wire together end to end (slow-ish) ---

def test_promotion_test_runs_real_games():
    res = promotion_test("greedy", "random", games=2)
    assert res.record.games == 2
    assert res.challenger == "greedy" and res.champion == "random"


def test_current_champion_reads_the_recorded_file():
    import json

    from harness.promotion import CHAMPION_PATH, current_champion

    # Don't pin the champion's identity (it changes as strategies evolve) — just
    # assert current_champion() reflects whatever is recorded in champion.json.
    assert current_champion() == json.load(open(CHAMPION_PATH))["champion"]


def test_promotion_test_defaults_to_the_recorded_champion():
    from harness.promotion import current_champion

    # No real games: inject a fake play and a fake agent-builder.
    res = promotion_test(
        "greedy",
        games=2,
        play_fn=lambda a, b, seed: 1,
        build=lambda names: {n: n for n in names},
    )
    assert res.champion == current_champion()
    assert res.record.games == 2


# --- pool_share_rank: rank by score share (#70), not win-rate ---

def _named(tag):
    """A stub agent carrying a tag the stub rewards_fn can key off."""
    def agent(obs):
        return {"farmer": ["PASS"], "hands": [], "market": []}
    agent.tag = tag
    return agent


def _stub_rewards(a, b, seed=None):
    """Reward equals the agent's tag length — longer tag scores higher."""
    return (float(len(getattr(a, "tag", ""))), float(len(getattr(b, "tag", ""))))


def test_pool_share_rank_orders_by_share_descending():
    """The strongest agent by score share ranks first."""
    cands = {"aaa": _named("aaa"), "a": _named("a")}
    pool = {"aa": _named("aa")}
    rows = promotion.pool_share_rank(cands, pool, games=2, rewards_fn=_stub_rewards)
    assert [r["name"] for r in rows] == ["aaa", "a"]
    assert rows[0]["share"] > rows[1]["share"]


def test_pool_share_rank_never_plays_a_candidate_against_itself():
    """A candidate that is also in the pool must not be its own opponent —
    a self-match always scores 0.5 and would drag every share toward the mean."""
    seen = []

    def recording_rewards(a, b, seed=None):
        seen.append((getattr(a, "tag", ""), getattr(b, "tag", "")))
        return (100.0, 100.0)

    cands = {"x": _named("x")}
    pool = {"x": _named("x"), "y": _named("y")}
    promotion.pool_share_rank(cands, pool, games=2, rewards_fn=recording_rewards)
    assert all("x" not in (a, b) or a != b for a, b in seen)
    assert all({a, b} != {"x"} for a, b in seen)


def test_pool_share_rank_carries_the_benchmark_flag():
    """The artifact records which rows are external benchmarks."""
    cands = {"aaa": _named("aaa"), "a": _named("a")}
    pool = {"aa": _named("aa")}
    rows = promotion.pool_share_rank(cands, pool, games=2,
                                     rewards_fn=_stub_rewards, benchmarks={"aaa"})
    flags = {r["name"]: r["benchmark"] for r in rows}
    assert flags == {"aaa": True, "a": False}


def test_pool_share_rank_is_deterministic_for_fixed_seeds():
    """ADR-0005: same arguments, same ranking."""
    cands = {"aaa": _named("aaa"), "a": _named("a")}
    pool = {"aa": _named("aa")}
    kw = dict(games=2, rewards_fn=_stub_rewards)
    assert promotion.pool_share_rank(cands, pool, **kw) == promotion.pool_share_rank(cands, pool, **kw)


def test_pool_share_rank_raises_on_an_empty_pool():
    """No opponents means no measurement — fail rather than emit 0.5 for everyone."""
    with pytest.raises(ValueError, match="pool"):
        promotion.pool_share_rank({"a": _named("a")}, {}, games=2, rewards_fn=_stub_rewards)


def test_pool_share_rank_raises_when_a_candidate_is_the_only_pool_entry():
    """Self-exclusion can empty a candidate's opponent list; that must raise.

    match_share returns 0.5 for an empty opponent list by design (#70). Letting
    that through here would designate a champion on a number that means
    "no evidence" rather than "evenly matched".
    """
    with pytest.raises(ValueError, match="no opponents"):
        promotion.pool_share_rank({"x": _named("x")}, {"x": _named("x")},
                                  games=2, rewards_fn=_stub_rewards)


def test_top_contender_takes_names_and_skips_benchmarks():
    """top_contender now consumes best-first names, not ranking tuples."""
    assert promotion.top_contender(["meta_bot", "ranch_hands"], {"meta_bot"}) == "ranch_hands"
    assert promotion.top_contender(["ranch_hands", "meta_bot"], {"meta_bot"}) == "ranch_hands"


def test_top_contender_raises_when_every_name_is_a_benchmark():
    """There is no valid submit default if everything is external."""
    with pytest.raises(ValueError):
        promotion.top_contender(["meta_bot"], {"meta_bot"})
