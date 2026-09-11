"""The #199 stage-1 gate's declared constants and pure parts. The games are
the bench's; here the verdict, the limbs and control 2 on stubbed inputs."""

from __future__ import annotations

import dataclasses
import json

from harness import predator_bench as pb
from strategies import predator as pr


def test_the_declared_constants():
    assert pb.CHAMPION == "lean_feed" and pb.REFERENCE == "field_rival"
    assert pb.GENOME.endswith("harness/genomes/199-predator.json")
    assert pb.SEEDS == tuple(range(976, 992)) and pb.CONTROL_SEED == 976 and pb.WIN_BAR == 8
    assert (pb.PROFILE_DAY, pb.RECORD_DAY) == (16, 8)
    assert pb.PROFILE_BOUNDS == {"planted": (14, 40), "animals": (5, 15), "hands": (5, 10)}


def test_the_seeds_are_fresh_against_every_range_already_spent():
    spent = set(range(100, 116)) | set(range(200, 216)) | set(range(300, 332)) \
        | set(range(400, 416)) | set(range(500, 516)) | set(range(600, 616)) \
        | set(range(700, 704)) | set(range(800, 960)) | set(range(960, 976))
    assert not spent & set(pb.SEEDS)


def _checkpoint(genome, fitness, ref_fitness):
    return {"genome": genome, "meta": {"fitness": fitness, "reference": {"fitness": ref_fitness},
                                       "seeds": [13900, 13901, 13902, 13903]}}


def test_search_moved_needs_a_better_fitness_and_a_changed_schedule():
    mutant = pr.encode(dataclasses.replace(pr.Schedule.frozen(), pivot=7))
    assert pb.search_moved(_checkpoint(mutant, 0.6, 0.4)) == {
        "ok": True, "best": 0.6, "reference": 0.4, "changed": ["pivot"]}
    assert pb.search_moved(_checkpoint(mutant, 0.4, 0.4))["ok"] is False   # not strictly better
    assert pb.search_moved(_checkpoint(list(pr.FROZEN), 0.6, 0.4))["ok"] is False  # frozen itself


def test_load_checkpoint_reads_the_genome_and_meta(tmp_path):
    p = tmp_path / "ck.json"
    p.write_text(json.dumps(_checkpoint(list(pr.FROZEN), 0.5, 0.5)))
    ck = pb.load_checkpoint(str(p))
    assert ck["genome"] == list(pr.FROZEN) and ck["meta"]["fitness"] == 0.5


def _game(seed, seat, pred, champ, done=True):
    return {"seed": seed, "seat": seat, "rewards": (pred, champ), "done": done, "steps": None}


def test_record_counts_wins_and_ties_never_ties_as_wins():
    games = [_game(1, 0, 10, 5), _game(2, 1, 5, 5), _game(3, 0, 1, 9)]
    assert pb.record(games) == {"wins": 1, "ties": 1, "games": 3}


def test_strict_parity_needs_every_game_done_with_identical_rewards():
    a = [_game(1, 0, 10, 5), _game(2, 1, 4, 8)]
    assert pb.strict_parity(a, [_game(1, 0, 10, 5), _game(2, 1, 4, 8)]) == {"ok": True, "reason": None}
    r = pb.strict_parity(a, [_game(1, 0, 10, 5), _game(2, 1, 4, 9)])
    assert r["ok"] is False and "seed 2" in r["reason"]
    r = pb.strict_parity([_game(1, 0, 10, 5, done=False)], [_game(1, 0, 10, 5)])
    assert r["ok"] is False and "seed 1" in r["reason"]


def test_profile_failures_name_the_bounds_that_did_not_hold():
    assert pb.profile_failures({"planted": 27, "animals": 10, "hands": 10}) == []
    assert pb.profile_failures({"planted": 13, "animals": 10, "hands": 10}) == ["planted"]
    assert pb.profile_failures({"planted": 40, "animals": 16, "hands": 4}) == ["animals", "hands"]


def test_profile_is_the_median_over_games_of_the_day_boards(monkeypatch):
    boards = {(1, 16): {"tiles": "b1"}, (2, 16): {"tiles": "b2"}, (3, 16): {"tiles": "b3"}}
    monkeypatch.setattr(pb, "board_on_day", lambda steps, seat, day: boards[(steps, day)])
    monkeypatch.setattr(pb, "hands_on_day", lambda steps, seat, day: {1: 8, 2: 9, 3: 10}[steps])
    monkeypatch.setattr(pb, "planted_by_crop", lambda tiles: {"b1": {"MELON": 20}, "b2": {"MELON": 30, "WHEAT": 1},
                                                              "b3": {"STRAWBERRY": 27}}[tiles])
    monkeypatch.setattr(pb, "animals_placed", lambda tiles: {"b1": {"COW": 5}, "b2": {"COW": 7, "SHEEP": 3},
                                                             "b3": {"SHEEP": 9}}[tiles])
    games = [{"seed": s, "seat": 0, "rewards": (1, 0), "done": True, "steps": s} for s in (1, 2, 3)]
    assert pb.profile(games, "predator", day=16) == {"planted": 27, "animals": 9, "hands": 9}


def test_verdict_pass_reject_degenerate():
    assert pb.verdict(8, True, []) == ("PASS", 0)
    assert pb.verdict(7, True, []) == ("REJECT", 1)
    assert pb.verdict(9, False, []) == ("DEGENERATE: strict parity", 1)
    assert pb.verdict(9, True, ["hands"]) == ("DEGENERATE: profile hands", 1)
    assert pb.verdict(7, False, ["hands"]) == ("REJECT", 1)
