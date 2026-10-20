import pytest
from fastapi.testclient import TestClient

from apifakes import api_settings, demo_match, recording_sleep
from jahbadh.api.app import create_app
from jahbadh.api.personal import PlayerRow, player_table

DEMO = demo_match()
SUB_ON = next(e.related_player_id for e in DEMO.events if e.type == "SUBSTITUTION")


def row(rows: list[PlayerRow], player_id: str) -> PlayerRow:
    return next(r for r in rows if r.player_id == player_id)


def test_the_table_counts_only_what_happened_by_t():
    assert row(player_table(DEMO, 880), "NBR-72").goals == 0          # Kian Jansen scores at 885 s
    assert row(player_table(DEMO, 900), "NBR-72").goals == 1
    rasmus = row(player_table(DEMO, 5400), "RMU-33")
    assert (rasmus.goals, rasmus.shots, round(rasmus.xgi, 2)) == (5, 10, 3.62)   # the showcase's own line


def test_cards_are_counted_by_t():
    assert row(player_table(DEMO, 20), "RMU-96").yellow_cards == 0     # Tomas Lindqvist is booked at 25 s
    lindqvist = row(player_table(DEMO, 60), "RMU-96")
    assert (lindqvist.yellow_cards, lindqvist.red_cards) == (1, 0)


def test_subs_who_have_not_come_on_are_left_out():
    assert SUB_ON not in {r.player_id for r in player_table(DEMO, 3000)}
    assert SUB_ON in {r.player_id for r in player_table(DEMO, 4000)}


def test_the_table_is_sorted_by_expected_goal_involvement():
    rows = player_table(DEMO, 5400)
    assert [(r.xgi, r.name) for r in rows] == sorted(((r.xgi, r.name) for r in rows), key=lambda x: (-x[0], x[1]))
    assert rows[0].player_id == "RMU-33"


def test_rows_carry_who_the_player_is_and_their_pass_speed():
    r = row(player_table(DEMO, 5400), "NBR-72")
    assert r.name == "Kian Jansen" and r.team_id == "NBR" and r.shirt > 0 and r.minutes > 0
    assert 20 <= r.pass_speed_avg <= r.pass_speed_max <= 100


def test_bad_t_is_refused():
    with pytest.raises(ValueError):
        player_table(DEMO, 5401)


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    with TestClient(create_app(api_settings(tmp_path_factory.mktemp("state")), sleep=recording_sleep()[0])) as c:
        yield c


def test_replay_players_route(client):
    rows = client.get("/api/replay/match-042/players?t=900").json()
    assert row([PlayerRow(**r) for r in rows], "NBR-72").goals == 1
    assert rows == [r.model_dump(mode="json") for r in player_table(client.app.state.showcases["match-042"].match, 900)]


def test_unknown_match_is_404_and_bad_t_is_422(client):
    assert client.get("/api/replay/match-999/players?t=900").status_code == 404
    assert client.get("/api/replay/match-042/players?t=5401").status_code == 422
    assert client.get("/api/replay/match-042/players").status_code == 422
