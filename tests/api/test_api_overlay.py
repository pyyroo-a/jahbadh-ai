import pytest

from apifakes import demo_match, grounded_claim
from jahbadh.agents.contracts import DeskRun, FeedItem, RenderedClaim
from jahbadh.analytics import rhythm_series
from jahbadh.api.overlay import (DURATION_S, FAST_SHOT_KMH, RHYTHM_HOLD_MIN, OverlayCue, claim_cues, event_cues,
                                 metric_cues, overlay_cues)
from jahbadh.schemas import EventType

LANGS = {"en", "ar", "es"}


def published():
    run, claim = grounded_claim()
    renders = [RenderedClaim(claim_id=claim.id, persona="pundit", language=lang, text=f"[{lang}] {claim.text}")
               for lang in ("en", "ar", "es")]
    item = FeedItem(moment=run.moment, claims=[claim], renders=renders, rejections=[], metrics=run.store.metrics(),
                    stats={}, latency_s=0.0)
    return item, claim


def test_cues_are_timed_sorted_and_complete():
    cues = overlay_cues(demo_match(), None)
    assert [c.match_time for c in cues] == sorted(c.match_time for c in cues)
    assert len({c.id for c in cues}) == len(cues)
    for c in cues:
        assert set(c.text) == LANGS and all(c.text.values()) and c.duration_s == DURATION_S[c.type]
        assert c.minute == min(90, int(c.match_time // 60) + 1) and c.precomputed
        assert not any(ch in t for t in c.text.values() for ch in ("—", "–", "{"))


def test_every_goal_gets_a_cue_and_points_at_its_events():
    m = demo_match()
    goals = [e for e in m.events if e.type == EventType.GOAL]
    cues = [c for c in event_cues(m) if c.type == "goal"]
    assert len(cues) == len(goals) == 8
    first = cues[0]
    assert first.text["en"] == "GOAL · Kian Jansen (Northbridge FC)" and first.match_time == goals[0].t
    assert first.event_ids == [212, 213] and first.team_id == "NBR" and first.source == "event"


def test_storyline_cues_read_the_events():
    texts = {c.type: c.text["en"] for c in event_cues(demo_match())}
    assert texts["formation_change"] == "Rivermouth United switch to 3-4-3"
    assert texts["substitution"] == "Substitution · Hugo Ruiz on, Zane Brennan off"
    assert texts["tactic_change"] == "Northbridge FC press higher"


def test_fast_shot_cues_are_marked_synthetic():
    shots = [c for c in event_cues(demo_match()) if c.type == "shot"]
    assert shots and all(c.synthetic and c.unit == "km/h" and c.value >= FAST_SHOT_KMH for c in shots)
    assert "km/h" in shots[0].text["en"]


def test_metric_cues_cover_alerts_and_settled_rhythm():
    m = demo_match()
    cues = metric_cues(m)
    sprints = [c for c in cues if c.type == "sprint_record"]
    assert sprints and all(c.synthetic and c.unit == "km/h" and c.text["en"].startswith("Top speed · ") for c in sprints)
    rhythm = [c for c in cues if c.type == "rhythm"]
    labels = {(int(s.window[1]), s.data["label"]) for s in rhythm_series(m)}
    for c in rhythm:                                   # announced only after holding RHYTHM_HOLD_MIN minutes
        label = c.text["en"].removeprefix("Game rhythm: ")
        assert all((int(c.match_time) - 60 * k, label) in labels for k in range(RHYTHM_HOLD_MIN))
    said = [c.text["en"] for c in rhythm]
    assert rhythm and all(a != b for a, b in zip(said, said[1:])) and len(rhythm) < 13    # 13 raw flips on the demo


def test_claim_cues_reuse_the_approved_renders():
    item, claim = published()
    [cue] = claim_cues(item, at=5420.0)
    assert cue.type == "claim" and cue.source == "claim" and cue.match_time == 5420.0
    assert cue.text == {lang: f"[{lang}] {claim.text}" for lang in LANGS}
    assert cue.metric_ids == claim.metric_ids and cue.event_ids == claim.event_ids


def test_a_missing_language_falls_back_to_english():
    item, claim = published()
    item = item.model_copy(update={"renders": [r for r in item.renders if r.language != "ar"]})
    assert claim_cues(item, at=10.0, precomputed=False)[0].text["ar"] == f"[en] {claim.text}"


def test_overlay_puts_claim_cues_after_their_moment():
    item, _ = published()
    run = DeskRun(match_id="match-042", model="x", created="now", items=[item], failures=[])
    cues = overlay_cues(demo_match(), run, lag_s=20.0)
    claims = [c for c in cues if c.type == "claim"]
    assert len(claims) == 1 and claims[0].match_time == item.moment.t + 20.0


def test_no_cue_comes_from_the_future():
    m = demo_match()
    for c in event_cues(m) + metric_cues(m):
        assert all(m.event(i).t <= c.match_time for i in c.event_ids)


def test_cue_schema_is_machine_readable():
    props = OverlayCue.model_json_schema()["properties"]
    assert {"match_time", "type", "team_id", "player_id", "value", "text", "duration_s"} <= set(props)


def test_running_cues_carry_the_players_club():
    m = demo_match()
    team_of = {p.id: t.id for t in (m.meta.home, m.meta.away) for p in t.players}
    alerts = [c for c in metric_cues(m) if c.type in ("sprint_record", "distance_milestone")]
    assert alerts and all(c.team_id == team_of[c.player_id] for c in alerts)
