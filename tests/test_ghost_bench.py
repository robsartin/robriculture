"""The ghost bench (issue #204): pure helpers behind the measurement.

The bench itself plays 63 full seasons, so the full-game entrypoints are
integration code. What is unit-tested here is everything that could quietly
report a wrong number: which seat we sat in, which seed the episode ran under,
how a residual is sized, and how a day-8 melon count is read off a board.
"""

from __future__ import annotations

from harness import ghost_bench as gb


def _replay(teams, seed=1504396418):
    return {"info": {"TeamNames": list(teams), "seed": seed}, "rewards": [1.0, 2.0]}


def test_episode_seed_reads_the_seed_the_episode_actually_ran_under():
    # configuration.seed is null in a downloaded replay; info.seed is the real one.
    assert gb.episode_seed(_replay(["Minikotey", "Rob Sartin"])) == 1504396418


def test_episode_seed_is_none_when_the_replay_records_no_seed():
    # No seed means no exact re-drive; the caller must be able to see that.
    assert gb.episode_seed(_replay(["a", "b"], seed=None)) is None


def test_seat_of_finds_us_on_either_side_of_the_board():
    # We are player 0 in some episodes and player 1 in others; ghosting the
    # wrong seat would replay our own agent and measure nothing.
    assert gb.seat_of(_replay(["Minikotey", "Rob Sartin"])) == 1
    assert gb.seat_of(_replay(["Rob Sartin", "Minikotey"])) == 0


def test_seat_of_raises_when_we_are_not_in_the_episode():
    # Silently defaulting to seat 0 would mislabel every row.
    try:
        gb.seat_of(_replay(["Minikotey", "someone else"]))
    except ValueError:
        return
    raise AssertionError("expected ValueError for an episode we did not play")


def test_residual_fraction_is_the_relative_gap_to_the_recorded_money():
    # 7.3% of 50,000 is 3,650: this is the scale the control is judged on.
    assert gb.residual_fraction(53650.0, 50000.0) == 0.073
    assert gb.residual_fraction(46350.0, 50000.0) == 0.073


def test_residual_fraction_of_an_exact_reproduction_is_zero():
    assert gb.residual_fraction(48144.0, 48144.0) == 0.0


def test_residual_fraction_is_one_when_the_recorded_money_is_zero_and_ours_is_not():
    # A zero denominator must not raise and must not read as a perfect match.
    assert gb.residual_fraction(10.0, 0.0) == 1.0
    assert gb.residual_fraction(0.0, 0.0) == 0.0


def _board(melon, other=0):
    row = ([{"kind": "PLANT", "crop": "MELON"}] * melon
           + [{"kind": "PLANT", "crop": "WHEAT"}] * other)
    return [row]


def _steps_with_boards(boards):
    """A steps table shaped like both a replay and a live env: the shared
    observation, farms included, lives on player 0's slot."""
    return [[{"observation": {"farms": [{"tiles": b0}, {"tiles": b1}]}}, {"observation": {}}]
            for b0, b1 in boards]


def test_standing_melon_counts_live_melon_tiles_for_the_named_player():
    steps = _steps_with_boards([(_board(3), _board(12, other=4))])
    assert gb.standing_melon(steps, 0, player=1) == 12
    assert gb.standing_melon(steps, 0, player=0) == 3


def test_standing_melon_is_zero_when_the_step_is_past_the_end_of_the_episode():
    # A crashed episode is shorter than the probe; that is 0 melon, not a crash.
    assert gb.standing_melon(_steps_with_boards([(_board(9), _board(9))]), 500, 1) == 0


def test_probe_step_is_mid_day_on_day_8():
    # The replay medians in strategies/field_rival.py are sampled mid-day, so
    # the trigger this bench reports is read at the same hour they were.
    assert gb.PROBE_STEP == 8 * 24 + 12


def test_win_rate_counts_only_wins_over_every_game_played():
    # The ladder pays for a win; a tie is not half a win here, and the
    # denominator is every episode benched, not just the decided ones.
    rows = [{"win": True}, {"win": False}, {"win": False}, {"win": True}]
    assert gb.win_rate(rows) == 0.5
    assert gb.win_rate([]) == 0.0


def test_control_passes_only_when_enough_episodes_land_inside_the_residual():
    # Declared in #204 before code: 55 of 63 within the 7.3% residual.
    assert gb.control_passed([0.0] * 55 + [0.9] * 8) is True
    assert gb.control_passed([0.0] * 54 + [0.9] * 9) is False


def test_control_counts_an_episode_exactly_on_the_tolerance_as_inside_it():
    assert gb.control_passed([gb.RESIDUAL_TOLERANCE] * 63) is True


def test_the_declared_criteria_are_the_ones_the_issue_states():
    # Frozen so a later edit cannot quietly move the bar (ADR-0007).
    assert (gb.RESIDUAL_TOLERANCE, gb.CONTROL_MINIMUM) == (0.073, 55)
    assert (gb.LADDER_WIN_RATE, gb.WIN_RATE_TOLERANCE) == (0.403, 0.10)
    assert (gb.TRIGGER_SHARE, gb.MELON_TRIGGER_TILES) == (0.50, 10)


def _full_replay():
    """A downloaded replay is ~21 MB of observations; the bench needs the
    actions, the seed, the seat and the recorded rewards, and nothing else."""
    return {
        "info": {"TeamNames": ["Minikotey", "Rob Sartin"], "seed": 7},
        "rewards": [53043.0, 47207.0],
        "steps": [
            [{"action": None, "observation": {"big": "x" * 1000}},
             {"action": None, "observation": {}}],
            [{"action": {"farmer": ["NORTH"]}, "observation": {"big": "x" * 1000}},
             {"action": {"farmer": ["SOUTH"]}, "observation": {}}],
        ],
    }


def test_episode_digest_keeps_both_scripts_the_seat_the_seed_and_the_rewards():
    d = gb.episode_digest("ep.json", _full_replay())
    assert d["episode"] == "ep.json"
    assert d["seed"] == 7
    assert d["seat"] == 1
    assert d["rewards"] == [53043.0, 47207.0]
    assert d["scripts"] == [[None, {"farmer": ["NORTH"]}], [None, {"farmer": ["SOUTH"]}]]


def test_episode_digest_drops_the_observations_it_was_built_from():
    # 63 replays at ~21 MB each cannot all be resident; holding one whole replay
    # per bench row was enough to make the run thrash.
    d = gb.episode_digest("ep.json", _full_replay())
    assert d["scripts"][0][1] == {"farmer": ["NORTH"]}, "the actions must survive"
    assert "x" * 1000 not in repr(d), "the observations must not"


def test_ghost_players_are_callables_that_replay_both_recorded_scripts():
    """A Strategy is not an agent. Passing the Ghost object itself to env.run
    ran a whole 63-episode control that reported every farm still holding its
    3,000 starting money -- 'DONE', and completely empty."""
    players = gb.ghost_players(gb.episode_digest("ep.json", _full_replay()))
    assert [p({"step": 0}) for p in players] == [{"farmer": ["NORTH"]},
                                                 {"farmer": ["SOUTH"]}]


def test_standing_melon_is_zero_for_a_seat_the_observation_does_not_carry():
    """A single-farm observation must read as no melon, not raise."""
    steps = [[{"observation": {"farms": [{"tiles": _board(11)}]}}, {"observation": {}}]]
    assert gb.standing_melon(steps, 0, player=1) == 0
