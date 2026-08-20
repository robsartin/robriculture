"""Tests for the per-game production/throughput report (#95).

The report replaces the throwaway `production_diag.py` / `land_check.py`
scratch scripts that produced the #95 diagnostic table. Its job is to make the
throughput gap (8 tiles vs pilkwang's 51) visible on demand, the way
`harness/genome_bench.py` made the fitness gap visible on demand (#70).

Following that module's pattern: the pure aggregation (`summarize`) is
unit-tested against synthetic logs, and the real-game wiring (`play_and_record`,
`resolve_agent`) is tested through injected seams (`play_fn`, `discover_fn`,
`build`) rather than a live `kaggle_environments` game.
"""

from __future__ import annotations

from harness import production_report as pr


# --- snapshot_turn: pure per-turn extraction from raw obs + returned action ---

def _obs(day=1, money=500, tiles=None, unlocked=("NW",), hands=0):
    return {
        "player": 0,
        "day": day,
        "farms": [{
            "money": money,
            "tiles": tiles or [],
            "unlocked_quadrants": list(unlocked),
            "hands": [None] * hands,
        }],
        "private": {"shed": {}},
    }


def test_snapshot_counts_planted_and_animal_tiles_from_raw_obs():
    tiles = [
        [{"kind": "PLANT"}, {"kind": "PLANT"}, {"animal": "COW"}],
        [{}, {"kind": "PLANT"}, None],
    ]
    row = pr.snapshot_turn(_obs(tiles=tiles), {"farmer": ["PASS"], "hands": [], "market": []})
    assert row["plants"] == 3
    assert row["animals"] == 1


def test_snapshot_captures_malformed_obs_as_an_error_row_not_a_crash():
    # Instrumentation must never take down a benchmark game (mirrors
    # harness/external_pool.py's import-failure skip).
    row = pr.snapshot_turn({"player": 0, "farms": []}, {"farmer": ["PASS"]})
    assert "error" in row


def test_snapshot_records_land_purchase_verb_from_farmer_action():
    row = pr.snapshot_turn(_obs(), {"farmer": ["BUY_LAND"], "hands": [], "market": []})
    assert row["verbs"]["BUY_LAND"] == 1


def test_snapshot_records_land_purchase_verb_from_a_hand_action():
    row = pr.snapshot_turn(_obs(), {"farmer": ["PASS"], "hands": [["BUY_LAND"]], "market": []})
    assert row["verbs"]["BUY_LAND"] == 1


def test_snapshot_records_sell_orders_by_item():
    action = {"farmer": ["PASS"], "hands": [], "market": [["SELL", "WHEAT", 5], ["SELL", "MELON", 2]]}
    row = pr.snapshot_turn(_obs(), action)
    assert row["sells"] == {"WHEAT": 5, "MELON": 2}


def test_snapshot_counts_a_non_sell_market_order_as_a_verb_without_a_sale():
    action = {"farmer": ["PASS"], "hands": [], "market": [["BUY_SEED", "WHEAT", 3]]}
    row = pr.snapshot_turn(_obs(), action)
    assert row["verbs"]["BUY_SEED"] == 1
    assert row["sells"] == {}


def test_snapshot_records_quadrants_unlocked_this_turn():
    row = pr.snapshot_turn(_obs(unlocked=("NW", "NE")), {"farmer": ["PASS"], "hands": [], "market": []})
    assert row["unlocked"] == ("NW", "NE")


def test_snapshot_ignores_falsy_entries_in_hands_and_market_lists():
    # A strategy may leave a `None`/empty slot for an unused hand or order --
    # must not raise on `h[0]`/`order[0]` for those.
    action = {"farmer": [None], "hands": [None, []], "market": [None, []]}
    row = pr.snapshot_turn(_obs(), action)
    assert row["verbs"] == {}
    assert row["sells"] == {}


def test_call_falls_back_to_single_arg_when_signature_is_not_introspectable():
    # Some callables (certain C builtins, e.g. `zip`) raise ValueError on
    # inspect.signature(); _call must still fall back to a single-arg call
    # rather than crash.
    result = pr._call(zip, [1, 2, 3])
    assert isinstance(result, zip)


# --- recorder: wraps an agent, appending one snapshot per call ---

def test_recorder_appends_one_snapshot_per_turn_and_returns_inner_action():
    def inner(obs):
        return {"farmer": ["PLANT", "WHEAT"], "hands": [], "market": []}

    log = []
    wrapped = pr.recorder(inner, log)
    act1 = wrapped(_obs(day=1))
    act2 = wrapped(_obs(day=2))

    assert act1["farmer"] == ["PLANT", "WHEAT"]
    assert act2["farmer"] == ["PLANT", "WHEAT"]
    assert [r["day"] for r in log] == [1, 2]


def test_recorder_handles_a_two_arg_external_style_agent():
    # External agents follow kaggle_environments' agent(observation, configuration).
    def inner(obs, config):
        return {"farmer": ["PASS"], "hands": [], "market": []}

    log = []
    wrapped = pr.recorder(inner, log)
    wrapped(_obs())
    assert len(log) == 1


# --- play_and_record: wires both sides through recorder; game-play is injected ---

