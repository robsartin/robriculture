"""Steal the opening book: replay a winner's first three days (issue #207).

The hypothesis is that the herd is hard to *establish*, not hard to run, so
these tests guard the two joints the claim rests on: the opening is replayed
verbatim at the right replay index (the #157 offset again), and the hand-over
happens on exactly the turn declared -- one turn early or late and neither the
control nor the result is measuring what #207 declared.
"""

from __future__ import annotations

from strategies import REGISTRY
from strategies.ghost import PASS
from strategies.opening_book import (OPENING_TURNS, OpeningBookStrategy,
                                     shift_script)

A1 = {"farmer": ["NORTH"], "hands": [], "market": []}
A2 = {"farmer": ["PLANT", "MELON"], "hands": [], "market": [["SELL", "MELON", 3]]}
HANDOVER = {"farmer": ["SOUTH"], "hands": [], "market": []}


class _Recorder:
    """A stand-in hand-over agent that says so, and counts its resets."""

    def __init__(self):
        self.resets = 0
        self.seen = []

    def act(self, obs):
        self.seen.append(obs)
        return HANDOVER

    def reset(self):
        self.resets += 1


def _book(script, handover=None, opening_turns=3):
    return OpeningBookStrategy(script=script,
                               handover=handover or _Recorder(),
                               opening_turns=opening_turns)


def test_opening_turns_is_the_first_three_days_of_the_sim():
    """#207 replays days 0-2; the sim runs 24 turns to a day. Single-sourced
    from `kaggisim.economy` so a config change cannot silently move it."""
    from kaggisim import economy
    assert OPENING_TURNS == 3 * economy.CONFIG_DEFAULTS["turnsPerDay"] == 72


def test_replays_the_action_recorded_one_index_past_the_observation():
    """The #157 offset: obs.step==0 owes the action at replay index 1."""
    assert _book([None, A1, A2]).act({"step": 0}) == A1


def test_replays_the_whole_opening_up_to_and_including_the_last_opening_turn():
    """Index 3 with opening_turns=3 is still the book, not the hand-over."""
    assert _book([None, A1, A1, A2]).act({"step": 2}) == A2


def test_hands_over_on_the_first_turn_after_the_opening():
    """obs.step==3 owes index 4, which is past a 3-turn opening: hand over."""
    assert _book([None, A1, A1, A2, A1]).act({"step": 3}) == HANDOVER


def test_keeps_delegating_once_the_opening_is_over():
    """The book is spent for the rest of the season, script or no script."""
    book = _book([None, A1, A1, A2, A1, A1])
    assert book.act({"step": 4}) == HANDOVER
    assert book.act({"step": 400}) == HANDOVER


def test_passes_rather_than_improvising_when_the_opening_has_a_gap():
    """A slot the replay did not record is not ours to guess at (#204)."""
    assert _book([None, A1, None, A2]).act({"step": 1}) == PASS


def test_counts_its_own_turns_when_the_observation_carries_no_step():
    """Player 1's stored observation has no `step`; the counter stands in."""
    book = _book([None, A1, A2])
    assert book.act({}) == A1
    assert book.act({}) == A2


def test_reset_rewinds_the_book_and_resets_the_handover_agent():
    """Reused across seeds otherwise, the turn counter and the delegate desync."""
    handover = _Recorder()
    book = _book([None, A1, A2], handover=handover)
    book.act({})
    book.reset()
    assert book.act({}) == A1
    assert handover.resets == 1


def test_reset_survives_a_handover_agent_with_no_reset_hook():
    """`Strategy.reset` is optional; a plain callable delegate must not crash."""
    book = OpeningBookStrategy(script=[None, A1], handover=object(),
                               opening_turns=1)
    book.reset()
    assert book.act({"step": 0}) == A1


def test_defaults_to_dense_farm_because_neuropilot_abandons_the_herd():
    """The module's standalone default, unchanged. #207's own hand-over target
    is the champion and the bench overrides it (`opening_bench.contender`);
    what this pins is that a bookless default never lands on `neuropilot`,
    whose genome rounds the herd target to zero animals (#187)."""
    from strategies.dense_farm import DenseFarmStrategy
    assert isinstance(OpeningBookStrategy(script=[None, A1]).handover,
                      DenseFarmStrategy)


def test_from_replay_scripts_the_named_seat_not_the_other_one():
    """Reading the wrong seat books our own opening, which is the null result."""
    steps = [[{"action": a0}, {"action": a1}]
             for a0, a1 in zip([None, A1], [None, A2])]
    replay = {"steps": steps}
    assert OpeningBookStrategy.from_replay(replay, 1).act({"step": 0}) == A2
    assert OpeningBookStrategy.from_replay(replay, 0).act({"step": 0}) == A1


def test_shift_script_moves_every_action_one_index_later():
    """The control's negative arm: the exact #157 off-by-one, on purpose."""
    assert shift_script([None, A1, A2]) == [None, None, A1, A2]


def test_shift_script_moves_every_action_by_an_arbitrary_number_of_indices():
    """Pins the `by` parameter the re-declared negative arm now rests on: the
    bench shifts by `NEGATIVE_SHIFT` = 6, not by the one that voided run 1."""
    from harness.opening_bench import NEGATIVE_SHIFT
    assert shift_script([A1, A2], NEGATIVE_SHIFT) == [None] * 6 + [A1, A2]


def test_shift_script_leaves_the_original_untouched():
    """The shifted arm must not corrupt the book the positive arm replays."""
    script = [None, A1, A2]
    shift_script(script)
    assert script == [None, A1, A2]


def test_a_shifted_book_plays_a_different_opening_than_the_real_one():
    """Precondition for the negative arm: it has to actually diverge."""
    script = [None, A1, A2]
    assert _book(shift_script(script)).act({"step": 0}) != _book(script).act({"step": 0})


def test_opening_book_is_not_in_the_strategy_registry():
    """Like `ghost`, it has no behaviour without a replay: a bookless one is
    just `dense_farm` wearing another name, and registering it would enter a
    duplicate in the tournament and in tests/test_no_crash.py's floor."""
    assert "opening_book" not in REGISTRY


def test_opening_book_is_not_flagged_a_benchmark():
    """It is a contender, not a sparring partner: it is what #207 would promote."""
    assert OpeningBookStrategy.benchmark is False
