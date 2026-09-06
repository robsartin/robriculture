"""The #219 experiment's counting and verdict logic, pinned before any number."""

from __future__ import annotations

from harness import rival_bench as rb


def test_the_declared_constants():
    assert rb.CHAMPION == "dense_farm" and rb.CONTENDER == "rival_aware"
    assert rb.SEEDS == tuple(range(400, 416))
    assert rb.CHAMPION_BAR == 0.60 and rb.ANCHOR_BAR == 0.90


def test_animal_buys_counts_kinds_across_turns():
    actions = [{"market": [["BUY_ANIMAL", "COW", 1], ["SELL", "WOOL", 3]]},
               {"market": [["BUY_ANIMAL", "SHEEP", 1], ["BUY_ANIMAL", "COW", 1]]},
               {"market": []}]
    assert rb.animal_buys(actions) == {"COW": 2, "SHEEP": 1}


def test_mechanism_fired_needs_more_cows_and_fewer_sheep():
    assert rb.mechanism_fired({"COW": 6, "SHEEP": 2}, {"COW": 3, "SHEEP": 5}) is True
    assert rb.mechanism_fired({"COW": 6, "SHEEP": 5}, {"COW": 3, "SHEEP": 5}) is False
    assert rb.mechanism_fired({"COW": 3, "SHEEP": 2}, {"COW": 3, "SHEEP": 5}) is False


def _row(name, wins, games=16):
    return {"name": "rival_aware", "opponent": name, "wins": wins, "ties": 0, "games": games,
            "seeds": "400-415"}


def test_rate_is_zero_on_zero_games_rather_than_dividing_by_it():
    # Whole-branch review minor: a row with games=0 (never expected from a real
    # run, but format_rows/criterion should not blow up on one) must not raise.
    assert rb._rate({"wins": 0, "games": 0}) == 0.0
    assert rb._rate({"wins": 3, "games": 6}) == 0.5


def test_criterion_passes_only_at_both_bars():
    anchors = [_row(n, 15) for n in ("meta_bot", "ranch_hands", "market_farmer",
                                     "ranch_adaptive", "wheat_hands", "field_rival")]
    ok = rb.criterion(_row("dense_farm", 10), anchors)           # 62.5% and 93.75%
    assert ok["passed"] is True and ok["failing"] == []
    champ_short = rb.criterion(_row("dense_farm", 9), anchors)   # 56.25% < 60%
    assert champ_short["passed"] is False and champ_short["failing"] == ["dense_farm"]
    anchors[0] = _row("meta_bot", 14)                            # 87.5% < 90%
    anchor_short = rb.criterion(_row("dense_farm", 10), anchors)
    assert anchor_short["passed"] is False and anchor_short["failing"] == ["meta_bot"]


def test_criterion_counts_a_tie_as_not_a_win():
    tied = dict(_row("dense_farm", 9), ties=7)
    assert rb.criterion(tied, [_row("meta_bot", 16)])["champion_rate"] == 9 / 16


def test_format_rows_one_line_per_opponent_with_rate():
    text = rb.format_rows([_row("dense_farm", 10), _row("meta_bot", 15)])
    lines = [ln for ln in text.splitlines() if ln.strip()]
    assert len(lines) == 3 and "dense_farm" in lines[1] and "10/16" in lines[1]
