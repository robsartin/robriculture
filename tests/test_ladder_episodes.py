"""The ladder-episode readings (#266): the record, opponents and reward bands
off the episode listing, and the both-sides reading off a replay's steps.
Fixtures are the API's own shapes; no network, no replay files."""

from __future__ import annotations

from harness import ladder_episodes as le

ME = 56153224


def _ep(eid, agents, etype="EPISODE_TYPE_PUBLIC", state="COMPLETED"):
    return {"id": eid, "createTime": "2026-09-12T13:50:35.378Z", "endTime": "2026-09-12T13:56:43.026Z",
            "state": state, "type": etype, "agents": agents}


def _ag(sub, reward, team, team_id=1):
    return {"submissionId": sub, "reward": reward, "teamName": team, "teamId": team_id}


EPISODES = [
    _ep(1, [_ag(ME, 96400, "Rob Sartin", 9), _ag(777, 56060, "Women or something", 1)]),
    _ep(2, [_ag(778, 154838, "Sergey Kutepov", 2), _ag(ME, 71174, "Rob Sartin", 9)]),
    _ep(3, [_ag(ME, 5000, "Rob Sartin", 9), _ag(777, 5000, "Women or something", 1)]),
    _ep(4, [_ag(ME, 96400, "Rob Sartin", 9), _ag(ME, 96400, "Rob Sartin", 9)], etype="EPISODE_TYPE_VALIDATION"),
    _ep(5, [_ag(779, None, "Pending", 3), _ag(ME, None, "Rob Sartin", 9)], state="RUNNING"),
    _ep(6, [_ag(778, 20000, "Sergey Kutepov", 2), _ag(ME, 38797, "Rob Sartin", 9)]),
]


def test_episode_rows_skip_self_matches_and_unfinished_games_and_keep_the_seat():
    rows = le.episode_rows(EPISODES, ME)
    assert [r["episode"] for r in rows] == [1, 2, 3, 6]
    assert rows[0] == {"episode": 1, "seat": 0, "ours": 96400, "theirs": 56060, "margin": 40340,
                       "opponent": "Women or something", "team_id": 1, "outcome": "W"}
    assert rows[1]["seat"] == 1 and rows[1]["outcome"] == "L" and rows[1]["margin"] == -83664
    assert rows[2]["outcome"] == "T"


def test_record_counts_wins_losses_ties_and_reward_stats():
    rows = le.episode_rows(EPISODES, ME)
    rec = le.record(rows)
    assert (rec["wins"], rec["losses"], rec["ties"], rec["games"]) == (2, 1, 1, 4)
    assert rec["win_rate"] == 0.5
    assert (rec["reward_min"], rec["reward_median"], rec["reward_max"]) == (5000, 54985.5, 96400)
    assert rec["median_margin"] == 9398.5  # margins 40340, -83664, 0, 18797 -> sorted -83664,0,18797,40340 -> (0+18797)/2


def test_by_opponent_groups_and_orders_by_games_then_name():
    rows = le.episode_rows(EPISODES, ME)
    groups = le.by_opponent(rows)
    assert groups[0] == {"opponent": "Sergey Kutepov", "team_id": 2, "games": 2, "wins": 1, "losses": 1, "ties": 0}
    assert groups[1] == {"opponent": "Women or something", "team_id": 1, "games": 2, "wins": 1, "losses": 0, "ties": 1}


def test_by_reward_band_is_10k_wide_from_zero_with_win_rate():
    rows = le.episode_rows(EPISODES, ME)
    bands = le.by_reward_band(rows)
    assert bands[0] == {"band": "0-10K", "games": 1, "wins": 0, "win_rate": 0.0}
    assert bands[1] == {"band": "30-40K", "games": 1, "wins": 1, "win_rate": 1.0}
    assert bands[2] == {"band": "70-80K", "games": 1, "wins": 0, "win_rate": 0.0}
    assert bands[3] == {"band": "90-100K", "games": 1, "wins": 1, "win_rate": 1.0}


def test_losses_and_matched_wins():
    rows = le.episode_rows(EPISODES, ME)
    assert [r["episode"] for r in le.losses(rows)] == [2]
    # matched wins: the n wins closest to the losses' median own-reward (71174) -> |96400-71174|=25226 < |38797-71174|=32377, so episode 1 is closer
    assert [r["episode"] for r in le.matched_wins(rows, 1)] == [1]
    assert [r["episode"] for r in le.matched_wins(rows, 5)] == [1, 6]


def test_replay_path():
    assert le.replay_path("replays", 108090526) == "replays/episode-108090526-replay.json"


def _tile(kind=None, crop=None, animal=None):
    t = {}
    if kind: t["kind"] = kind
    if crop: t["crop"] = crop
    if animal: t["animal"] = animal
    return t


