"""The offline triage tool (#172 Stage 2): rank whole strategies by seeded
self-play final money. Everything here runs against a fake `play` so the
arithmetic is pinned without a simulator; the one real game is at the end."""

from __future__ import annotations

from harness import triage


def _fake_play(table):
    """A `play` whose rewards are looked up by (agent name, seed)."""
    def play(agent_a, agent_b, seed):
        return table[(agent_a, seed)]
    return play


def _names(name):
    return name          # the fake agent IS its name


def test_the_declared_constants():
    assert triage.SEEDS == (0, 1, 2, 3)
    assert triage.BAR == 0.40
    assert triage.FLOOR == "lean"
    assert triage.MIN_MEMBERS == 5


def test_self_play_score_averages_both_seats_and_all_seeds():
    table = {("a", 0): (100.0, 300.0), ("a", 1): (50.0, 50.0)}
    got = triage.self_play_score("a", seeds=(0, 1), play=_fake_play(table), agents=_names)
    assert got["name"] == "a"
    assert got["per_seed"] == [200.0, 50.0]
    assert got["score"] == 125.0
    assert got["seconds"] >= 0.0


def test_self_play_hands_the_same_strategy_to_both_seats_with_the_seed():
    seen = []

    def play(agent_a, agent_b, seed):
        seen.append((agent_a, agent_b, seed))
        return (1.0, 1.0)

    triage.self_play_score("z", seeds=(7,), play=play, agents=lambda n: f"agent:{n}")
    assert seen == [("agent:z", "agent:z", 7)]


def test_rank_sorts_best_first_and_keeps_input_order_on_ties():
    table = {("low", 0): (1.0, 1.0), ("high", 0): (9.0, 9.0),
             ("tie1", 0): (5.0, 5.0), ("tie2", 0): (5.0, 5.0)}
    rows = triage.rank(["low", "tie1", "high", "tie2"], seeds=(0,),
                       play=_fake_play(table), agents=_names)
    assert [r["name"] for r in rows] == ["high", "tie1", "tie2", "low"]


def test_format_ranking_has_a_header_and_one_line_per_strategy_with_seeds():
    rows = [{"name": "high", "score": 9.0, "per_seed": [9.0, 9.0], "seconds": 0.5},
            {"name": "low", "score": 1.0, "per_seed": [1.5, 0.5], "seconds": 0.4}]
    text = triage.format_ranking(rows)
    lines = [ln for ln in text.splitlines() if ln.strip()]
    assert len(lines) == 3
    assert lines[1].startswith("1") and "high" in lines[1] and "9.0" in lines[1]
    assert "1.5" in lines[2] and "0.5" in lines[2]


def test_format_ranking_aligns_the_name_column_at_ten_or_more_rows():
    # Single-digit and double-digit ranks must put the name in the same
    # column as the header's "strategy" label -- otherwise a 10+-row table
    # visibly staggers between rank 9 and rank 10.
    rows = [{"name": f"strat{i:02d}", "score": float(i), "per_seed": [float(i)], "seconds": 0.1}
            for i in range(10, 0, -1)]
    text = triage.format_ranking(rows)
    lines = text.splitlines()
    header_name_col = lines[0].index("strategy")
    for i, r in enumerate(rows, 1):
        assert lines[i].index(r["name"]) == header_name_col, lines[i]


def test_calibrate_reports_rho_and_the_two_tops():
    scores = {"a": 300.0, "b": 200.0, "c": 100.0, "d": 50.0, "e": 10.0}
    verdicts = {"a": 1.0, "b": 0.9, "c": 0.7, "d": 0.5, "e": 0.1}
    got = triage.calibrate(scores, verdicts)
    assert got["n"] == 5 and got["rho"] == 1.0
    assert got["passed"] is True and got["void"] is False
    assert got["top_predicted"] == "a" and got["top_recorded"] == "a"


def test_calibrate_passes_at_the_bar_and_not_just_under_it():
    scores = {n: float(i) for i, n in enumerate("abcde")}
    verdicts = {n: float(i) for i, n in enumerate("abcde")}          # rho exactly 1.0
    assert triage.calibrate(scores, verdicts, bar=1.0)["passed"] is True
    assert triage.calibrate(scores, verdicts, bar=1.01)["passed"] is False


def test_calibrate_is_void_below_the_minimum_and_never_passes_void():
    scores = {"a": 3.0, "b": 2.0, "c": 1.0, "d": 0.5}
    verdicts = {"a": 1.0, "b": 0.9, "c": 0.7, "d": 0.5}
    got = triage.calibrate(scores, verdicts)
    assert got["void"] is True and got["passed"] is False and got["n"] == 4


def test_calibrate_uses_only_the_names_present_in_both():
    scores = {"a": 3.0, "b": 2.0, "c": 1.0, "d": 0.5, "e": 0.1, "unrecorded": 9.0}
    verdicts = {"a": 1.0, "b": 0.9, "c": 0.7, "d": 0.5, "e": 0.1, "unscored": 0.3}
    got = triage.calibrate(scores, verdicts)
    assert got["n"] == 5 and got["top_predicted"] == "a"


