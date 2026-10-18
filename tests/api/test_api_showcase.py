import json

import pytest

from apifakes import SHOWCASE_ROOT, demo_match
from jahbadh.agents.contracts import Claim, DeskRun, FeedItem, Moment
from jahbadh.api.showcase import ShowcaseError, load_showcase, load_showcases

NOTE = {"seed": 42, "demo_storyline": True, "note": "Real output of python -m jahbadh.agents. Never edited by hand."}


def folder(tmp_path, items=(), match_id="match-042"):
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "showcase.json").write_text(json.dumps(NOTE), encoding="utf-8")
    run = DeskRun(match_id=match_id, model="gpt-5-mini", created="2026-10-18T00:00:00Z", items=list(items), failures=[])
    (tmp_path / "desk.json").write_text(run.model_dump_json(), encoding="utf-8")
    return tmp_path


def item(event_ids, t=900.0):
    moment = Moment(id="goal-885", kind="goal", t=t, label="Goal")
    claim = Claim(id="goal-885:c1", text="A goal.", metric_ids=[], event_ids=event_ids, figures=[])
    return FeedItem(moment=moment, claims=[claim], renders=[], rejections=[], metrics=[], stats={}, latency_s=0.0)


def test_a_showcase_rebuilds_its_match_from_the_seed(tmp_path):
    show = load_showcase(folder(tmp_path, [item([213])]))
    assert show.seed == 42 and show.match.meta.match_id == "match-042" and len(show.desk.items) == 1
    assert [e.model_dump() for e in show.match.events[:50]] == [e.model_dump() for e in demo_match().events[:50]]


def test_a_desk_for_another_match_is_refused(tmp_path):
    with pytest.raises(ShowcaseError, match="match-007"):
        load_showcase(folder(tmp_path, match_id="match-007"))


def test_a_claim_citing_a_missing_event_is_refused(tmp_path):
    with pytest.raises(ShowcaseError, match="99999"):
        load_showcase(folder(tmp_path, [item([213, 99999])]))


def test_a_moment_outside_the_match_is_refused(tmp_path):
    with pytest.raises(ShowcaseError, match="6000"):
        load_showcase(folder(tmp_path, [item([213], t=6000.0)]))


def test_no_showcase_folder_means_no_showcases(tmp_path):
    assert load_showcases(tmp_path / "nope") == {}


def test_load_showcases_keys_by_match_and_skips_half_folders(tmp_path):
    folder(tmp_path / "match-042")
    (tmp_path / "half").mkdir()
    (tmp_path / "half" / "showcase.json").write_text(json.dumps(NOTE), encoding="utf-8")
    assert list(load_showcases(tmp_path)) == ["match-042"]


def test_the_committed_showcase_loads_with_every_combo():
    show = load_showcases(SHOWCASE_ROOT)["match-042"]
    assert show.desk.items[-1].moment.kind == "full_time"
    assert {i.moment.id for i in show.desk.items} >= {"team_recap-NBR", "team_recap-RMU"}
    for item in show.desk.items:
        for c in item.claims:
            combos = {(r.persona, r.language) for r in item.renders if r.claim_id == c.id}
            assert len(combos) == 9
        assert not any("\u2014" in r.text or "\u2013" in r.text for r in item.renders)