def test_side_reading_reads_day_boards_and_the_decomposition(monkeypatch):
    boards = {8: {"tiles": [[_tile("PLANT", "MELON"), _tile(animal="COW")]]},
              16: {"tiles": [[_tile("PLANT", "MELON"), _tile("PLANT", "STRAWBERRY"), _tile(animal="COW"), _tile(animal="SHEEP")]]}}
    monkeypatch.setattr(le, "board_on_day", lambda steps, seat, day: boards.get(day))
    monkeypatch.setattr(le, "hands_on_day", lambda steps, seat, day: {8: 6, 16: 9}[day])
    monkeypatch.setattr(le, "decompose", lambda steps, seat: {
        "revenue": {"MELON": 30000, "MILK": 5000}, "spend": {"seed": 800, "hire": 4000, "land": 1000, "animal": 1900, "product": 600},
        "actions": {"WATER": 100}, "final_money": 40000.0, "residual": -12.0})
    r = le.side_reading("steps", 1)
    assert r["day8"] == {"planted": 1, "animals": 1, "cows": 1, "sheep": 0, "hands": 6}
    assert r["day16"] == {"planted": 2, "animals": 2, "cows": 1, "sheep": 1, "hands": 9}
    assert r["revenue"] == {"MELON": 30000, "MILK": 5000} and r["revenue_total"] == 35000
    assert r["spend"]["hire"] == 4000 and r["spend_total"] == 8300
    assert r["final_money"] == 40000.0 and r["residual"] == -12.0


def test_episode_reading_puts_us_in_ours_by_seat(monkeypatch):
    monkeypatch.setattr(le, "side_reading", lambda steps, seat: {"seat": seat})
    row = {"episode": 2, "seat": 1, "ours": 71174, "theirs": 154838, "margin": -83664,
           "opponent": "Sergey Kutepov", "team_id": 2, "outcome": "L"}
    r = le.episode_reading("steps", row)
    assert r["ours"] == {"seat": 1} and r["theirs"] == {"seat": 0} and r["row"] is row


def test_summarise_takes_medians_over_readings():
    readings = [
        {"row": {"outcome": "L"}, "ours": {"day8": {"planted": 20, "animals": 4, "hands": 6}, "day16": {"planted": 30, "animals": 8, "hands": 9},
                                          "revenue": {"MELON": 10000}, "revenue_total": 10000, "spend": {"hire": 3000}, "spend_total": 3000, "final_money": 30000, "residual": 0},
         "theirs": {"day8": {"planted": 10, "animals": 8, "hands": 5}, "day16": {"planted": 12, "animals": 12, "hands": 8},
                    "revenue": {"MILK": 40000}, "revenue_total": 40000, "spend": {"animal": 9000}, "spend_total": 9000, "final_money": 90000, "residual": 500}},
        {"row": {"outcome": "L"}, "ours": {"day8": {"planted": 22, "animals": 4, "hands": 6}, "day16": {"planted": 34, "animals": 10, "hands": 10},
                                          "revenue": {"MELON": 14000}, "revenue_total": 14000, "spend": {"hire": 3200}, "spend_total": 3200, "final_money": 34000, "residual": 0},
         "theirs": {"day8": {"planted": 12, "animals": 10, "hands": 5}, "day16": {"planted": 14, "animals": 14, "hands": 8},
                    "revenue": {"MILK": 50000}, "revenue_total": 50000, "spend": {"animal": 11000}, "spend_total": 11000, "final_money": 100000, "residual": 700}},
    ]
    s = le.summarise(readings)
    assert s["games"] == 2
    assert s["ours"]["day8"] == {"planted": 21, "animals": 4, "hands": 6}  # medians over the keys present
    assert s["theirs"]["day16"] == {"planted": 13, "animals": 13, "hands": 8}
    assert s["ours"]["revenue_total"] == 12000 and s["theirs"]["revenue_total"] == 45000
    assert s["theirs"]["revenue"] == {"MILK": 45000} and s["ours"]["spend"] == {"hire": 3100}
    assert s["theirs"]["residual"] == 600


def test_formatters_render_tables():
    rows = le.episode_rows(EPISODES, ME)
    out = le.format_record(le.record(rows))
    assert "21W" not in out and "2W 1L 1T" in out and "0.500" in out
    assert "Sergey Kutepov" in le.format_opponents(le.by_opponent(rows))
    assert "90-100K" in le.format_bands(le.by_reward_band(rows))


def test_episode_rows_skips_a_finished_game_that_does_not_contain_the_submission():
    stranger = _ep(9, [_ag(701, 1000, "A", 1), _ag(702, 2000, "B", 2)])
    assert le.episode_rows([stranger], ME) == []


def test_summarise_and_formatters_survive_no_games():
    s = le.summarise([])
    assert s["games"] == 0 and s["ours"] is None and s["theirs"] is None
    assert "n=0" in le.format_readings("losses", s)
    assert le.format_opponents([]).count("\n") == 1 and le.format_bands([]).count("\n") == 1


def test_side_reading_splits_the_herd_by_kind(monkeypatch):
    boards = {8: {"tiles": [[_tile(animal="COW"), _tile(animal="SHEEP"), _tile(animal="SHEEP")]]},
              16: {"tiles": [[_tile(animal="GOOSE")]]}}
    monkeypatch.setattr(le, "board_on_day", lambda steps, seat, day: boards.get(day))
    monkeypatch.setattr(le, "hands_on_day", lambda steps, seat, day: 5)
    monkeypatch.setattr(le, "decompose", lambda steps, seat: {"revenue": {}, "spend": {}, "actions": {}, "final_money": 0.0, "residual": 0.0})
    r = le.side_reading("steps", 0)
    assert r["day8"] == {"planted": 0, "animals": 3, "cows": 1, "sheep": 2, "hands": 5}
    assert r["day16"] == {"planted": 0, "animals": 1, "cows": 0, "sheep": 0, "hands": 5}