def test_calibrate_with_all_tied_verdicts_is_void_not_zero():
    scores = {"a": 3.0, "b": 2.0, "c": 1.0, "d": 0.5, "e": 0.1}
    verdicts = {n: 0.5 for n in scores}
    got = triage.calibrate(scores, verdicts)
    assert got["rho"] is None and got["void"] is True and got["passed"] is False


def test_floor_holds_only_when_every_member_beats_the_floor():
    assert triage.floor_holds({"a": 10.0, "b": 5.0}, 4.0) is True
    assert triage.floor_holds({"a": 10.0, "b": 4.0}, 4.0) is False     # a tie fails
    assert triage.floor_holds({"a": 10.0, "b": 3.0}, 4.0) is False


def test_head_to_head_alternates_seats_and_counts_strict_wins():
    seen = []

    def play(agent_a, agent_b, seed):
        seen.append((agent_a, agent_b, seed))
        # seat 0 gets 10, seat 1 gets 5, except seed 3 is a tie
        return (7.0, 7.0) if seed == 3 else (10.0, 5.0)

    got = triage.head_to_head_rate("me", opponent="them", seeds=(0, 1, 2, 3), play=play, agents=_names)
    assert seen == [("me", "them", 0), ("them", "me", 1), ("me", "them", 2), ("them", "me", 3)]
    # seed 0: me in seat 0 wins; seed 1: me in seat 1 loses; seed 2: wins; seed 3: tie -> not a win
    assert got == {"name": "me", "opponent": "them", "wins": 2, "ties": 1, "games": 4, "seeds": "0-3"}


def test_head_to_head_alternates_by_list_position_not_seed_parity():
    # opening_bench.our_seat's convention is "alternate by index", so it must
    # hold for ANY seed set, not just one where index parity matches seed
    # parity (as 0,1,2,3 and 100-115 both happen to).
    seen = []

    def play(agent_a, agent_b, seed):
        seen.append((agent_a, agent_b, seed))
        return (10.0, 5.0)

    triage.head_to_head_rate("name", opponent="them", seeds=(2, 4), play=play, agents=_names)
    assert seen == [("name", "them", 2), ("them", "name", 4)]


def test_measure_verdicts_shapes_rows_for_the_file():
    play = lambda a, b, seed: (10.0, 5.0)
    rows = triage.measure_verdicts(["x", "y"], opponent="them", seeds=(0, 1), play=play, agents=_names)
    assert [r["name"] for r in rows] == ["x", "y"]
    for r in rows:
        assert r["games"] == 2 and r["issue"] == 172 and r["source"] == "fresh"
        assert r["seeds"] == "0-1" and "opponent" in r
        assert r["ties"] == 0          # carried through from head_to_head_rate unchanged


def test_load_verdicts_ties_half_scores_fresh_rows_and_leaves_others_unchanged(tmp_path):
    import json
    path = tmp_path / "v.json"
    path.write_text(json.dumps({"protocol": "p", "members": [
        {"name": "a", "wins": 0, "ties": 16, "games": 16, "seeds": "100-115",
         "issue": 172, "source": "fresh"},
        {"name": "b", "wins": 14, "games": 16, "seeds": "100-115", "issue": 202,
         "source": "recorded"}]}))
    assert triage.load_verdicts(str(path)) == {"a": 0.0, "b": 14 / 16}
    got = triage.load_verdicts(str(path), ties_half=True)
    assert got["a"] == 0.5
    assert got["b"] == 14 / 16          # no "ties" key -> unchanged


def test_run_calibration_adds_result_ties_half_from_the_injected_verdicts_unchanged_when_injected():
    # Documented: when verdicts is injected (as in every other test here),
    # result_ties_half is computed from that SAME dict, not from the real
    # calibration_verdicts.json file -- tests stay simple.
    table = {}
    for seed in (0, 1):
        for name, val in (("a", 5.0), ("b", 4.0), ("c", 3.0), ("d", 2.0), ("e", 1.0), ("lean", 0.0)):
            table[(name, seed)] = (val, val)
    verdicts = {"a": 1.0, "b": 0.8, "c": 0.6, "d": 0.4, "e": 0.2}
    got = triage.run_calibration(seeds=(0, 1), play=_fake_play(table), agents=_names,
                                 verdicts=verdicts)
    assert got["result_ties_half"] == got["result"]


