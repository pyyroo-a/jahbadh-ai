import asyncio
import json
from datetime import date

import pytest

from apifakes import demo_match, recording_sleep, scripted_full_desk_client
from jahbadh.agents import pipeline
from jahbadh.agents.desk import Desk
from jahbadh.api.limits import DailyLimit
from jahbadh.api.live import LIVE_SPEED, SKIP_LEAD_S, LiveRun, key_moments

DEMO = demo_match()


def run_with(sleep=None, now=lambda: 0.0, **kw) -> LiveRun:
    sleep = sleep or recording_sleep()[0]
    desk = Desk(client=scripted_full_desk_client(), match=DEMO)
    return LiveRun("live-42-test", DEMO, desk, sleep=sleep, now=now, **kw)


async def drain(run: LiveRun, before=None) -> list:
    """Start the run, then read it as a viewer until the end."""
    run.start()
    if before:
        await before(run)
    return [x async for x in run.subscribe()]


def kinds(run: LiveRun) -> list[str]:
    return [i.kind for i in run.history]


def test_daily_limit_persists_and_resets(tmp_path):
    day = [date(2026, 10, 18)]
    lim = DailyLimit(tmp_path / "live.json", 3, today=lambda: day[0])
    assert lim.remaining() == 3
    assert [lim.take() for _ in range(4)] == [True, True, True, False]
    assert json.loads((tmp_path / "live.json").read_text()) == {"day": "2026-10-18", "used": 3}
    assert DailyLimit(tmp_path / "live.json", 3, today=lambda: day[0]).remaining() == 0
    day[0] = date(2026, 10, 19)
    assert lim.remaining() == 3 and lim.take() and lim.remaining() == 2


def test_daily_limit_fails_closed_on_a_corrupt_file(tmp_path):
    for broken in ("{nope", '{"day": "2026-10-18"}', '{"day": 5, "used": "x"}', "[]"):
        (tmp_path / "live.json").write_text(broken)
        lim = DailyLimit(tmp_path / "live.json", 3, today=lambda: date(2026, 10, 18))
        assert lim.remaining() == 0 and lim.take() is False


def test_daily_limit_makes_its_folder(tmp_path):
    assert DailyLimit(tmp_path / "state" / "live.json", 1).take() is True


def test_key_moments_on_the_demo_match():
    kinds_ = [mo.kind for mo in key_moments(DEMO)]
    assert len(kinds_) == 16 and kinds_[-1] == "full_time" and not {"momentum_swing", "check_in"} & set(kinds_)


def test_a_live_run_publishes_every_key_moment_on_the_clock():
    sleep, slept = recording_sleep()
    run = run_with(sleep)
    seen = asyncio.run(drain(run))
    k = kinds(run)
    assert k[0] == "match" and k[-1] == "end" and run.history[-1].data.reason == "full_time" and run.done
    info = run.history[0].data
    assert info.mode == "live" and info.precomputed is False and info.moment_times == []
    assert k.count("thinking") == k.count("feed") == 16 and "failure" not in k
    for n, i in enumerate(run.history):
        if i.kind == "thinking":
            assert i.t >= i.data.t and all(h.t <= i.t for h in run.history[:n] if h.kind == "event")
        if i.kind == "feed":          # never before its own thinking
            assert any(h.kind == "thinking" and h.data.id == i.data.moment.id for h in run.history[:n])
    assert sum(k_ == "event" for k_ in k) == len(DEMO.events)
    assert sum(slept) == pytest.approx(5400 / LIVE_SPEED)
    assert [n for n, _ in seen] == list(range(len(run.history)))


def test_a_failing_moment_is_reported_and_the_run_carries_on(monkeypatch):
    broken = key_moments(DEMO)[2]
    real = pipeline.analyse

    async def flaky(run):
        if run.moment.id == broken.id:
            raise RuntimeError("429 rate limited")
        return await real(run)

    monkeypatch.setattr(pipeline, "analyse", flaky)
    run = run_with()
    asyncio.run(drain(run))
    failures = [i for i in run.history if i.kind == "failure"]
    assert [f.data.moment_id for f in failures] == [broken.id] and "rate limited" in failures[0].data.error
    assert kinds(run).count("feed") == 15 and run.history[-1].data.reason == "full_time"


def test_skip_jumps_to_the_next_moment():
    calls: list[tuple[float, float]] = []
    run = None

    async def sleep(s: float) -> None:
        calls.append((run.clock, s))

    run = run_with(sleep)
    first = key_moments(DEMO)[0]
    assert run.skip() == first.t - SKIP_LEAD_S and run.clock == first.t - SKIP_LEAD_S
    asyncio.run(drain(run))
    clock, s = next((c, s) for c, s in calls if s > 0)
    assert clock + s * LIVE_SPEED >= first.t - SKIP_LEAD_S
    early = [i for i in run.history if i.kind == "event" and i.t < first.t - SKIP_LEAD_S]
    assert early and kinds(run).count("thinking") == 16          # the skipped events still went out


