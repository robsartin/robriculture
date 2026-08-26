"""Multi-seed experiment evaluation (#71)."""
from __future__ import annotations

from harness import multi_seed as ms


def _row(seed=0, share=0.4, plants_peak=20, land_purchases=(("NE", 12, 5000),)):
    # share=0.4 is deliberately above PROMOTION_BAR (0.3760) so tests that
    # don't mention share still isolate the land/plants clause they name.
    return {"seed": seed, "share": share, "plants_peak": plants_peak,
            "land_purchases": list(land_purchases), "animals_peak": 0,
            "hands_peak": 9, "reward": 25000.0}


def test_seed_verdict_true_when_land_bought_and_enough_tiles_planted():
    assert ms.seed_verdict(_row()) is True


def test_seed_verdict_false_when_no_land_was_bought():
    # #113's outcome: the genome farmed fine but never expanded.
    assert ms.seed_verdict(_row(land_purchases=())) is False


def test_seed_verdict_false_when_planted_tiles_stay_under_the_bar():
    # 11 is the ceiling every agent we own already hits, so it proves nothing.
    assert ms.seed_verdict(_row(plants_peak=11)) is False


def test_seed_verdict_true_exactly_at_the_bar():
    assert ms.seed_verdict(_row(plants_peak=ms.MIN_PLANTS_PEAK)) is True


def test_seed_verdict_false_when_share_stays_below_promotion_bar():
    # This is the exact case the branch's own smoke run produced: land
    # bought, plants_peak well past MIN_PLANTS_PEAK (21 and 62 tiles), but
    # share (0.1850 and 0.3134) below PROMOTION_BAR (0.3760). The old
    # two-clause verdict would have called both of those seeds a success;
    # planting broadly is not the same as scoring well.
    assert ms.seed_verdict(_row(share=0.10)) is False


def test_summarize_seeds_reports_the_success_rate():
    rows = [_row(seed=0), _row(seed=1, land_purchases=()), _row(seed=2)]
    got = ms.summarize_seeds(rows)
    assert got["n"] == 3
    assert got["n_supported"] == 2
    assert got["rate"] == 2 / 3


def test_summarize_seeds_reports_share_spread():
    rows = [_row(seed=0, share=0.30), _row(seed=1, share=0.50)]
    got = ms.summarize_seeds(rows)
    assert got["share_mean"] == 0.40
    assert got["share_max"] == 0.50
    assert got["share_min"] == 0.30


def test_summarize_seeds_reports_the_best_planted_count():
    rows = [_row(seed=0, plants_peak=12), _row(seed=1, plants_peak=31)]
    assert ms.summarize_seeds(rows)["plants_peak_max"] == 31


def test_summarize_seeds_handles_no_rows():
    # A run where every seed crashed must report emptiness, not divide by zero.
    got = ms.summarize_seeds([])
    assert got["n"] == 0 and got["rate"] == 0.0


# --- #130: a stopped long run must not lose everything ---

def test_checkpoint_path_is_per_seed_and_derived_from_out():
    # Each seed writes its own partial so a stopped run leaves usable work for
    # every lane, not one file the lanes overwrite each other in.
    got = ms.checkpoint_path("harness/genomes/run.json", 3)
    assert got == "harness/genomes/run-seed3.partial.json"


def test_checkpoint_path_handles_an_out_with_no_extension():
    # --out is user-supplied; a bare name must still produce a .json partial
    # rather than a path with no extension that nothing will parse.
    assert ms.checkpoint_path("run", 0) == "run-seed0.partial.json"


def test_checkpoint_paths_differ_per_seed():
    # The bug this guards: one shared path means ten lanes clobber each other
    # and a stopped run leaves a single arbitrary genome.
    paths = {ms.checkpoint_path("out.json", s) for s in range(10)}
    assert len(paths) == 10


def test_write_checkpoint_records_progress_and_is_reloadable(tmp_path):
    # A partial is only worth writing if it can be read back and benchmarked.
    # Pins the shape a salvage step depends on: the genome, which generation
    # it came from, and the anchor share so partials can be ranked without
    # re-running anything.
    path = str(tmp_path / "r.json")
    ms.write_checkpoint(path, seed=2, genome=[0.5, 0.25], fitness=0.4242,
                        history=[{"gen": 0}, {"gen": 1}])
    import json
    back = json.load(open(path))
    assert back["genome"] == [0.5, 0.25]
    assert back["meta"]["seed"] == 2
    assert back["meta"]["generations_done"] == 2
    assert back["meta"]["anchor_share"] == 0.4242


def test_write_checkpoint_overwrites_rather_than_appending(tmp_path):
    # Called every generation, so it must leave one current file, not grow
    # without bound over a 25-generation run.
    path = str(tmp_path / "r.json")
    ms.write_checkpoint(path, seed=0, genome=[1.0], fitness=0.1, history=[{"gen": 0}])
    ms.write_checkpoint(path, seed=0, genome=[2.0], fitness=0.2,
                        history=[{"gen": 0}, {"gen": 1}])
    import json
    back = json.load(open(path))
    assert back["genome"] == [2.0] and back["meta"]["generations_done"] == 2