def test_run_calibration_computes_result_ties_half_via_load_verdicts_when_not_injected(monkeypatch):
    # verdicts=None (the default) means "not injected" -> result uses
    # load_verdicts() and result_ties_half uses load_verdicts(ties_half=True),
    # which can genuinely differ from each other.
    table = {}
    for seed in (0, 1):
        for name, val in (("a", 5.0), ("b", 4.0), ("c", 3.0), ("d", 2.0), ("e", 1.0), ("lean", 0.0)):
            table[(name, seed)] = (val, val)
    plain_verdicts = {"a": 1.0, "b": 0.8, "c": 0.6, "d": 0.4, "e": 0.2}
    # e now outranks d -- a genuinely different rank order from plain_verdicts,
    # so calibrate() over it must give a different rho, not just a different dict.
    ties_half_verdicts = {"a": 1.0, "b": 0.8, "c": 0.6, "d": 0.4, "e": 0.5}
    calls = []

    def fake_load_verdicts(path=triage.VERDICTS_PATH, ties_half=False):
        calls.append(ties_half)
        return ties_half_verdicts if ties_half else plain_verdicts

    monkeypatch.setattr(triage, "load_verdicts", fake_load_verdicts)

    got = triage.run_calibration(seeds=(0, 1), play=_fake_play(table), agents=_names, verdicts=None)
    assert calls == [False, True]
    assert got["result"] == triage.calibrate(got["scores"], plain_verdicts)
    assert got["result_ties_half"] == triage.calibrate(got["scores"], ties_half_verdicts)
    assert got["result_ties_half"] != got["result"]


def test_append_verdicts_adds_rows_and_refuses_duplicates(tmp_path):
    import json
    path = tmp_path / "v.json"
    path.write_text(json.dumps({"protocol": "p", "members": [
        {"name": "a", "wins": 1, "games": 2, "seeds": "0-1", "issue": 1, "source": "recorded"}]}))
    triage.append_verdicts([{"name": "b", "wins": 2, "games": 2, "seeds": "0-1", "issue": 172,
                             "source": "fresh", "opponent": "meta_bot"}], path=str(path))
    assert [m["name"] for m in json.load(open(path))["members"]] == ["a", "b"]
    import pytest
    with pytest.raises(ValueError):
        triage.append_verdicts([{"name": "a", "wins": 0, "games": 2, "seeds": "0-1", "issue": 172,
                                 "source": "fresh", "opponent": "meta_bot"}], path=str(path))


def test_run_calibration_runs_both_controls_and_calibrates():
    table = {}
    for seed in (0, 1):
        for name, val in (("a", 5.0), ("b", 4.0), ("c", 3.0), ("d", 2.0), ("e", 1.0), ("lean", 0.0)):
            table[(name, seed)] = (val, val)
    verdicts = {"a": 1.0, "b": 0.8, "c": 0.6, "d": 0.4, "e": 0.2}
    got = triage.run_calibration(seeds=(0, 1), play=_fake_play(table), agents=_names,
                                 verdicts=verdicts)
    assert got["floor_score"] == 0.0 and got["floor_ok"] is True
    assert got["determinism_ok"] is True
    assert got["result"]["passed"] is True and got["result"]["n"] == 5
    assert [r["name"] for r in got["rows"]] == ["a", "b", "c", "d", "e"]


def test_run_calibration_reports_a_failed_floor():
    table = {}
    for name, val in (("a", 5.0), ("b", 4.0), ("c", 3.0), ("d", 2.0), ("e", 1.0), ("lean", 1.0)):
        table[(name, 0)] = (val, val)                 # e ties the floor
    verdicts = {"a": 1.0, "b": 0.8, "c": 0.6, "d": 0.4, "e": 0.2}
    got = triage.run_calibration(seeds=(0,), play=_fake_play(table), agents=_names, verdicts=verdicts)
    assert got["floor_ok"] is False


def test_run_calibration_detects_a_nondeterministic_play():
    calls = {"n": 0}

    def drifting(agent_a, agent_b, seed):
        calls["n"] += 1
        return (float(calls["n"]), float(calls["n"]))   # never the same twice

    verdicts = {n: 0.5 for n in "abcde"}
    got = triage.run_calibration(seeds=(0,), play=drifting, agents=_names, verdicts=verdicts)
    assert got["determinism_ok"] is False


def test_default_agents_makes_a_fresh_callable_agent_each_call():
    # "Fresh agent per seat and per game" (self_play_score's docstring) only
    # holds if _default_agents() itself hands back a new agent object each
    # time it is called for the same name, not a cached/shared one.
    agents = triage._default_agents()
    assert agents("lean") is not agents("lean")


def test_a_real_full_self_play_game_ranks_dense_farm_above_lean():
    # The floor control at full length, through the REAL defaults
    # (_default_play/_default_agents -- no play/agents injected), so this is
    # the one test that exercises them: ~4 s for a full 720-turn game.
    #
    # At 240 steps (this test's length before this fix wave) dense_farm's
    # investment has not yet paid off -- its self-play score there is 2308
    # vs lean's 3048, so lean wins -- and dense_farm only overtakes lean from
    # ~360 turns on. Recorded here as an observation, not re-verified by this
    # test: the full 720-step game is what actually ships.
    rows = triage.rank(["lean", "dense_farm"], seeds=(0,))
    assert all(r["score"] > 0 for r in rows), "POSITIVE CONTROL: no money moved, test proves nothing"
    assert [r["name"] for r in rows] == ["dense_farm", "lean"]
