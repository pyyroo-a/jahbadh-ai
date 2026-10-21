# Live Slow-down Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** In live mode the match drops to real time while a key moment's checked line is with the desk, so the line lands within about a minute of the moment, and every persona can see why.

**Architecture:** The server owns the pace. `LiveRun` keeps a set of "holds" (key moments still with the desk), advances its clock in one-real-second ticks at the pace in force, and streams two new kinds: `pace` (speed now and who holds it) and `step` (each finished desk step, with the clock time). The pipeline reports finished steps through an optional callback. The page only reads those messages: its ticking clock follows the latest `pace`, and the persona picks how the slow-down is drawn.

**Tech Stack:** Python 3.13, asyncio, pydantic, FastAPI SSE, Microsoft Agent Framework workflows; React + TypeScript (Vite, vitest, oxlint).

**Spec:** `docs/superpowers/specs/2026-10-21-live-slowdown-design.md` (committed as 39d4b62). Part of Plan 4; Plan 4's ledger records it.

## Global Constraints

- No new runtime dependencies (Python or web).
- TDD per step: the test is written and seen failing first; the whole Python suite (`.venv/Scripts/python -m pytest -q`, about 9 min, run in the background) and the web checks (`npm --prefix web run test`, `run build`, `run lint`) are green at the end of every task.
- No em or en dashes anywhere: code comments, UI copy, docs, commit text. Friendly tone.
- Data-true: a hold starts at the moment's own clock time, never before; only the pace changes, never an event's time or what the desk says; progress shown is real finished steps only.
- Live mode only holds. Replay is unchanged. Ingest never holds (it still reports steps). Spotlights and `full_time` never hold. Extra versions (combos) never hold.
- Hold speed 1x (`LIVE_HOLD_SPEED = 1.0`), base speed `LIVE_SPEED = 6.0` unchanged, cap `LIVE_HOLD_CAP_S = 120.0` real seconds per hold, pacing tick `PACE_TICK_S = 1.0` real second.
- `LIVE_CONCURRENCY = 3` unchanged; key moments and spotlights take a free place before any waiting combo.
- Existing stream kinds keep their payloads. `MatchInfo.speed` stays the base speed.
- The user commits every change: after each task, stop with commit instructions (files, Summary, Description) and wait for "committed". Never commit or push.
- A real live run costs money (about $0.35, more with extra versions) and needs the user's yes; this plan proves behaviour with fake desks and fake sleeps.

## Review Focus

1. A viewer reconnects in the middle of a hold: the history replays in a burst, and the page must end up slowed with the right moment named (latest `pace` wins), then unslowed when the hold ends. Test in Task 4.
2. A held moment fails (rate limit, bad reply): its hold ends with the failure, the pace goes back to 6x, no Publish step is sent. Test in Task 3.
3. A viewer has added all 8 extra versions and the next key moment arrives while their renders queue: the moment gets the next free place. Test in Task 1 (gate) and Task 3 (in a run).
4. The run ends or is cancelled (idle, or `cancel()`) during a hold: no stuck "slowed" state on the page after `end`, nothing left holding on the server. Tests in Task 3 and Task 4.
5. Two holds overlap: the pace stays 1x until the second lands, and the banner names the earliest moment still holding. Tests in Task 3 and Task 4.

---

### Task 1: Key moments go ahead of extra versions in the desk queue

**Files:**
- Create: `src/jahbadh/api/gate.py`
- Modify: `src/jahbadh/api/live.py` (`_events` builds the gate; `_work` and `_render` take slots)
- Test: `tests/api/test_api_gate.py`, `tests/api/test_api_live_core.py`

**Interfaces:**
- Produces: `class PriorityGate` with `__init__(self, limit: int)` and `slot(self, first: bool) -> contextlib.AbstractAsyncContextManager[None]`. At most `limit` holders at once. When a place frees, a waiting `first=True` caller goes before any waiting `first=False` caller; FIFO within each group. A caller cancelled while waiting leaves the queue without taking a place.
- `LiveRun._gate: PriorityGate | None` (same attribute name, new type). `_work` uses `slot(first=True)`, `_render` uses `slot(first=False)`.