def test_skip_returns_none_when_no_moment_is_left():
    run = run_with()
    asyncio.run(drain(run))
    assert run.skip() is None


def test_nobody_watching_cancels_the_run(monkeypatch):
    clock = [0.0]
    run = run_with(now=lambda: clock[0], idle_s=60)
    cancelled_at: list[int] = []
    release = asyncio.Event()
    real = pipeline.analyse

    async def held(r):                     # every moment stays with the desk until the test lets go
        await release.wait()
        return await real(r)

    monkeypatch.setattr(pipeline, "analyse", held)

    async def sleep(s: float) -> None:
        if run.clock >= 1800:              # half an hour in, the last viewer has been gone for two minutes
            clock[0] = 120.0
        await asyncio.sleep(0)

    run.sleep = sleep

    async def watch_then_leave(r: LiveRun) -> None:
        async for _, item in r.subscribe():
            if item.kind == "event":
                break                      # the viewer closes the tab at kick-off

    async def main():
        run.start()
        await watch_then_leave(run)
        while not run.done:
            await asyncio.sleep(0.01)
        cancelled_at.append(len(run.desk.client.calls))
        release.set()
        await asyncio.sleep(0.2)           # anything still running would call the model now

    asyncio.run(asyncio.wait_for(main(), timeout=30))      # a run that never cancels fails, not hangs
    assert run.history[-1].data.reason == "cancelled" and run.done
    assert run.clock < 5400 and kinds(run).count("end") == 1
    assert kinds(run).count("thinking") >= 4 and "feed" not in kinds(run)    # moments were still in flight
    assert len(run.desk.client.calls) == cancelled_at[0] == 0


def test_a_viewer_keeps_the_run_alive():
    clock = [0.0]

    async def sleep(s: float) -> None:
        clock[0] += s                      # wall time passes with the match: 15 minutes at 6x
        await asyncio.sleep(0)

    run = run_with(sleep, now=lambda: clock[0], idle_s=60)
    asyncio.run(drain(run))
    assert run.history[-1].data.reason == "full_time"


def test_cancel_ends_the_stream_for_viewers():
    run = run_with()

    async def main():
        run.start()
        await run.cancel()
        await run.cancel()                 # twice is harmless
        return [i.kind async for _, i in run.subscribe()]

    seen = asyncio.run(main())
    assert seen[-1] == "end" and run.history[-1].data.reason == "cancelled" and seen.count("end") == 1


def test_spotlight_runs_at_the_current_clock():
    run = run_with()
    at = run.skip()

    async def ask(r: LiveRun) -> None:
        mo = await r.spotlight("RMU-33")
        assert mo.t == at and mo.id == f"spotlight-RMU-33-{int(at)}" and mo.kind == "spotlight"
        with pytest.raises(KeyError):
            await r.spotlight("XYZ-1")

    asyncio.run(drain(run, before=ask))
    thinking = [i for i in run.history if i.kind == "thinking" and i.data.kind == "spotlight"]
    assert len(thinking) == 1 and thinking[0].t == at
    feeds = [i.data.moment.id for i in run.history if i.kind == "feed"]
    assert f"spotlight-RMU-33-{int(at)}" in feeds and len(feeds) == 17


def test_only_two_extra_combos_per_run():
    run = run_with()
    assert run.add_combo("pundit", "en") is True             # the default never counts
    assert [run.add_combo("casual", "en"), run.add_combo("pundit", "ar"), run.add_combo("fantasy", "es")] == \
        [True, True, False]
    assert run.add_combo("casual", "en") is True             # one that already exists is fine
    asyncio.run(drain(run))
    renders = [i for i in run.history if i.kind == "renders"]
    assert len(renders) == 2 * 16
    for n, i in enumerate(run.history):
        if i.kind == "renders":
            assert any(h.kind == "feed" and h.data.moment.id == i.data.moment_id for h in run.history[:n])


def test_a_combo_added_mid_run_renders_what_already_published():
    run = run_with()

    async def main():
        run.start()
        async for _, item in run.subscribe():
            if item.kind == "feed":
                run.add_combo("casual", "es")
                break
        return [x async for x in run.subscribe()]

    asyncio.run(main())
    feeds = [i.data.moment.id for i in run.history if i.kind == "feed"]
    rendered = [i.data.moment_id for i in run.history if i.kind == "renders"]
    assert sorted(rendered) == sorted(feeds) and len(feeds) == 16


def _one_claim(monkeypatch) -> None:
    """Every moment publishes one plain claim, so there is something to cue."""
    from jahbadh.agents.contracts import Claim, FeedItem

    async def publish(desk, moment):
        claim = Claim(id=f"{moment.id}:c1", text=f"{moment.label}.", metric_ids=[], event_ids=list(moment.event_ids),
                      figures=[])
        return FeedItem(moment=moment, claims=[claim], renders=[], rejections=[], metrics=[], stats={}, latency_s=0.0)

    monkeypatch.setattr(pipeline, "run_moment", publish)


