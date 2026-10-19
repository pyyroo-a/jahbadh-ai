from collections import Counter

import numpy as np

from evalfakes import demo_match
from jahbadh.agents.contracts import Claim, Figure
from jahbadh.agents.moments import detect_moments
from jahbadh.eval.plant import PLANT_KINDS, plant_claim, schedule_plants
from jahbadh.schemas import EventType

DEMO = demo_match()
SWITCH = next(m for m in detect_moments(DEMO) if m.kind == "formation_change")       # 61', t = 3600


def rng():
    return np.random.default_rng(7)


def draft(text: str, written: str | None = None, cid: str = "c1", event_ids=(1,)) -> Claim:
    figures = [Figure(metric_id="field_tilt:RMU:3000-3601", field="value", written=written)] if written else []
    return Claim(id=f"{SWITCH.id}:{cid}", text=text, metric_ids=["field_tilt:RMU:3000-3601"] if written else [],
                 event_ids=list(event_ids), figures=figures)


def test_a_wrong_number_changes_one_figure_and_its_text():
    cases = [("45%", "60%"), ("0.74", "1.11"), ("3", "5")]
    for written, wrong in cases:
        source = draft(f"Rivermouth United had {written} of the final-third passes after 61'.", written)
        planted = plant_claim("wrong_number", [source], DEMO, SWITCH, rng(), 1)
        assert planted.claim.id == f"{SWITCH.id}:p1" and planted.source_claim_id == source.id
        assert planted.claim.text == source.text.replace(written, wrong)
        assert planted.claim.figures[0].written == wrong and planted.claim.metric_ids == source.metric_ids


def test_a_wrong_player_names_someone_from_the_other_team():
    names = {p.name: t.id for t in (DEMO.meta.home, DEMO.meta.away) for p in t.players}
    source = draft("Omar Rasmus dropped deep to link play after 61'.")
    planted = plant_claim("wrong_player", [source], DEMO, SWITCH, rng(), 1).claim
    assert "Omar Rasmus" not in planted.text
    swapped = next(n for n in names if n in planted.text)
    assert names[swapped] != names["Omar Rasmus"]
    assert planted.event_ids == source.event_ids


def test_a_made_up_event_cites_a_real_pass_but_says_it_hit_the_post():
    planted = plant_claim("made_up_event", [], DEMO, SWITCH, rng(), 2)
    assert planted.source_claim_id is None and planted.claim.id == f"{SWITCH.id}:p2"
    [eid] = planted.claim.event_ids
    event = next(e for e in DEMO.events if e.id == eid)
    assert event.type == EventType.PASS and event.t < SWITCH.horizon
    name = next(p.name for t in (DEMO.meta.home, DEMO.meta.away) for p in t.players if p.id == event.player_id)
    assert planted.claim.text == f"{name} hit the post at {event.minute}'."


def test_a_wrong_team_swaps_the_club():
    source = draft("Rivermouth United pushed their full-backs higher after the switch to 3-4-3.")
    planted = plant_claim("wrong_team", [source], DEMO, SWITCH, rng(), 1).claim
    assert planted.text == "Northbridge FC pushed their full-backs higher after the switch to 3-4-3."
    short = draft("Rivermouth pushed higher after the switch.")
    assert plant_claim("wrong_team", [short], DEMO, SWITCH, rng(), 1).claim.text == "Northbridge pushed higher after the switch."


def test_a_line_naming_both_clubs_is_not_used_for_a_wrong_team():
    both = draft("Rivermouth United pinned Northbridge FC back after 61'.")
    assert plant_claim("wrong_team", [both], DEMO, SWITCH, rng(), 1) is None


def test_a_wrong_minute_moves_twenty_minutes():
    source = draft("Rivermouth United switched to a back three at 61'.")
    assert plant_claim("wrong_minute", [source], DEMO, SWITCH, rng(), 1).claim.text == \
        "Rivermouth United switched to a back three at 81'."
    late = draft("Rivermouth United kept pressing at 85'.")
    assert plant_claim("wrong_minute", [late], DEMO, SWITCH, rng(), 1).claim.text == "Rivermouth United kept pressing at 65'."


def test_no_suitable_draft_means_no_plant():
    plain = draft("Rivermouth kept the ball well.")
    for kind in ("wrong_number", "wrong_player", "wrong_minute"):
        assert plant_claim(kind, [plain], DEMO, SWITCH, rng(), 1) is None
    assert plant_claim("wrong_team", [], DEMO, SWITCH, rng(), 1) is None


def test_plants_are_spread_evenly_across_kinds_and_matches():
    moments = [m for m in detect_moments(DEMO) if m.kind in ("goal", "card", "full_time")]
    sched = schedule_plants({s: moments for s in range(1, 21)}, total=50)
    kinds = Counter(k for per_match in sched.values() for k in per_match.values())
    assert kinds == {k: 10 for k in PLANT_KINDS}
    assert all(len(per_match) in (2, 3) for per_match in sched.values())
    assert all(len(set(per_match.values())) == len(per_match) for per_match in sched.values())   # no kind twice in a match
    assert not any(mid.startswith("full_time") for per_match in sched.values() for mid in per_match)


def fake_run(moment=SWITCH):
    from types import SimpleNamespace

    from jahbadh.agents.evidence import EvidenceStore
    return SimpleNamespace(desk=SimpleNamespace(match=DEMO), store=EvidenceStore(DEMO), moment=moment)


def test_plants_only_go_into_drafts_that_pass_the_number_check():
    from jahbadh.eval.plant import Planter
    dirty = Claim(id=f"{SWITCH.id}:c1", text="Omar Rasmus linked play (events 1231 and 1232).",
                  metric_ids=["field_tilt:RMU:0-3601"], event_ids=[1], figures=[])      # unknown metric: fails layer 1
    clean = Claim(id=f"{SWITCH.id}:c2", text="Omar Rasmus dropped deep to link play.", metric_ids=[],
                  event_ids=[1], figures=[])
    planter = Planter(1, {SWITCH.id: "wrong_player"})
    [planted] = planter(fake_run(), [dirty, clean])
    assert "Omar Rasmus" not in planted.text and planted.text.endswith("dropped deep to link play.")
    only_dirty = Planter(1, {SWITCH.id: "wrong_player"})
    assert only_dirty(fake_run(), [dirty]) == [] and only_dirty.carried == ["wrong_player"]


def test_a_plant_remembers_whether_its_source_draft_was_rejected_too():
    from jahbadh.eval.plant import Planter
    clean = Claim(id=f"{SWITCH.id}:c2", text="Omar Rasmus dropped deep to link play.", metric_ids=[],
                  event_ids=[1], figures=[])
    planter = Planter(1, {SWITCH.id: "wrong_player"})
    [planted] = planter(fake_run(), [clean])
    planter.record(planted, None, {clean.id})
    assert planter.results[0].source_rejected is True and planter.results[0].caught is False