- [ ] **Step 1: Write the failing tests** in `tests/api/test_api_gate.py`:
  - `test_a_free_gate_lets_callers_straight_in`: limit 2, two `slot(first=False)` entered together without waiting.
  - `test_a_waiting_moment_goes_before_waiting_versions`: limit 1; A holds a slot; then queue `v1 = slot(first=False)`, `v2 = slot(first=False)`, `m = slot(first=True)` in that order; release A; the order of entry is `["m", "v1", "v2"]`.
  - `test_a_caller_cancelled_while_waiting_gives_up_its_turn`: limit 1; A holds; B waits and is cancelled; C waits; release A; C enters, and the gate later admits a new caller immediately (no place lost).
  And in `tests/api/test_api_live_core.py`:
  - `test_a_key_moment_is_not_stuck_behind_extra_versions(monkeypatch)`: monkeypatch `live.LIVE_CONCURRENCY` to 1, add all 8 combos, patch `live.render_combo` with a fake that records its start and awaits a short `asyncio.sleep(0)` chain, patch `pipeline.run_moment` with a fake (signature `(desk, moment, on_step=None)`) that records its start; after the first feed, the second key moment's start is recorded before the 8th combo render of the first moment starts.
- [ ] **Step 2: Run them, expect FAIL** (`ModuleNotFoundError: jahbadh.api.gate`, then the ordering assertion).
  Run: `.venv/Scripts/python -m pytest -q tests/api/test_api_gate.py tests/api/test_api_live_core.py -k "gate or stuck"`
- [ ] **Step 3: Implement `PriorityGate`** in `src/jahbadh/api/gate.py` with two `collections.deque`s of futures and a count; and switch `LiveRun` to it.
- [ ] **Step 4: Run them, expect PASS**, then the whole suite in the background: `.venv/Scripts/python -m pytest -q` (expect everything green; existing `async def publish(desk, moment)` fakes need no change yet).
- [ ] **Step 5: Stop for the user's commit** (Summary suggestion: `feat(live): let key moments go ahead of extra versions in the desk queue`).

### Task 2: The desk reports each finished step on the stream

**Files:**
- Modify: `src/jahbadh/agents/desk.py` (`MomentRun.on_step`), `src/jahbadh/agents/pipeline.py` (`run_moment`, `_Step` subclasses), `src/jahbadh/api/stream.py` (`DeskStep`, `StepUpdate`, `StreamKind`), `src/jahbadh/api/live.py` (`_work`)
- Modify (fakes): every test fake that replaces `pipeline.run_moment` gains `on_step=None` (grep `"run_moment"` under `tests/`)
- Test: `tests/agents/test_pipeline_steps.py` (new), `tests/api/test_api_live_core.py`, `tests/api/test_api_ingest.py`

**Interfaces:**
- Produces (Python): `DeskStep = Literal["analyst", "tactical", "writer", "referee", "rewrite", "recheck", "publish"]`; `class StepUpdate(BaseModel): moment_id: str; step: DeskStep; t: float`; `StreamKind` gains `"step"`.
- Produces: `MomentRun.on_step: Callable[[DeskStep], None] | None = None`; `async def run_moment(desk: Desk, moment: Moment, on_step: Callable[[DeskStep], None] | None = None) -> FeedItem`.
- Reported by the pipeline, each once its own work is done and before it sends its message: Analyst `"analyst"`, Tactical `"tactical"`, Writer `"writer"` (or `"rewrite"` when it handles `state.retry`), Referee `"referee"` (or `"recheck"` on its second check, `state.attempt >= 1`). Persona and Localize report nothing: they are part of Publish.
- `LiveRun._work` passes `on_step` that appends `StreamItem(t=self.clock, kind="step", data=StepUpdate(moment_id=..., step=..., t=self.clock))`, and appends `step="publish"` at `self.clock` immediately before the `feed` item (same `t`). A failure gets no publish step. Ingest runs inherit this.

