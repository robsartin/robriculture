"""Unit tests for scripts/survey_dedup.py (#296).

The recurring #67 re-survey deduped candidates against a hardcoded list in its
own instructions rather than against harness/external_agents.json, so it twice
re-proposed agents already in the pool. This module is that dedup source: the
manifest decides what we already have.
"""

from __future__ import annotations

from scripts import survey_dedup as sd


def _entries():
    return [
        {
            "name": "madhur_sabherwal_hub_geometry_agent",
            "source_type": "github_file",
            "repo": "Madhur-Sabherwal/kaggriculture-hub-geometry-agent",
            "path": "src/agent.py",
        },
        {
            "name": "pilkwang_structured_economic_policy",
            "source_type": "kaggle_kernel",
            "kernel_ref": "pilkwang/kaggriculture-structured-economic-policy",
        },
    ]


def test_github_candidate_matching_repo_and_path_is_already_held():
    verdict = sd.classify(
        "Madhur-Sabherwal/kaggriculture-hub-geometry-agent",
        path="src/agent.py",
        entries=_entries(),
    )
    assert verdict.status == "HAVE"
    assert verdict.matched == "madhur_sabherwal_hub_geometry_agent"


def test_kaggle_candidate_matching_kernel_ref_is_already_held():
    verdict = sd.classify(
        "pilkwang/kaggriculture-structured-economic-policy", entries=_entries()
    )
    assert verdict.status == "HAVE"
    assert verdict.matched == "pilkwang_structured_economic_policy"


def test_github_candidate_in_a_held_repo_at_a_new_path_needs_review():
    # #295 settled that a second file from an already-vendored repo is a
    # lineage/rung judgement (which ShashankJangid rungs? which Driw0x agent?),
    # not an automatic add and not an automatic drop.
    verdict = sd.classify(
        "Madhur-Sabherwal/kaggriculture-hub-geometry-agent",
        path="src/agent_v2.py",
        entries=_entries(),
    )
    assert verdict.status == "REVIEW"
    assert verdict.matched == "madhur_sabherwal_hub_geometry_agent"


def test_candidate_absent_from_the_manifest_is_new():
    verdict = sd.classify("adilshamim8/kaggriculture-101", entries=_entries())
    assert verdict.status == "NEW"
    assert verdict.matched is None


def test_repo_case_does_not_hide_a_held_entry():
    # GitHub refs are case-insensitive; a survey that writes the owner or repo
    # with different capitalisation than the manifest would re-propose an agent
    # we already hold -- the #296 failure in a subtler form.
    verdict = sd.classify(
        "madhur-sabherwal/Kaggriculture-Hub-Geometry-Agent",
        path="src/agent.py",
        entries=_entries(),
    )
    assert verdict.status == "HAVE"


# --- the CLI the scheduled task calls ---

def test_main_reports_a_status_per_candidate(capsys):
    code = sd.main(
        [
            "pilkwang/kaggriculture-structured-economic-policy",
            "adilshamim8/kaggriculture-101",
        ]
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "HAVE\tpilkwang/kaggriculture-structured-economic-policy" in out
    assert "NEW\tadilshamim8/kaggriculture-101" in out


def test_main_splits_a_repo_and_path_candidate_on_the_colon(capsys):
    sd.main(["ShashankJangid/kaggriculture-agent:agent_v9.py"])
    assert "HAVE" in capsys.readouterr().out


# --- regression: the duplicates the 2026-09-18 run re-proposed (#296) ---

def test_the_2026_09_18_survey_duplicates_are_caught_against_the_real_manifest():
    held = [
        ("georgymamarin/kaggriculture-visualized-what-every-crop-pays", None),
        ("loubaliber/kaggriculture-loubal", "submission.py"),
    ]
    for ref, path in held:
        assert sd.classify(ref, path=path, entries=sd.load_manifest()).status == "HAVE", ref


def test_a_second_rung_from_a_held_repo_is_flagged_for_review_not_proposed():
    entries = sd.load_manifest()
    rungs = [
        ("ShashankJangid/kaggriculture-agent", "agent_v100_sota.py"),
        ("Driw0x/Kaggriculture", "submissions/agent.py"),
        ("lonespear/kaggriculture", "main_bigherd.py"),
        ("Darunesh1/Kaggriculture", "agent/policy.py"),
    ]
    for ref, path in rungs:
        assert sd.classify(ref, path=path, entries=entries).status == "REVIEW", ref