def test_play_and_record_wraps_both_sides_and_returns_logs_and_rewards():
    def agent_a(obs):
        return {"farmer": ["PLANT", "WHEAT"], "hands": [], "market": []}

    def agent_b(obs):
        return {"farmer": ["PASS"], "hands": [], "market": []}

    def fake_play(wrapped_a, wrapped_b, seed):
        # A minimal fake "game": two turns, calling each wrapped agent directly.
        for day in (1, 2):
            wrapped_a(_obs(day=day))
            wrapped_b(_obs(day=day))
        return 300.0, 100.0

    log_a, log_b, reward_a, reward_b = pr.play_and_record(
        agent_a, agent_b, seed=0, play_fn=fake_play)

    assert len(log_a) == 2 and len(log_b) == 2
    assert (reward_a, reward_b) == (300.0, 100.0)


# --- summarize: pure aggregation over a recorder log ---

def _row(day, money, plants=0, animals=0, hands=0, unlocked=("NW",), sells=None, verbs=None):
    return {
        "day": day, "money": money, "plants": plants, "animals": animals,
        "hands": hands, "unlocked": tuple(unlocked),
        "shed": {}, "sells": sells or {}, "verbs": verbs or {},
    }


def test_summarize_reports_peak_and_mean_plants():
    log = [_row(1, 100, plants=2), _row(2, 100, plants=8), _row(3, 100, plants=5)]
    rep = pr.summarize(log, reward=1000)
    assert rep["plants_peak"] == 8
    assert rep["plants_mean"] == 5.0


def test_summarize_reports_peak_animals_and_hands():
    log = [_row(1, 100, animals=1, hands=2), _row(2, 100, animals=4, hands=3)]
    rep = pr.summarize(log, reward=1000)
    assert rep["animals_peak"] == 4
    assert rep["hands_peak"] == 3


def test_summarize_reports_first_day_each_quadrant_was_seen_unlocked():
    log = [
        _row(1, 100, unlocked=("NW",)),
        _row(5, 100, unlocked=("NW", "NE")),
        _row(9, 100, unlocked=("NW", "NE", "SW")),
    ]
    rep = pr.summarize(log, reward=1000)
    assert rep["quadrants_unlocked"] == {"NW": 1, "NE": 5, "SW": 9}


def test_summarize_reports_confirmed_land_purchases_from_quadrant_growth():
    # The sim's `_do_buy_land` (kaggriculture.py) silently no-ops on
    # insufficient funds, so a `BUY_LAND` verb is only an attempt -- the
    # confirmed record comes from `unlocked_quadrants` actually growing.
    log = [
        _row(1, 100, unlocked=("NW",)),
        _row(3, 1150, unlocked=("NW", "NE"), verbs={"BUY_LAND": 1}),
        _row(9, 3400, unlocked=("NW", "NE", "SW"), verbs={"BUY_LAND": 1}),
    ]
    rep = pr.summarize(log, reward=1000)
    assert rep["land_purchases"] == [
        {"quadrant": "NE", "day": 3, "money": 1150},
        {"quadrant": "SW", "day": 9, "money": 3400},
    ]


def test_summarize_reports_attempted_land_purchases_from_the_buy_land_verb():
    # Attempts are tracked separately from confirmed purchases so a rejected
    # attempt is visible rather than silently absorbed or silently dropped.
    log = [
        _row(1, 100, verbs={}),
        _row(3, 1200, verbs={"BUY_LAND": 1}),
        _row(9, 3400, verbs={"BUY_LAND": 1}),
    ]
    rep = pr.summarize(log, reward=1000)
    assert rep["land_purchase_attempts"] == [{"day": 3, "money": 1200}, {"day": 9, "money": 3400}]


def test_summarize_does_not_count_a_rejected_land_purchase_as_confirmed():
    # Pins the bug: a BUY_LAND verb fires (an attempt) but the sim rejects it
    # for insufficient funds, so unlocked_quadrants never grows. The confirmed
    # count must stay 0 even though an attempt was recorded -- otherwise a
    # policy that only ever *tries* to buy land (and never affords it) would
    # be reported as buying land.
    log = [
        _row(1, 50, unlocked=("NW",), verbs={"BUY_LAND": 1}),  # can't afford $1000 NE
        _row(2, 50, unlocked=("NW",)),                          # still only NW -- rejected
    ]
    rep = pr.summarize(log, reward=1000)
    assert rep["land_purchases"] == []
    assert rep["land_purchase_attempts"] == [{"day": 1, "money": 50}]


def test_summarize_reports_a_confirmed_purchase_even_without_a_captured_attempt_verb():
    # Confirmation is derived purely from the quadrant set growing, not tied
    # to having also captured a BUY_LAND verb on some prior row -- e.g. an
    # error row could have swallowed the turn the verb was issued on. State
    # is the source of truth, not the log of attempts.
    log = [
        _row(1, 100, unlocked=("NW",)),
        _row(2, 1100, unlocked=("NW", "NE")),  # no BUY_LAND verb recorded anywhere
    ]
    rep = pr.summarize(log, reward=1000)
    assert rep["land_purchases"] == [{"quadrant": "NE", "day": 2, "money": 1100}]
    assert rep["land_purchase_attempts"] == []