- [ ] **Step 1: Write the failing tests:**
  - `tests/agents/test_pipeline_steps.py::test_a_clean_moment_reports_its_steps_in_order`: run a moment with the scripted full desk client (as the existing pipeline tests do) and a list-appending `on_step`; steps `== ["analyst", "tactical", "writer", "referee"]`.
  - `...::test_a_rewrite_reports_the_rewrite_and_the_second_check`: a scripted desk whose Referee rejects one claim on the first check (reuse the existing rewrite test's script); steps `== ["analyst", "tactical", "writer", "referee", "rewrite", "recheck"]`.
  - `...::test_steps_are_optional`: `run_moment(desk, moment)` with no callback still returns the FeedItem (the eval and showcase CLI path).
  - `tests/api/test_api_live_core.py::test_live_steps_come_before_their_feed_and_publish_shares_its_time`: a full drained run; for every feed, the item just before it is `kind == "step"` with `step == "publish"`, the same `moment_id`, and `t == feed.t == step.data.t`; every moment's step items come after its `thinking`.
  - `...::test_a_failed_moment_sends_no_publish_step` (reuse the flaky analyse setup).
  - `tests/api/test_api_ingest.py::test_an_ingest_moment_reports_its_steps`: one ingest moment with a scripted desk produces step items ending in `publish`.
- [ ] **Step 2: Run them, expect FAIL** (no `on_step` parameter, no `"step"` kind).
- [ ] **Step 3: Implement** the models, the callback, the pipeline reports and the live appends; update the `run_moment` fakes in tests to `(desk, moment, on_step=None)`. Also add `"step"` anywhere a test or helper pins the full list of stream kinds (grep `StreamKind`, `STREAM_KINDS`); the web side of the list moves in Task 4, so if a Python test compares against `web/src/api/types.ts`, update that one line of `STREAM_KINDS` and the `StreamMessage` union now with a `StepUpdate` interface (fields as above).
- [ ] **Step 4: Run them, expect PASS**; whole Python suite in the background; web test, build, lint if `types.ts` changed.
- [ ] **Step 5: Stop for the user's commit** (Summary suggestion: `feat(desk): report each finished step on the live stream`).

### Task 3: The live match slows to real time while a key moment is with the desk

**Files:**
- Modify: `src/jahbadh/api/live.py` (constants, `_play` pacing, `_begin`, `_work`, `spotlight`, `cancel`), `src/jahbadh/api/ingest.py` (`IngestRun.HOLDS = False`), `src/jahbadh/api/stream.py` (`PaceUpdate`, `StreamKind`)
- Test: `tests/api/test_api_live_core.py`, `tests/api/test_api_ingest.py`

**Interfaces:**
- Consumes: Task 1's gate, Task 2's step items.
- Produces (Python): `class PaceUpdate(BaseModel): t: float; speed: float; holding: list[str]` (moment ids, earliest moment first; empty when back to normal); `StreamKind` gains `"pace"`.
- Constants in `live.py`: `LIVE_HOLD_SPEED = 1.0`, `LIVE_HOLD_CAP_S = 120.0`, `PACE_TICK_S = 1.0`.
- `LiveRun.HOLDS: ClassVar[bool] = True`; `IngestRun.HOLDS = False`.
- `LiveRun._holds: dict[str, float]` (moment id to `self.now()` when the hold began). `_begin(moment, at, hold: bool)`: appends `thinking`, then, if `hold`, adds the hold and announces. `_play` calls it with `hold=self.HOLDS and moment.kind != "full_time"`; `spotlight` with `hold=False`.
- `_pace() -> float`: drops holds older than `LIVE_HOLD_CAP_S` (announcing if any dropped), returns `LIVE_HOLD_SPEED` if any hold is left, else `self.speed`.
- Announcing appends `StreamItem(t=self.clock, kind="pace", data=PaceUpdate(...))` only when `(speed, holding)` differs from the last one announced. No `pace` item is sent before the first hold (the page starts at `MatchInfo.speed`).
- `_work` releases its moment's hold (and announces) right after its `feed` and cues, or its `failure`. `cancel()` clears holds without announcing.

- [ ] **Step 1: Write the failing tests** in `tests/api/test_api_live_core.py`. Helper in the test file: `paces(run) -> list[PaceUpdate]` and `real_seconds(run) -> float`, the real time a run should have slept, from its pace items: each span of match seconds divided by the speed in force over it (base `LIVE_SPEED` outside spans).
  - Change `test_a_live_run_publishes_every_key_moment_on_the_clock`: `sum(slept) == pytest.approx(real_seconds(run))` replaces `5400 / LIVE_SPEED`; everything else stays.
  - `test_a_key_moment_holds_the_match_at_real_time_until_its_line_lands(monkeypatch)`: patch `pipeline.run_moment` so the first key moment waits on an `asyncio.Event` and the rest publish at once; the recording sleep sets the event on its 5th call after that moment's `thinking`. Assert: the item right after its `thinking` is `pace` with `speed == 1.0`, `holding == [id]`, `t == moment.t`; the next 5 sleeps are `1.0` each; its `feed.t == moment.t + 5` (within one tick); the item after its last cue is `pace` with `speed == LIVE_SPEED`, `holding == []`, same `t` as the feed.
  - `test_the_match_never_slows_before_a_moment`: in a full drained run, every `pace` with `speed == 1.0` comes right after a `thinking` with the same `t` whose id is in `holding`, and no event before that index has `t` greater than it.
  - `test_a_stuck_moment_lets_the_match_go_after_the_cap(monkeypatch)`: `now` is a fake clock moved forward by each fake sleep; the held moment releases only after 150 sleeps; a `pace` back to `LIVE_SPEED` with `holding == []` comes about `LIVE_HOLD_CAP_S` real seconds after the hold began (within one tick) and before that moment's `feed`, which still arrives later.
  - `test_a_failed_moment_ends_its_hold` (flaky analyse on one key moment): its `failure` is followed by `pace` back to `LIVE_SPEED`.
  - `test_two_close_moments_hold_until_both_land(monkeypatch)`: two held moments released in order B then A; `holding` goes `[A]`, `[A, B]`, `[A]`, `[]`, speed `1.0` until the last.
  - `test_spotlights_and_full_time_never_hold`: no `pace` names a `spotlight-` id or the `full_time` moment's id.
  - `test_extra_versions_never_hold(monkeypatch)`: with all 8 combos added and renders held on an event, the pace returns to `LIVE_SPEED` right after the moment's feed while renders are still waiting.
  - `test_cancel_during_a_hold_ends_cleanly`: a held moment, `cancel()`; history ends with `end`, `run._holds == {}`.
  - `tests/api/test_api_ingest.py::test_an_outside_feed_never_slows`: an ingest run with a moment and a scripted desk has no `pace` items.
- [ ] **Step 2: Run them, expect FAIL** (no `pace` kind; sleeps still `gap / 6`).
  Run: `.venv/Scripts/python -m pytest -q tests/api/test_api_live_core.py tests/api/test_api_ingest.py`
- [ ] **Step 3: Implement the pacing.** The loop advances in ticks so a hold that starts or ends mid-gap takes effect within a second:

```python
while item.t > self.clock:
    pace = self._pace()
    target = self.clock
    step = min(item.t - target, pace * PACE_TICK_S)
    await self._wait(step / pace)
    if self.done:
        return
    if self.clock == target:                  # not skipped meanwhile
        self.clock = target + step
```

  Skip and idle cancel keep working as now (skip still wakes `_wait`; skipping does not end a hold).
- [ ] **Step 4: Run them, expect PASS**; whole Python suite in the background (every existing live, ingest and route test green).
- [ ] **Step 5: Stop for the user's commit** (Summary suggestion: `feat(live): slow the match to real time while the desk checks a key moment`).

### Task 4: The page follows the pace and keeps the steps

**Files:**
- Modify: `web/src/api/types.ts` (`PaceUpdate`, `StepUpdate`, `DeskStep`, `StreamMessage`, `STREAM_KINDS`), `web/src/state/desk.ts` (`DeskState.pace`, `DeskState.steps`, reducer), `web/src/App.tsx` (the ticking clock's speed)
- Create: `web/src/state/slowdown.ts`
- Test: `web/src/state/desk.test.ts`, `web/src/state/slowdown.test.ts` (new)

**Interfaces:**
- Consumes: Task 2's `StepUpdate {moment_id, step, t}` and Task 3's `PaceUpdate {t, speed, holding}` (same field names in TypeScript).
- Produces: `DeskState.pace: PaceUpdate | null` (latest, `null` initially and after `end`); `DeskState.steps: Record<string, StepUpdate[]>` (by moment id, in arrival order, no duplicates by step name).
- `slowdown.ts`: `isSlowed(desk: DeskState): boolean` (pace speed below `desk.info.speed` and not ended); `holdingMoment(desk: DeskState): Moment | null` (the first id of `pace.holding` found in `desk.thinking`); `clockSpeed(desk: DeskState): number` (`pace.speed`, else `info.speed`, else 6); `landedAt(desk: DeskState, momentId: string): number | null` (the `publish` step's `t`); `stepChips(steps: StepUpdate[]): { step: DeskStep; done: boolean }[]` (always `analyst, tactical, writer, referee`, then `rewrite, recheck` only if either was reported, then `publish`; `done` when reported; nothing marked as "in progress", since nobody knows which step comes next).
- `App.tsx`: `tickingClock(..., clockSpeed(desk), ...)` instead of `info?.speed ?? 6`.

- [ ] **Step 1: Write the failing tests:**
  - `desk.test.ts`: `"keeps the latest pace and drops it at the end"`; `"keeps each moment's steps once, in order"` (a resent `step` with a lower id is ignored by the existing `lastId` rule, and the same step name twice is kept once); `"a reconnect burst ends on the latest pace"` (replaying `match, thinking, pace(1, [a]), step..., feed, pace(6, [])` from scratch gives `pace.speed == 6`, `holding == []`).
  - `slowdown.test.ts`: `isSlowed` true at speed 1 vs info speed 6, false after `end`, false in replay (no pace); `holdingMoment` returns the earliest holding moment of two; `clockSpeed` falls back to `info.speed`; `landedAt` reads the publish step's `t` and is `null` without one; `stepChips` for a clean moment is the five base chips with the first four done, and with a rewrite shows seven with `rewrite` and `recheck` in place.
- [ ] **Step 2: Run, expect FAIL.** Run: `npm --prefix web run test`
- [ ] **Step 3: Implement** the types, reducer cases (`pace`: `{ ...next, pace: m.data, clock: Math.max(s.clock, m.data.t) }`; `step`: append to `steps[moment_id]` and advance the clock the same way; `end` also sets `pace: null`) and `slowdown.ts`; switch the App clock.
- [ ] **Step 4: Run, expect PASS**: `npm --prefix web run test`, `run build`, `run lint`. If a Python test compares the kind lists, run it too.
- [ ] **Step 5: Stop for the user's commit** (Summary suggestion: `feat(web): follow the live pace and keep the desk's steps`).

### Task 5: Show the slow-down, per persona

**Files:**
- Modify: `web/src/state/labels.ts` (`SLOWDOWN`, `STEP_LABELS`, `speedNote`), `web/src/components/TopBar.tsx` (`slowed` prop), `web/src/components/DeskFeed.tsx` (thinking cards, landed stamp), `web/src/components/layouts/FanLayout.tsx` (`banner` prop, thinking cards), `web/src/components/TacticalView.tsx` (`banner` prop drawn over the top of the pitch), `web/src/App.tsx` (wiring), `web/src/styles.css`
- Create: `web/src/components/SlowdownBanner.tsx`, `web/src/components/ThinkingCard.tsx`
- Test: `web/src/state/labels.test.ts`

**Interfaces:**
- Consumes: Task 4's `isSlowed`, `holdingMoment`, `landedAt`, `stepChips`, `DeskState.steps`, `DeskState.pace`.
- Produces: `SlowdownBanner({ moment }: { moment: Moment })`; `ThinkingCard({ moment, holding, chips, detailed }: { moment: Moment; holding: boolean; chips: { step: DeskStep; done: boolean }[]; detailed: boolean })`; `TopBar` prop `slowed: boolean`; `TacticalView` prop `banner?: ReactNode`; `FanLayout` prop `banner?: ReactNode`.
- Copy (exact, in `labels.ts`):
  - `SLOWDOWN.pill = "1x · desk checking"`
  - `SLOWDOWN.banner = "Desk review"` (drawn uppercase by CSS, followed by ` · ` and the moment's label)
  - `SLOWDOWN.bannerSub = "Slowed so the desk can write and check its line"`
  - `SLOWDOWN.checking = (label: string) => \`The desk is checking ${label}.\``
  - `SLOWDOWN.checkingSub = "The match is slowed to real time so its agents can write and check the line before play moves on."`
  - `SLOWDOWN.landed = (t: number) => \`Checked, landed at ${mm}:${ss}\`` (match clock, minutes and two-digit seconds, e.g. 3356 gives "Checked, landed at 55:56")
  - `STEP_LABELS = { analyst: "Analyst", tactical: "Tactical", writer: "Writer", referee: "Referee", rewrite: "Rewrite", recheck: "Referee again", publish: "Publish" }`
  - `speedNote` for live becomes "Quick lines arrive straight away. At each key moment the match slows to real time while the desk writes and checks its line, so it lands within about a minute of the moment." (ingest and replay unchanged)
- Placement:
  - Everyone (live, while `isSlowed`): the top bar minute gets class `minute slowed` (amber, `var(--amber)`) and a pill with `SLOWDOWN.pill` beside it.
  - Casual fan (`layoutFor(persona) === "fan"`): `SlowdownBanner` for `holdingMoment(desk)` while slowed: on desktop through `TacticalView`'s `banner` (absolute strip across the top of the pitch); on phones through `FanLayout`'s `banner`, first in the stack above the momentum bar. Casual thinking cards stay as today ("The desk is thinking about {label}...").
  - Studio pundit and Fantasy (`DeskFeed` with persona not casual): `ThinkingCard` with `detailed`: a holding moment shows `SLOWDOWN.checking(label)` and `SLOWDOWN.checkingSub`; any other moment shows "The desk is thinking about {label}..."; both show the chips (done chips in `var(--ok)`, the rest muted).
  - Landed stamp: in live and ingest (`desk.info.mode !== "replay"`), each `Moment` card with a `landedAt` shows `SLOWDOWN.landed(t)` as a small `var(--ok)` note under its tag.
- Look: follow the approved mockup `.superpowers/brainstorm/1044-1792569373/content/slowdown-by-persona.html` and the existing CSS tokens; the banner text truncates with an ellipsis on narrow screens rather than wrapping the pitch.

- [ ] **Step 1: Write the failing tests** in `labels.test.ts`: `speedNote` live text is the new sentence exactly; `SLOWDOWN.landed(3356) === "Checked, landed at 55:56"` and `SLOWDOWN.landed(65) === "Checked, landed at 1:05"`; `SLOWDOWN.checking("15' Goal for Northbridge FC (Kian Jansen)")` is the sentence with that label; every `DeskStep` has a `STEP_LABELS` entry; no copy in `SLOWDOWN`, `STEP_LABELS` or `speedNote` contains an em or en dash.
- [ ] **Step 2: Run, expect FAIL.** Run: `npm --prefix web run test`
- [ ] **Step 3: Implement** the copy, the two components, the props and wiring, and the CSS.
- [ ] **Step 4: Run, expect PASS**: web test, build, lint. Then look at it in the browser pane without spending: replay must look exactly as before (no pill, banner, chips or stamp). The slowed look itself is checked by the tests and, with the user's yes, in one live run on the deployed site after shipping (about $0.35).
- [ ] **Step 5: Stop for the user's commit** (Summary suggestion: `feat(web): show the live slow-down for every persona`), then the user pushes and runs GitHub Actions > Deploy.
