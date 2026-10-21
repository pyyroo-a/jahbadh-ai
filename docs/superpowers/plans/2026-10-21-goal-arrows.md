# Goal Arrows Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Each goal's build-up plays on the tactical view as a TV-style replay (arrows in order, then the shot), with a "Goal build-ups" chip row to watch any goal again.

**Architecture:** The server picks the build-up: a pure walk in `src/jahbadh/api/buildup.py` over the events before the goal, attached to the goal's `EventLine` as `buildup` (a list of ordinary event lines). The browser only draws it: pure helpers in `web/src/state/goals.ts` (chips, which replay plays, pace) and `web/src/pitch/layers.ts` (geometry), a `GoalReplay` component animated with CSS, and wiring in `TacticalView` and `App`.

**Tech Stack:** Python 3.13, pydantic, pytest; React 19, TypeScript, Vite, vitest, oxlint.

**Spec:** `docs/superpowers/specs/2026-10-21-goal-arrows-design.md`

## Global Constraints

- Data-true: draw only recorded events; a shot arrow ends at its recorded `end_x`, `end_y` (the simulator's are (105, 34) for the home side and (0, 34) for the away side); no curves, no invented touches, no forced goal centre.
- The server picks the move; the browser never decides which events belong to it.
- No change to the simulator, the agents, the showcase output or what claims cite. No model calls, no cost.
- No em dashes or en dashes in UI copy, comments, docs or commit text. Friendly, plain copy.
- Web: no new dependencies; tsconfig has `erasableSyntaxOnly`; oxlint rejects setState inside effects and impure calls (like `Date.now()`) in render.
- Test basenames stay unique across `tests/` (API tests are `tests/api/test_api_*.py`).
- Never commit or push: each task ends by giving the user the files to tick, a Summary and a Description, then waiting for "committed".

## Review Focus

- A replay skip or reconnect delivers old goals in one catch-up burst: an old goal must not play by itself (only a goal within `GOAL_FRESH_S` of the clock). Test in Task 2 (`freshGoal`).
- The stream restarts (a new match, a mode switch) while a replay plays: the requested goal is no longer in `eventsById`, so nothing plays and nothing crashes. Guard in Task 3, checked in the browser.
- Arabic: each step line in the step list is right to left on its own, like the event stream. Checked in Task 3's browser step.
- A 20-action move must not take 16 seconds: `stepMs` keeps a whole replay at about 7 s. Test in Task 2.
- An outside feed sends a goal and later events in the same batch: the walk must use only events before the goal. Test in Task 1.

---

### Task 1: The server picks each goal's build-up

**Files:**
- Create: `src/jahbadh/api/buildup.py`
- Modify: `src/jahbadh/api/stream.py` (`EventLine`), `src/jahbadh/api/timeline.py` (`event_line`)
- Test: `tests/api/test_api_buildup.py` (new), `tests/api/test_api_timeline.py::test_event_line_payload_keys_are_the_protocol`

**Interfaces:**
- Produces: `goal_buildup(events: list[Event], goal: Event) -> list[Event]` (ordered steps, the shot last; or the goal itself last when it has no shot). `EventLine.buildup: list[EventLine] | None` (a list only on GOAL lines, `None` on every other line).

- [ ] **Step 1: Write the failing tests** in `tests/api/test_api_buildup.py`.

Real data (`demo_match()`, the showcase match, measured 21 Oct):

```python
DEMO = demo_match()
def ids_for(goal_id): return [e.id for e in goal_buildup(DEMO.events, DEMO.event(goal_id))]

def test_a_won_tackle_starts_the_move():                 # Quill 27'
    assert ids_for(421) == [415, 416, 418, 419, 420]

def test_a_foul_by_the_other_team_stays_and_the_move_goes_on():   # Quill 42', ten steps with a free kick
    steps = goal_buildup(DEMO.events, DEMO.event(601))
    assert [e.id for e in steps] == [586, 588, 589, 591, 593, 594, 595, 597, 599, 600]
    assert steps[6].type == EventType.FOUL and steps[6].team_id == "RMU"

def test_a_shot_straight_after_the_ball_changed_hands_is_only_the_shot():   # Rasmus 47'
    assert ids_for(692) == [691]

def test_the_shot_ends_where_it_was_recorded():
    assert (DEMO.event(600).end_x, DEMO.event(600).end_y) == (105.0, 34.0)
    assert goal_buildup(DEMO.events, DEMO.event(692))[-1].end_x == 0.0

def test_only_goal_lines_carry_a_build_up():
    goal = event_line(DEMO, DEMO.event(601))
    assert [s.id for s in goal.buildup] == ids_for(601) and goal.buildup[-1].lines["en"].startswith("Marek Quill")
    assert event_line(DEMO, DEMO.event(600)).buildup is None
```

Hand-built cases with a small helper `ev(id, type, team="NBR", outcome=True, **kw) -> Event` (t = id, period 1, x 50, y 34, `player_id` "NBR-9" or "RMU-4" by team); goals get `detail={"shot_id": float(shot.id)}`:

- `test_events_after_the_goal_are_never_used`: pass, shot, goal, then a later NBR pass and an RMU pass in the same list; result is `[pass, shot]`.
- `test_an_own_failed_pass_ends_the_move`: failed pass, completed pass, shot, goal; result `[completed pass, shot]`.
- `test_an_earlier_own_shot_ends_the_move`: pass, missed shot, pass, shot, goal; result `[second pass, shot]`.
- `test_a_kickoff_ends_the_move_and_is_not_kept`: kickoff, pass, shot, goal; result `[pass, shot]`.
- `test_pressures_cards_and_failed_challenges_are_skipped`: own pass, RMU pressure, RMU failed tackle, RMU card, own carry, shot, goal; result `[pass, carry, shot]`.
- `test_the_other_teams_won_ball_ends_the_move`: own pass, RMU successful interception, own pass, shot, goal; result `[second pass, shot]`.
- `test_a_goal_without_a_shot_ends_with_the_goal_itself`: pass, goal with no `shot_id`; result `[pass, goal]`.

Update the protocol test: the key set gains `"buildup"`.

- [ ] **Step 2: Run them and see them fail**

Run: `.venv/Scripts/python -m pytest tests/api/test_api_buildup.py tests/api/test_api_timeline.py -q`
Expected: FAIL (`ModuleNotFoundError: jahbadh.api.buildup`, and the protocol key set).

- [ ] **Step 3: Implement `goal_buildup` in `src/jahbadh/api/buildup.py`**

A module docstring stating the rule in plain words. Only events before the goal in `events` are looked at (find the goal by id, scanning from the end). The anchor is the event with id `detail["shot_id"]` before the goal, or the goal itself when there is none. Walk backwards from just before the anchor, with `team` = the goal's team:

- the other team's PASS, CARRY or SHOT, or its TACKLE / INTERCEPTION with `outcome` true: stop, not kept;
- the other team's FOUL: keep (the free kick), go on; anything else by the other team: skip;
- own SHOT, own PASS or CARRY with `outcome` false, own FOUL: stop, not kept;
- own TACKLE / INTERCEPTION with `outcome` true: keep, then stop (it starts the move);
- own PASS or CARRY with `outcome` true: keep;
- KICKOFF, PERIOD_END or GOAL by either team: stop, not kept;
- anything else (pressures, failed challenges, cards, substitutions, formation and press changes): skip.

Return the kept events in match order with the anchor last.

- [ ] **Step 4: Add `buildup: list["EventLine"] | None = None` to `EventLine`** (with a short comment: goals only, the steps of the move in order, the shot last), and in `event_line` set it to `[event_line(match, s) for s in goal_buildup(match.events, e)]` when `e.type == EventType.GOAL`.

- [ ] **Step 5: Run the tests and see them pass**

Run: `.venv/Scripts/python -m pytest tests/api -q`
Expected: all pass.

- [ ] **Step 6: Hand over for commit**

Files: `src/jahbadh/api/buildup.py`, `src/jahbadh/api/stream.py`, `src/jahbadh/api/timeline.py`, `tests/api/test_api_buildup.py`, `tests/api/test_api_timeline.py`. Summary: `feat(api): send each goal's build-up with its event line`. Wait for "committed".

---

### Task 2: The browser's replay rules and geometry

**Files:**
- Modify: `web/src/api/types.ts` (`EventLine`), `web/src/pitch/layers.ts`, `web/src/state/labels.ts`
- Create: `web/src/state/goals.ts`
- Test: `web/src/state/goals.test.ts` (new), `web/src/pitch/layers.test.ts`

**Interfaces:**
- Consumes: `EventLine.buildup` from Task 1.
- Produces (all exported):
  - `types.ts`: `buildup?: EventLine[] | null` on `EventLine`.
  - `goals.ts`: `GOAL_FRESH_S = 60`, `HOLD_MS = 4000`; `type GoalChip = { goalId: number; minute: number; teamId: string; label: string }`; `goalChips(events: EventLine[], info: MatchInfo): GoalChip[]`; `freshGoal(events: EventLine[], clock: number): EventLine | null`; `goalOfItem(item: FeedItem, eventsById: Record<number, EventLine>): EventLine | null`; `stepMs(steps: number): number`; `newestUnwatched(chips: GoalChip[], watched: ReadonlySet<number>): GoalChip | null`; `type ReplayInputs = { request: number | null; lineGoal: number | null; lineDone: boolean; fresh: number | null; watched: ReadonlySet<number>; overview: boolean; phone: boolean }`; `pickReplay(i: ReplayInputs): number | null`.
  - `layers.ts`: `type ReplayStep = { id: number; kind: "pass" | "carry" | "shot" | "point"; x1: number; y1: number; x2: number; y2: number; shirt: string | null; team: string }`; `replaySteps(steps: EventLine[], info: MatchInfo): ReplayStep[]`.
  - `labels.ts`: `GOAL_LABELS = { row: "Goal build-ups", title: (m: number) => \`How the ${m}' goal was built\`, fromData: "The move, from the match data", noBuildUp: "No passes or carries before the shot in this move.", cardHint: (m: number) => \`${m}' goal build-up\` }`.

- [ ] **Step 1: Write the failing tests**

`goals.test.ts` (fixtures from `test-fixtures.ts`; build `EventLine`s like `layers.test.ts` does):

- `goalChips`: two GOAL lines (NBR-9 at minute 15, RMU-33 at 47) give `["15' 9", "47' 33"]` with the fixture names "Player 9" and "Player 33" (the label is the minute and the last word of the scorer's name), in match order with their team ids; a goal whose scorer isn't on either team sheet uses the team id.
- `freshGoal`: a goal at t 900 is fresh at clock 950 and gone at clock 961; of two fresh goals the newest wins; no goals gives null.
- `goalOfItem`: a `goal` moment whose `event_ids` are `[shot, goal]` returns the goal line; a `big_chance` moment returns null; a goal moment whose goal line is missing from `eventsById` returns null.
- `stepMs`: `stepMs(1) == 800`, `stepMs(10) == 600`, `stepMs(20) == 350`.
- `newestUnwatched`: returns the newest chip if unwatched; returns null when the newest is watched even if an older one isn't.
- `pickReplay`: a chip request beats a goal line and a fresh goal; a goal line plays until `lineDone`; a fresh goal plays only when `overview` and not `phone` and not in `watched`; otherwise null.

`layers.test.ts`, new `describe("replaySteps")`:

- a pass (50, 60) to (70, 40) by NBR-9 gives `{ kind: "pass", x1: 50, y1: 8, x2: 70, y2: 28, shirt: "9", team: "NBR" }`.
- a shot (99, 33) to (105, 34) gives kind `"shot"` ending at `x2 105, y2 34`.
- a tackle, a foul and a GOAL line give kind `"point"` with `x2 == x1`, `y2 == y1`.
- shirt numbers only at a new player's first touch: NBR-9 pass, NBR-10 carry, NBR-10 pass give `["9", "10", null]`; a foul by RMU-4 gives `null`.

- [ ] **Step 2: Run them and see them fail**

Run: `npm --prefix web run test`
Expected: FAIL (missing exports).

- [ ] **Step 3: Implement** `goals.ts`, `replaySteps` and `GOAL_LABELS` to the interfaces above. `stepMs(n) = clamp(6000 / n, 350, 800)`, rounded. `replaySteps` uses the raw broadcast frame (`toSvg`, like `eventLayer`): PASS and CARRY with an end are arrows of their kind, a SHOT with an end is `"shot"`, everything else is a `"point"`. A step's `shirt` is the player's shirt when the player is on the goal's team (the last step's `team_id`) and differs from the previous shirt-carrying player, else null.

- [ ] **Step 4: Run the tests, build and lint**

Run: `npm --prefix web run test`, `npm --prefix web run build`, `npm --prefix web run lint`
Expected: all green.

- [ ] **Step 5: Hand over for commit**

Files: `web/src/api/types.ts`, `web/src/state/goals.ts`, `web/src/state/goals.test.ts`, `web/src/pitch/layers.ts`, `web/src/pitch/layers.test.ts`, `web/src/state/labels.ts`. Summary: `feat(web): rules and geometry for goal replays`. Wait for "committed".

---

### Task 3: The replay on the tactical view (desktop)

**Files:**
- Create: `web/src/components/GoalReplay.tsx`, `web/src/components/GoalChips.tsx`
- Modify: `web/src/components/Pitch.tsx`, `web/src/components/TacticalView.tsx`, `web/src/App.tsx`, `web/src/styles.css`

**Interfaces:**
- Consumes: everything Task 2 produces.
- Produces: `Pitch` takes `children?: ReactNode`, drawn inside the SVG after the event arrows and points. `GoalReplay.tsx` exports `ReplayDrawing({ steps: ReplayStep[]; info: MatchInfo; ms: number })` (an SVG `<g>`) and `ReplaySteps({ steps: EventLine[]; language: Language; ms: number; onDone: () => void })` (the numbered list). `GoalChips({ chips: GoalChip[]; glowId: number | null; onPick: (goalId: number) => void; info: MatchInfo })`. `TacticalView` gains `replay: { goal: EventLine; nonce: number } | null`, `chips: GoalChip[]`, `glowId: number | null`, `onChip: (goalId: number) => void`, `onReplayDone: (goalId: number) => void`, `language: Language`.

- [ ] **Step 1: Draw the replay.** `ReplayDrawing` draws each step in the order given: passes solid, carries dashed, in the team colour (`var(--home)` / `var(--away)`), with arrowheads in the same colour (one marker per colour, since a marker can't take the line's colour everywhere); the shot thicker in `var(--amber)` with a dot at its start so a 0.1 m shot still shows; points as small dots; a shirt number in a small team-colour dot at each step's start where `shirt` is set. Step i appears at `i * ms` through CSS (`animation-delay` inline, `pathLength="1"` and a dash-offset draw for arrows, a fade for points). `ReplaySteps` lists each step as its number and `lines[language]` (each line with `dir="rtl"` in Arabic), lighting up at the same delays; a single-step move adds `GOAL_LABELS.noBuildUp`. A hidden hold element whose non-moving animation lasts `steps * ms + HOLD_MS` calls `onDone` on `animationend`, so no timers are needed. Under `prefers-reduced-motion: reduce`, the drawing and the list show at once (no delays, no dash draw); the hold still runs.

- [ ] **Step 2: Wire `TacticalView`.** With a replay and nothing selected: title `GOAL_LABELS.title(goal.minute)`, the pitch shows only the replay (no formations or heatmap), tiles as today. With a replay and a selected line: the evidence view as today plus the replay drawn on the same pitch and `GOAL_LABELS.fromData` above the step list. Key the replay by `${goal.id}-${nonce}` so a repeat restarts it. The chip row (`GOAL_LABELS.row`) sits under the pitch whenever there is at least one goal; a chip is in its team's colour and glows when its id is `glowId`.

- [ ] **Step 3: Wire `App`.** State: `watched: Set<number>`, `request: { goalId: number; nonce: number } | null`, `lineDone: string | null` (the selection key whose goal-line replay finished). Derived in render with Task 2's helpers: `chips`, `fresh = freshGoal(desk.events, desk.clock)`, `lineGoal = selected ? goalOfItem(selected.item, desk.eventsById) : null`, `goalId = pickReplay({...})`, then `goal = goalId === null ? null : desk.eventsById[goalId] ?? null` (a goal the stream no longer has plays nothing), `glowId = newestUnwatched(chips, watched)?.goalId ?? null`. `onChip` sets `request` with a new nonce; `onReplayDone(id)` adds `id` to `watched`, clears `request`, and sets `lineDone` to the current selection key when a goal line was playing. Phone wiring is Task 4: pass `phone` into `pickReplay` already.

- [ ] **Step 4: Test, build and lint**

Run: `npm --prefix web run test`, `npm --prefix web run build`, `npm --prefix web run lint`
Expected: all green.

- [ ] **Step 5: See it in the browser** (replay of the showcase; restart the `api` preview so it serves the new build). At 1440 wide, check and screenshot:
  1. On the overview, Quill's 42' goal plays by itself: ten steps in order, the foul as a point, the gold shot to (105, 34), the step list lighting up; then after the hold the formations come back and the "42' Quill" chip is in the row.
  2. Tapping the 27' chip replays that goal; tapping it again restarts it.
  3. With another line's evidence open when a goal lands, the evidence stays and the new chip glows.
  4. Selecting a 42' goal line shows its evidence, "The move, from the match data" and the replay, then the evidence stays.
  5. Rasmus 47': one step and the "No passes or carries" line.
  6. Arabic: step lines read right to left. Console has no errors.

- [ ] **Step 6: Hand over for commit**

Files: the five web files above plus the two new components. Summary: `feat(web): play each goal's build-up on the tactical view`. Wait for "committed".

---

### Task 4: Phones, then the whole suite

**Files:**
- Modify: `web/src/components/TacticalCard.tsx`, the layouts that use it (`web/src/components/layouts/FanLayout.tsx`, `AnalystLayout.tsx`, `PlayerWatchLayout.tsx` if it folds the view), `web/src/App.tsx`, `web/src/styles.css`

**Interfaces:**
- Consumes: `newestUnwatched`, `GOAL_LABELS.cardHint` (Task 2); `request` and `onChip` (Task 3).
- Produces: `TacticalCard` takes `hint?: string | null` (shown glowing in the summary when set) and `onOpen?: () => void` (called when the viewer opens it).

- [ ] **Step 1: Implement.** The card never opens by itself for a goal (it still opens for a selected line, as today). While the newest goal is unwatched, the summary shows `GOAL_LABELS.cardHint(minute)` with the glow. Opening the card while that hint shows requests that goal's replay (the same path as a chip tap). The chip row is inside the card under the pitch, as on desktop.

- [ ] **Step 2: Test, build and lint**

Run: `npm --prefix web run test`, `npm --prefix web run build`, `npm --prefix web run lint`
Expected: all green.

- [ ] **Step 3: See it on a phone width** (375 wide, each of Fan, Analyst and Player watch): a goal lands, the card stays folded and its header glows with "42' goal build-up"; opening it plays the replay; no sideways scroll (`scrollWidth` 375). Then reset the viewport.

- [ ] **Step 4: The whole suite**

Run in the background: `.venv/Scripts/python -m pytest -q` (about 9 minutes). Expected: the 21 Oct count (584 passed, 4 skipped, 1 xfailed) plus the new build-up tests, nothing failing. Web: `npm --prefix web run test` (76 plus the new tests), build and lint green.

- [ ] **Step 5: Hand over for commit**

Files: `TacticalCard.tsx`, the touched layouts, `App.tsx`, `styles.css`. Summary: `feat(web): a goal build-up hint on the folded phone card`. Wait for "committed". Then record the task lines and the user's decisions in the Plan 4 ledger.