def test_live_claim_cues_follow_their_feed_item(monkeypatch):
    _one_claim(monkeypatch)
    run = run_with()
    asyncio.run(drain(run))
    h = run.history
    feeds = [n for n, i in enumerate(h) if i.kind == "feed"]
    assert len(feeds) == 16
    for n in feeds:
        cue = h[n + 1]
        assert cue.kind == "cue" and cue.data.source == "claim" and cue.t == h[n].t
        assert cue.data.id == f"claim-{h[n].data.moment.id}:c1" and cue.data.precomputed is False
        assert cue.data.match_time == h[n].t and cue.data.text["en"] == h[n].data.claims[0].text


def test_every_live_cue_says_it_was_not_precomputed():
    run = run_with()
    asyncio.run(drain(run))
    cues = [i.data for i in run.history if i.kind == "cue"]
    assert cues and {c.source for c in cues} >= {"event", "metric"} and not any(c.precomputed for c in cues)


def test_nothing_new_starts_while_a_run_is_cancelling(monkeypatch):
    release = asyncio.Event()
    real = pipeline.analyse

    async def held(r):
        await release.wait()
        return await real(r)

    monkeypatch.setattr(pipeline, "analyse", held)
    run = run_with(sleep=lambda s: asyncio.sleep(0))

    async def main():
        run.start()
        while kinds(run).count("thinking") < 1:
            await asyncio.sleep(0)
        stopping = asyncio.create_task(run.cancel())
        await asyncio.sleep(0)                 # cancel() is now waiting for the moments to stop
        assert run.finished and not run.done
        with pytest.raises(RuntimeError):
            await run.spotlight("RMU-33")
        assert run.add_combo("casual", "en") is False
        await stopping
        release.set()
        await asyncio.sleep(0.1)

    asyncio.run(asyncio.wait_for(main(), timeout=30))
    assert run.history[-1].data.reason == "cancelled"
    assert not any(i.kind == "thinking" and i.data.kind == "spotlight" for i in run.history)


def test_two_spotlights_on_one_player_in_the_same_second_both_run():
    run = run_with()
    at = run.skip()

    async def ask_twice(r: LiveRun) -> None:
        first, second = await r.spotlight("RMU-33"), await r.spotlight("RMU-33")
        assert first.id == f"spotlight-RMU-33-{int(at)}" and second.id != first.id

    asyncio.run(drain(run, before=ask_twice))
    feeds = [i.data.moment.id for i in run.history if i.kind == "feed" and i.data.moment.kind == "spotlight"]
    assert len(feeds) == 2 and len(set(feeds)) == 2


def test_combos_with_one_persona_share_its_english(monkeypatch):
    from jahbadh.agents.contracts import RenderedClaim
    from jahbadh.api import live
    _one_claim(monkeypatch)
    calls: list[tuple[str, str, bool]] = []

    async def fake_render(desk, item, persona, language):
        has_english = any(r.persona == persona and r.language == "en" for r in item.renders)
        calls.append((item.moment.id, language, has_english))
        await asyncio.sleep(0)
        if language == "en":
            return [RenderedClaim(claim_id=c.id, persona=persona, language="en", text=f"{persona} take {len(calls)}")
                    for c in item.claims], []
        return [RenderedClaim(claim_id=c.id, persona=persona, language=language, text="ترجمة") for c in item.claims], []

    monkeypatch.setattr(live, "render_combo", fake_render)
    run = run_with()
    run.add_combo("casual", "en")
    run.add_combo("casual", "ar")
    asyncio.run(drain(run))
    english = [c for c in calls if c[1] == "en"]
    assert len(english) == 16 and len({m for m, _, _ in english}) == 16       # once per moment, never twice
    arabic = [c for c in calls if c[1] == "ar"]
    assert len(arabic) == 16 and all(has for _, _, has in arabic)            # each starts from the shared English


def test_live_start_builds_the_timeline_off_the_event_loop(monkeypatch):
    import threading

    from jahbadh.api import live
    built_on = []
    real = live.match_timeline

    def spy(*a, **kw):
        built_on.append(threading.get_ident())
        return real(*a, **kw)

    monkeypatch.setattr(live, "match_timeline", spy)
    run = run_with()

    async def go():
        loop_thread = threading.get_ident()
        await drain(run)
        return loop_thread

    loop_thread = asyncio.run(go())
    assert built_on and all(t != loop_thread for t in built_on)


def test_a_corrupt_counter_file_is_logged_with_its_path(tmp_path, caplog):
    path = tmp_path / "live.json"
    path.write_text("{not json")
    with caplog.at_level("WARNING"):
        assert DailyLimit(path, per_day=3).remaining() == 0
    assert str(path) in caplog.text