def test_summarize_reports_units_sold_per_product_and_distinct_count():
    log = [
        _row(1, 100, sells={"WHEAT": 5}),
        _row(2, 100, sells={"WHEAT": 3, "MELON": 1}),
    ]
    rep = pr.summarize(log, reward=1000)
    assert rep["units_sold"] == {"WHEAT": 8, "MELON": 1}
    assert rep["units_sold_total"] == 9
    assert rep["distinct_products_sold"] == 2


def test_summarize_reports_money_peak_and_final():
    log = [_row(1, 500), _row(2, 900), _row(3, 300)]
    rep = pr.summarize(log, reward=1000)
    assert rep["money_peak"] == 900
    assert rep["money_final"] == 300


def test_summarize_flags_money_sat_idle_when_flat_streak_exceeds_a_day():
    # Money sits unchanged, above the cheapest quadrant's cost, for 25 turns.
    log = [_row(d, 2000) for d in range(1, 26)]
    rep = pr.summarize(log, reward=1000)
    assert rep["money_idle_streak"] == 25
    assert rep["money_sat_idle"] is True


def test_summarize_does_not_flag_idle_when_money_keeps_moving():
    log = [_row(d, 1000 + d * 50) for d in range(1, 26)]
    rep = pr.summarize(log, reward=1000)
    assert rep["money_sat_idle"] is False


def test_summarize_does_not_flag_idle_when_flat_money_is_below_the_land_floor():
    # Flat at $50 forever isn't "idle capital" -- there was nothing to spend it on.
    log = [_row(d, 50) for d in range(1, 40)]
    rep = pr.summarize(log, reward=1000)
    assert rep["money_sat_idle"] is False


def test_summarize_ignores_error_rows_when_aggregating():
    log = [_row(1, 100, plants=4), {"error": "boom"}, _row(2, 100, plants=6)]
    rep = pr.summarize(log, reward=1000)
    assert rep["turns"] == 2
    assert rep["turns_with_errors"] == 1
    assert rep["plants_peak"] == 6


def test_summarize_carries_through_the_label_and_reward():
    rep = pr.summarize([_row(1, 100)], reward=57763, label="meta_rancher")
    assert rep["label"] == "meta_rancher"
    assert rep["reward"] == 57763


# --- report_game: orchestrates play_and_record + summarize for both sides ---

def test_report_game_returns_one_summary_per_side():
    def agent_a(obs):
        return {"farmer": ["PLANT", "WHEAT"], "hands": [], "market": []}

    def agent_b(obs):
        return {"farmer": ["PASS"], "hands": [], "market": []}

    def fake_play(wrapped_a, wrapped_b, seed):
        wrapped_a(_obs(day=1, tiles=[[{"kind": "PLANT"}]]))
        wrapped_b(_obs(day=1))
        return 42.0, 7.0

    rep_a, rep_b = pr.report_game("A", agent_a, "B", agent_b, seed=0, play_fn=fake_play)
    assert rep_a["label"] == "A" and rep_a["reward"] == 42.0 and rep_a["plants_peak"] == 1
    assert rep_b["label"] == "B" and rep_b["reward"] == 7.0


# --- resolve_agent: genome path / registered strategy / external agent fragment ---

def test_resolve_agent_loads_a_genome_json_file_over_a_same_named_strategy(tmp_path):
    from harness.evolve import GENOME_LEN
    import json
    genome_path = tmp_path / "some_genome.json"
    genome_path.write_text(json.dumps({"genome": [0.0] * GENOME_LEN}))

    label, agent = pr.resolve_agent(str(genome_path))
    assert label == "some_genome"
    assert callable(agent)


def test_resolve_agent_uses_the_registry_for_a_registered_strategy_name():
    label, agent = pr.resolve_agent(
        "wheat_hands", build=lambda names: {n: f"built:{n}" for n in names})
    assert (label, agent) == ("wheat_hands", "built:wheat_hands")


def test_resolve_agent_matches_an_exact_external_agent_name():
    label, agent = pr.resolve_agent(
        "pilkwang_structured_economic_policy",
        discover_fn=lambda: {"pilkwang_structured_economic_policy": "pilkwang-agent"})
    assert (label, agent) == ("pilkwang_structured_economic_policy", "pilkwang-agent")


def test_resolve_agent_matches_a_unique_external_agent_fragment():
    label, agent = pr.resolve_agent(
        "pilkwang", discover_fn=lambda: {"pilkwang_structured_economic_policy": "pilkwang-agent"})
    assert label == "pilkwang_structured_economic_policy"
    assert agent == "pilkwang-agent"


def test_resolve_agent_raises_on_an_ambiguous_external_fragment():
    import pytest
    with pytest.raises(ValueError):
        pr.resolve_agent("a", discover_fn=lambda: {"aaa": "1", "abb": "2"})


def test_resolve_agent_raises_on_an_unknown_spec():
    import pytest
    with pytest.raises(ValueError):
        pr.resolve_agent("totally_unknown_thing", discover_fn=lambda: {})
