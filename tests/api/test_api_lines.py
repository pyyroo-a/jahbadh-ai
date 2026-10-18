from apifakes import demo_match
from jahbadh.api.lines import PHRASES, event_lines
from jahbadh.schemas import Event, EventType


def test_every_event_has_a_finished_line_in_every_language():
    m = demo_match()
    for e in m.events:
        lines = event_lines(m, e)
        assert set(lines) == {"en", "ar", "es"}
        for text in lines.values():
            assert text and "{" not in text and "—" not in text and "–" not in text


def test_lines_match_the_event():
    m = demo_match()
    assert event_lines(m, m.event(2))["en"] == "Marek Quill finds Quinn Yilmaz"
    assert event_lines(m, m.event(21))["en"] == "Sami Lindqvist shoots, no goal (xG 0.01)"
    assert event_lines(m, m.event(974))["en"] == "Substitution for Rivermouth United: Hugo Ruiz on, Zane Brennan off"
    assert event_lines(m, m.event(975))["es"] == "Rivermouth United pasa del 4-3-3 al 3-4-3"
    assert event_lines(m, m.event(1163))["en"] == "Northbridge FC push their press higher"
    assert event_lines(m, m.event(661))["en"] == "Half time"
    assert event_lines(m, m.event(213))["en"] == "GOAL! Kian Jansen scores for Northbridge FC"
    assert event_lines(m, m.event(13))["en"] == "Yellow card for Tomas Lindqvist"


def test_a_failed_pass_never_says_why_it_failed():
    # the simulator records no receiver and no reason for a failed pass (cut out, loose or out of play)
    m = demo_match()
    failed = next(e for e in m.events if e.type == EventType.PASS and not e.outcome)
    name = next(p.name for t in (m.meta.home, m.meta.away) for p in t.players if p.id == failed.player_id)
    assert event_lines(m, failed)["en"] == f"{name}'s pass goes astray"


def test_names_are_never_translated():
    m = demo_match()
    lines = event_lines(m, m.event(2))
    assert all("Marek Quill" in lines[lang] and "Quinn Yilmaz" in lines[lang] for lang in ("ar", "es"))


def test_every_phrase_exists_in_every_language():
    assert all(set(by_lang) == {"en", "ar", "es"} for by_lang in PHRASES.values())


def test_a_lost_tackle_and_a_full_time_whistle():
    m = demo_match()
    lost = next(e for e in m.events if e.type == EventType.TACKLE and not e.outcome)
    assert "goes in for the tackle but misses" in event_lines(m, lost)["en"]
    whistle = Event(id=9999, t=5399, period=2, team_id="NBR", player_id=None, type=EventType.PERIOD_END, x=52.5, y=34)
    assert event_lines(m, whistle) == {"en": "Full time", "ar": "نهاية المباراة", "es": "Final del partido"}


def test_arabic_and_spanish_wording_reads_back_right():
    # free back-translation (18 Oct): "يغير الرسم" read as "changes the graphics", "retrasa su presión" as "delays",
    # "va a la entrada" as "goes to the inning"; these phrasings read back as the football they describe
    m = demo_match()
    assert event_lines(m, m.event(975))["ar"] == "Rivermouth United يغير الخطة من 4-3-3 إلى 3-4-3"
    assert event_lines(m, m.event(1163))["es"] == "Northbridge FC sube su línea de presión"
    assert PHRASES["press_deeper"]["ar"] == "{team} يخفض خط الضغط"
    assert PHRASES["press_deeper"]["es"] == "{team} baja su línea de presión"
    assert PHRASES["tackle_lost"]["es"] == "{player} intenta la entrada pero no recupera el balón"
