# Jahbadh Plan 1: Data Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A seeded synthetic match simulator (events + 1 Hz tracking) and a pure-Python tactical analytics library whose every result carries evidence IDs.

**Architecture:** One Python package `jahbadh` under `src/`. The simulator runs a 1-second tick loop: a movement model moves 22 players toward formation slots, and a possession state machine emits events. Output is a `Match` (metadata, event list, tracking DataFrame) saved as JSON + Parquet. The analytics modules take a `Match` and return `Metric` objects. No LLMs anywhere in this plan.

**Tech Stack:** Python 3.13, numpy, pandas, pyarrow, pydantic v2, pytest, matplotlib (preview script only).

**Spec:** `docs/superpowers/specs/2026-10-17-jahbadh-design.md`

### How the build is split

| Plan | Covers | Roadmap days |
|---|---|---|
| **1. Data foundation (this file)** | Schemas, simulator, storyline knobs, dataset export, analytics library | 1 to 3 |
| 2. Agents | Foundry setup, Agent Framework, Analyst, Tactical, Writers, Referee, Persona, Localization, orchestrator | 4 to 6 |
| 3. Desk | FastAPI + SSE, live and replay modes, React desk UI | 6 to 8 |
| 4. Ship | Eval harness, Azure Container Apps deploy, CI, README, video, submission | 8 to 10 |

Plans 2 to 4 get written when we reach them, because they depend on what Plan 1's interfaces turn out to be and on what the Foundry/Agent Framework APIs actually do on your subscription.

## Global Constraints

- Python 3.13. Dependencies: numpy, pandas, pyarrow, pydantic>=2, matplotlib. Dev: pytest. Nothing else without a reason.
- Randomness only through a `numpy.random.Generator` created from the match seed and passed down. Never `random` or global numpy state. Same seed means an identical match.
- Pitch is 105 x 68 metres, origin bottom-left. **Home always attacks toward x = 105 and away toward x = 0, for the whole match (no side switch at half time).** Match length is exactly 5400 seconds: period 1 is t in [0, 2700), period 2 is [2700, 5400). No stoppage time.
- All teams, players and names are fictional. No real clubs, players or badges.
- Every analytics result is a `Metric` with evidence (event IDs and/or a tracking time range).
- Docs and user-facing text: friendly, and no em dashes.
- **Commits:** the user commits every change themselves. Each task ends with a *suggested* commit (files + message). Never run `git commit` or `git push`.
- Cards are yellow only. No red cards, injuries or extra time (YAGNI).

## Review Focus

1. **Empty windows:** a metric over a window with no qualifying events (PPDA with zero defensive actions, field tilt with no final-third passes) should return `value=None` with an explanatory `note`, not crash or return inf/NaN. Tested in Tasks 9 and 10.
2. **Subbed-off players:** heatmaps, shape and pass networks over windows spanning a substitution only use seconds the player was on the pitch, and a subbed-on player appears from his first second. Tested in Task 11.
3. **Away team direction:** metrics for the away team (attacking toward x = 0) should mirror correctly. A mirrored match gives mirrored results. Tested in Task 9.
4. **Positions off the pitch:** movement noise must never produce x outside [0, 105] or y outside [0, 68]. Tested in Task 4.
5. **Save/load round trip:** a saved and reloaded match is equal to the original, including `None` fields and dtypes. Tested in Task 8.

---

## File Structure

```
pyproject.toml
src/jahbadh/
  __init__.py
  schemas.py            # Team, Player, Event, EventType, Match, Metric, ScriptedChange
  pitch.py              # pitch constants, clamp, normalise_x (attacking direction), zones
  simulator/
    __init__.py         # re-exports simulate_match
    formations.py       # slot coordinates per formation
    teams.py            # fictional team + player generation
    xg.py               # shot xG model
    movement.py         # per-tick player movement
    engine.py           # tick loop, possession state machine -> events + tracking
    storyline.py        # applying ScriptedChange during the loop, DEMO_STORYLINE
    io.py               # save_match / load_match / export_schema
    __main__.py         # CLI: python -m jahbadh.simulator
  analytics/
    __init__.py
    base.py             # window helpers, metric id builder, team direction helpers
    shots.py            # xg_total, xg_timeline
    territory.py        # field_tilt, ppda
    momentum.py         # momentum
    positional.py       # heatmap, shape, average_positions
    overloads.py        # zone_overloads
    networks.py         # pass_network
    compare.py          # before_after
scripts/preview_match.py  # renders heatmaps/shape to PNG for eyeballing
tests/                    # mirrors src layout
```

---

### Task 1: Project scaffold and core schemas

**Files:**
- Create: `pyproject.toml`, `src/jahbadh/__init__.py`, `src/jahbadh/schemas.py`, `src/jahbadh/pitch.py`, `.env.example` (empty placeholder with a comment)
- Test: `tests/test_schemas.py`, `tests/test_pitch.py`

**Interfaces:**
- Produces (in `jahbadh.schemas`):
  - `class TeamTactics(BaseModel)`: `press_height: float`, `width: float`, `tempo: float`, `directness: float`, all constrained to [0, 1].
  - `class Player(BaseModel)`: `id: str` (format `"{team_id}-{shirt}"`), `team_id: str`, `name: str`, `shirt: int`, `role: Literal["GK","CB","FB","DM","CM","AM","W","ST"]`, `starter: bool`.
  - `class Team(BaseModel)`: `id: str` (3 uppercase letters), `name: str`, `formation: str`, `tactics: TeamTactics`, `players: list[Player]`.
  - `class EventType(StrEnum)`: `KICKOFF, PASS, CARRY, SHOT, GOAL, TACKLE, INTERCEPTION, PRESSURE, FOUL, CARD, SUBSTITUTION, FORMATION_CHANGE, TACTIC_CHANGE, PERIOD_END`.
  - `class Event(BaseModel)`: `id: int`, `t: float`, `period: Literal[1,2]`, `team_id: str`, `player_id: str | None`, `type: EventType`, `x: float`, `y: float`, `end_x: float | None = None`, `end_y: float | None = None`, `outcome: bool | None = None`, `xg: float | None = None`, `related_player_id: str | None = None` (pass receiver, sub coming on), `detail: dict[str, str | float] = {}`. Property `minute -> int` = `int(t // 60) + 1`.
  - `class ScriptedChange(BaseModel)`: `minute: int`, `team_id: str`, `kind: Literal["formation","press_height","substitution"]`, `value: str | float | None = None`, `player_out: str | None = None`, `player_in: str | None = None`.
  - `class MatchMeta(BaseModel)`: `match_id: str`, `seed: int`, `home: Team`, `away: Team`, `storyline: list[ScriptedChange]`, `score: dict[str, int]`.
  - `@dataclass class Match`: `meta: MatchMeta`, `events: list[Event]`, `tracking: pd.DataFrame` (columns `t:int, entity_id:str, team_id:str, x:float, y:float`, ball rows use `entity_id="BALL"`, `team_id="BALL"`). Methods: `team(team_id) -> Team`, `opponent_id(team_id) -> str`, `events_of(type: EventType | None = None, team_id: str | None = None, start: float = 0, end: float = 5400) -> list[Event]`, `event(id: int) -> Event` (KeyError if missing).
  - `class Metric(BaseModel)`: `id: str`, `name: str`, `subject: str` (team or player id, or `"MATCH"`), `window: tuple[float, float]`, `value: float | None`, `unit: str`, `evidence_event_ids: list[int] = []`, `evidence_frames: tuple[int, int] | None = None`, `data: dict = {}`, `note: str | None = None`.
- Produces (in `jahbadh.pitch`): `LENGTH = 105.0`, `WIDTH = 68.0`, `clamp(x: float, y: float) -> tuple[float, float]`, `attack_x(x: float, team_is_home: bool) -> float` (returns x as seen by a team attacking toward 105, i.e. `x` for home, `105 - x` for away), `lane(y: float, team_is_home: bool) -> Literal["left","centre","right"]` (left/right from the attacking team's point of view, thirds of the width), `third(ax: float) -> Literal["defensive","middle","final"]` (on an `attack_x` value, splits at 35 and 70).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_schemas.py
def test_event_minute_is_one_based():
    e = Event(id=1, t=59.9, period=1, team_id="NBR", player_id="NBR-9", type=EventType.PASS, x=50, y=30)
    assert e.minute == 1
    assert Event(**{**e.model_dump(), "t": 60.0}).minute == 2

def test_tactics_reject_out_of_range():
    with pytest.raises(ValidationError):
        TeamTactics(press_height=1.2, width=0.5, tempo=0.5, directness=0.5)

def test_match_event_lookup_and_filter(tiny_match):   # fixture in tests/conftest.py builds a 2-team match with 3 hand-written events
    assert tiny_match.event(2).type == EventType.SHOT
    assert [e.id for e in tiny_match.events_of(EventType.PASS, team_id="NBR")] == [1]
    with pytest.raises(KeyError):
        tiny_match.event(999)
    assert tiny_match.opponent_id("NBR") == "RMU"

# tests/test_pitch.py
def test_attack_x_mirrors_for_away():
    assert attack_x(90, team_is_home=True) == 90
    assert attack_x(90, team_is_home=False) == 15

def test_lane_is_from_attacker_view():
    assert lane(60, team_is_home=True) == "left"    # home attacks +x, so high y is their left
    assert lane(60, team_is_home=False) == "right"

def test_clamp_and_third():
    assert clamp(-3, 70) == (0.0, 68.0)
    assert third(20) == "defensive" and third(50) == "middle" and third(80) == "final"
```

- [ ] **Step 2:** Run `pytest -q`. Expected: FAIL (import errors).
- [ ] **Step 3:** Write `pyproject.toml` (src layout, project name `jahbadh`, deps above, `[project.optional-dependencies] dev = ["pytest"]`, pytest `testpaths = ["tests"]`). Then implement `schemas.py`, `pitch.py` and the `tiny_match` fixture in `tests/conftest.py`. Set up with `py -3.13 -m venv .venv`, then `.venv\Scripts\pip install -e .[dev]`.
- [ ] **Step 4:** Run `pytest -q`. Expected: all pass.
- [ ] **Step 5: Suggest commit** (the user commits): files `pyproject.toml src/ tests/ .env.example`, message `chore: scaffold package and core match schemas`.

---

### Task 2: Formations and fictional teams

**Files:**
- Create: `src/jahbadh/simulator/__init__.py` (empty for now), `src/jahbadh/simulator/formations.py`, `src/jahbadh/simulator/teams.py`
- Test: `tests/simulator/test_formations.py`, `tests/simulator/test_teams.py`

**Interfaces:**
- Consumes: `Team`, `Player`, `TeamTactics` from Task 1.
- Produces:
  - `FORMATIONS: dict[str, list[tuple[str, float, float]]]`: for each of `"4-3-3"`, `"4-4-2"`, `"4-2-3-1"`, `"3-4-3"`, `"3-5-2"`, exactly 11 `(role, ax, y)` slots in attacking coordinates (home view, GK first at ax≈5). Defensive line ax≈25, midfield ≈45, attack ≈70 (these are the *in-possession, ball at halfway* base positions).
  - `slots_for(formation: str) -> list[tuple[str, float, float]]` (raises `ValueError` for unknown formation).
  - `make_team(team_id: str, name: str, formation: str, tactics: TeamTactics, rng: np.random.Generator) -> Team`: 11 starters with roles taken from the formation slots in order, shirts unique 1 to 99, plus 5 subs (one of each of GK, CB, CM, W, ST). Names come from small built-in fictional first/last name lists combined via `rng`.
  - `DEFAULT_TEAMS: tuple[...]`: two fixed specs for the demo: `("NBR", "Northbridge FC", "4-3-3", press_height=0.7, width=0.6, tempo=0.6, directness=0.4)` and `("RMU", "Rivermouth United", "4-3-3", press_height=0.45, width=0.55, tempo=0.5, directness=0.55)`.

- [ ] **Step 1: Write the failing tests**

```python
def test_every_formation_has_11_slots_and_one_gk():
    for name, slots in FORMATIONS.items():
        assert len(slots) == 11, name
        assert [r for r, _, _ in slots].count("GK") == 1
        assert all(0 <= ax <= 105 and 0 <= y <= 68 for _, ax, y in slots)

def test_back_line_size_matches_formation_name():
    assert sum(1 for r, _, _ in slots_for("4-3-3") if r in ("CB", "FB")) == 4
    assert sum(1 for r, _, _ in slots_for("3-4-3") if r in ("CB", "FB")) == 3

def test_make_team_is_deterministic_and_complete():
    t1 = make_team("NBR", "Northbridge FC", "4-3-3", TACTICS, np.random.default_rng(7))
    t2 = make_team("NBR", "Northbridge FC", "4-3-3", TACTICS, np.random.default_rng(7))
    assert t1 == t2
    assert len(t1.players) == 16 and sum(p.starter for p in t1.players) == 11
    assert len({p.shirt for p in t1.players}) == 16
    assert all(p.id == f"NBR-{p.shirt}" for p in t1.players)

def test_unknown_formation_raises():
    with pytest.raises(ValueError):
        slots_for("2-3-5")
```

- [ ] **Step 2:** Run `pytest tests/simulator -q`. Expected: FAIL.
- [ ] **Step 3:** Implement `formations.py` and `teams.py`.
- [ ] **Step 4:** Run `pytest -q`. Expected: all pass.
- [ ] **Step 5: Suggest commit:** `feat(sim): add formations and fictional team generator`.

---

### Task 3: xG model

**Files:**
- Create: `src/jahbadh/simulator/xg.py`
- Test: `tests/simulator/test_xg.py`

**Interfaces:**
- Produces: `shot_xg(ax: float, y: float, under_pressure: bool = False) -> float`, where `ax` is in attacking coordinates (goal at ax = 105, posts at y = 30.34 and 37.66). Logistic model: `logit = -1.0 - 0.10 * distance_m + 1.5 * goal_angle_rad - (0.4 if under_pressure else 0)`, where `goal_angle_rad` is the angle subtended by the two posts from the shot location. The result is clamped to [0.01, 0.95].

- [ ] **Step 1: Write the failing tests**

```python
def test_penalty_spot_is_around_quarter():
    assert 0.20 <= shot_xg(94, 34) <= 0.30

def test_long_range_central_is_low():
    assert shot_xg(80, 34) < 0.06

def test_closer_and_central_is_higher():
    assert shot_xg(100, 34) > shot_xg(94, 34) > shot_xg(94, 10)

def test_pressure_lowers_xg_and_bounds_hold():
    assert shot_xg(94, 34, under_pressure=True) < shot_xg(94, 34)
    assert 0.01 <= shot_xg(104.9, 34) <= 0.95
```

- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement `shot_xg`.
- [ ] **Step 4:** Run the tests. Expected: PASS.
- [ ] **Step 5: Suggest commit:** `feat(sim): add distance/angle xG model`.

---

### Task 4: Movement model

**Files:**
- Create: `src/jahbadh/simulator/movement.py`
- Test: `tests/simulator/test_movement.py`

**Interfaces:**
- Consumes: `slots_for`, `clamp`, `attack_x`, `TeamTactics`.
- Produces:
  - `@dataclass class TeamState`: `team_id: str`, `is_home: bool`, `formation: str`, `tactics: TeamTactics`, `on_pitch: list[str]` (player ids, index-aligned with the formation's slots), `pos: np.ndarray` (shape `(11, 2)`, pitch coordinates).
  - `target_positions(team: TeamState, ball: tuple[float, float], in_possession: bool) -> np.ndarray` with shape `(11, 2)`.
  - `step_positions(team: TeamState, ball: tuple[float, float], in_possession: bool, rng: np.random.Generator, dt: float = 1.0) -> None`, which moves `team.pos` in place.

Behaviour (the starting constants; tune only if a test in Task 7 needs it):
- Targets start from the formation slots in attacking coordinates. The whole block shifts along ax by `0.5 * (ball_ax - 52.5)`, plus `+8` when in possession. Out of possession it also gets `+10 * (press_height - 0.5)` and is squeezed toward the ball's y by a factor `0.3 * (1 - width)`. In possession, y spreads away from 34 by a factor `1 + 0.3 * width`. The GK stays within ax in [2, 18]. Then convert back to pitch coordinates for away teams.
- Out of possession, the 1 player nearest the ball (2 players if `press_height > 0.6`) targets the ball itself.
- Each tick a player moves toward its target by at most `7.0 * dt` m, plus Gaussian noise with sd 0.8 m. Then clamp.

- [ ] **Step 1: Write the failing tests**

```python
def test_block_pushes_up_when_ball_advances(home_state):
    back = target_positions(home_state, ball=(30, 34), in_possession=True)[:, 0].mean()
    fwd = target_positions(home_state, ball=(80, 34), in_possession=True)[:, 0].mean()
    assert fwd - back > 20

def test_away_team_targets_are_mirrored(home_state, away_state_same_shape):
    h = target_positions(home_state, ball=(52.5, 34), in_possession=True)
    a = target_positions(away_state_same_shape, ball=(52.5, 34), in_possession=True)
    assert np.allclose(a[:, 0], 105 - h[:, 0], atol=1e-6)

def test_nearest_defender_presses_ball(home_state):
    t = target_positions(home_state, ball=(40, 20), in_possession=False)
    assert np.min(np.hypot(t[:, 0] - 40, t[:, 1] - 20)) < 0.5

def test_speed_cap_and_never_off_pitch(home_state):
    rng = np.random.default_rng(1)
    for ball in [(0, 0), (105, 68), (105, 0)] * 50:
        before = home_state.pos.copy()
        step_positions(home_state, ball, in_possession=False, rng=rng)
        assert (np.hypot(*(home_state.pos - before).T) <= 7.0 + 4 * 0.8).all()
        assert (home_state.pos[:, 0] >= 0).all() and (home_state.pos[:, 0] <= 105).all()
        assert (home_state.pos[:, 1] >= 0).all() and (home_state.pos[:, 1] <= 68).all()
```

- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement `movement.py`.
- [ ] **Step 4:** Run the tests. Expected: PASS.
- [ ] **Step 5: Suggest commit:** `feat(sim): add formation-slot movement model`.

---

### Task 5: Match engine (events + tracking)

**Files:**
- Create: `src/jahbadh/simulator/engine.py`
- Modify: `src/jahbadh/simulator/__init__.py` (export `simulate_match`)
- Test: `tests/simulator/test_engine.py`

**Interfaces:**
- Consumes: Tasks 1 to 4.
- Produces: `simulate_match(seed: int, match_id: str | None = None, storyline: list[ScriptedChange] | None = None, home_spec=DEFAULT_TEAMS[0], away_spec=DEFAULT_TEAMS[1]) -> Match`. `match_id` defaults to `f"match-{seed:03d}"`. The storyline is accepted but applied in Task 6 (here it is passed through to `meta`).

Tick loop: for each integer `t` from 0 to 5399, apply the steps below.

1. At t = 0 and t = 2700, emit `KICKOFF`: home kicks off at t = 0, away at t = 2700, with the ball at (52.5, 34). At t = 2699, emit `PERIOD_END`.
2. If a dead-ball pause is active, decrement it and only move players. Pauses: 20 to 40 s after the ball goes out of play, 25 to 45 s after a foul, 60 s after a goal.
3. Otherwise the **carrier acts** with probability `0.30 + 0.25 * tempo`:
   - Shot if `ax > 80` with probability `min(0.5, 2.0 * shot_xg(...))`. Pressure means an opponent is within 2.5 m. Emit `SHOT` with `xg`, then `GOAL` (same t, `related` to the shot via `detail["shot_id"]`) with probability `xg`. After a goal, kick off to the other team. After a miss, possession goes to the opponent GK with probability 0.6, otherwise the ball goes out.
   - Else a carry with probability 0.15: move 3 to 8 m toward goal with jitter, and emit `CARRY`.
   - Else a pass. Weight teammates by `exp(directness * forward_gain / 15) * openness`, where `openness = min(1, nearest_opponent_dist / 5)`. Success probability is `0.93 - 0.20 * (length / 40) - 0.15 * pressured - 0.08 * (target in final third)`, clamped to [0.3, 0.97]. On success, emit `PASS` (outcome True, `related_player_id` = receiver) and the receiver becomes the carrier. On failure, 70% of the time the opponent nearest the target emits `INTERCEPTION` and takes possession. Otherwise `PASS` outcome False and the ball goes out (dead ball, opponent restarts).
4. **Defending team**, every non-paused tick: if an opponent is within 2.5 m of the carrier, emit `PRESSURE` with probability `0.25 + 0.4 * press_height`. Then attempt a `TACKLE` with probability 0.06 (success 0.5 means a possession change). Then a `FOUL` with probability 0.012, which a `CARD` (`detail["colour"] = "yellow"`) follows with probability 0.12. Max one yellow per player, and a second foul by a booked player gets no card (no reds).
5. The ball follows the carrier (or the pass end point). Move both teams with `step_positions`. Append 23 tracking rows (on-pitch players + ball).

Event IDs start at 1 and increase. `meta.score` counts `GOAL` events.

- [ ] **Step 1: Write the failing tests**

```python
@pytest.fixture(scope="module")
def m():
    return simulate_match(seed=42)

def test_same_seed_same_match_different_seed_differs():
    a, b, c = simulate_match(1), simulate_match(1), simulate_match(2)
    assert [e.model_dump() for e in a.events] == [e.model_dump() for e in b.events]
    pd.testing.assert_frame_equal(a.tracking, b.tracking)
    assert [e.model_dump() for e in a.events] != [e.model_dump() for e in c.events]

def test_tracking_shape(m):
    assert m.tracking["t"].min() == 0 and m.tracking["t"].max() == 5399
    assert (m.tracking.groupby("t").size() == 23).all()
    assert list(m.tracking.columns) == ["t", "entity_id", "team_id", "x", "y"]

def test_events_are_ordered_unique_and_valid(m):
    ids = [e.id for e in m.events]
    assert ids == list(range(1, len(ids) + 1))
    assert all(a.t <= b.t for a, b in zip(m.events, m.events[1:]))
    assert all(0 <= e.x <= 105 and 0 <= e.y <= 68 for e in m.events)
    assert all(e.xg is not None for e in m.events_of(EventType.SHOT))
    assert all(e.related_player_id for e in m.events_of(EventType.PASS) if e.outcome)

def test_score_matches_goal_events(m):
    for tid in (m.meta.home.id, m.meta.away.id):
        assert m.meta.score[tid] == len(m.events_of(EventType.GOAL, team_id=tid))

def test_kickoffs_and_period_end(m):
    ko = m.events_of(EventType.KICKOFF)
    assert [(e.t, e.team_id) for e in ko][:1] == [(0, m.meta.home.id)]
    assert any(e.t == 2700 and e.team_id == m.meta.away.id for e in ko)
    assert len(m.events_of(EventType.PERIOD_END)) == 1
```

- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement `engine.py`. Keep the possession state in a small `@dataclass _State` (carrier id, possession team, ball xy, pause ticks) and split carrier and defender logic into private functions.
- [ ] **Step 4:** Run `pytest -q`. Expected: all pass, and `simulate_match` takes under 15 s.
- [ ] **Step 5: Suggest commit:** `feat(sim): add tick-based match engine producing events and tracking`.

---

### Task 6: Storyline knobs

**Files:**
- Create: `src/jahbadh/simulator/storyline.py`
- Modify: `src/jahbadh/simulator/engine.py` (call `apply_due_changes` once per tick)
- Test: `tests/simulator/test_storyline.py`

**Interfaces:**
- Produces:
  - `apply_due_changes(t: int, changes: list[ScriptedChange], teams: dict[str, TeamState], match_team: dict[str, Team], emit: Callable[..., Event]) -> None`. Applies every change whose `minute * 60 == t`:
    - `formation`: emit `FORMATION_CHANGE` with `detail={"from": old, "to": new}` and re-map the 11 on-pitch players to the new slots. The GK stays GK. Remaining players are matched to the nearest new slot, by role order.
    - `press_height`: emit `TACTIC_CHANGE` with `detail={"press_height_from": a, "press_height_to": b}`.
    - `substitution`: emit `SUBSTITUTION` with `player_id=player_out` and `related_player_id=player_in`. The sub takes the slot and the current position of the player going off. `ValueError` if `player_out` isn't on the pitch or `player_in` isn't a bench player.
  - `DEMO_STORYLINE: list[ScriptedChange]`: `RMU` substitution at minute 60 (a CM off, a W on), `RMU` formation `"3-4-3"` at minute 60, and `NBR` press_height `0.85` at minute 70.

- [ ] **Step 1: Write the failing tests**

```python
def test_formation_change_event_and_shape():
    m = simulate_match(42, storyline=[ScriptedChange(minute=60, team_id="RMU", kind="formation", value="3-4-3")])
    fc = m.events_of(EventType.FORMATION_CHANGE, team_id="RMU")
    assert len(fc) == 1 and fc[0].t == 3600 and fc[0].detail == {"from": "4-3-3", "to": "3-4-3"}

def test_back_line_goes_from_four_to_three():
    m = simulate_match(42, storyline=[ScriptedChange(minute=60, team_id="RMU", kind="formation", value="3-4-3")])
    def deep_players(start, end):   # RMU outfield players whose mean attacking-x is below 33
        tr = m.tracking[(m.tracking.team_id == "RMU") & m.tracking.t.between(start, end - 1)]
        gk = next(p.id for p in m.meta.away.players if p.role == "GK" and p.starter)
        means = tr[tr.entity_id != gk].groupby("entity_id").x.mean()
        return int(((105 - means) < 33).sum())
    assert deep_players(2700, 3600) == 4
    assert deep_players(3660, 5400) == 3

def test_substitution_swaps_tracking_entity():
    m = simulate_match(42, storyline=DEMO_STORYLINE)
    sub = m.events_of(EventType.SUBSTITUTION)[0]
    tr = m.tracking
    assert tr[(tr.entity_id == sub.player_id)].t.max() == 3599
    assert tr[(tr.entity_id == sub.related_player_id)].t.min() == 3600

def test_bad_substitution_raises():
    with pytest.raises(ValueError):
        simulate_match(42, storyline=[ScriptedChange(minute=10, team_id="RMU", kind="substitution", player_out="RMU-999", player_in="RMU-998")])
```

- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement `storyline.py` and hook it into the engine loop *before* movement on each tick.
- [ ] **Step 4:** Run `pytest -q`. Expected: all pass.
- [ ] **Step 5: Suggest commit:** `feat(sim): add scripted storyline changes (formation, press, subs)`.

---

### Task 7: Realism calibration

**Files:**
- Create: `tests/simulator/test_realism.py`
- Modify: engine and movement constants only, if needed

**Interfaces:** none new. This task tunes Task 4 and 5 constants until the realism ranges hold.

- [ ] **Step 1: Write the test.** Ranges are per match with both teams combined, checked on seeds 1 to 5:

```python
RANGES = {
    "passes": (700, 1150), "pass_completion": (0.74, 0.90), "shots": (14, 36),
    "xg_total": (1.4, 4.8), "goals": (0, 8), "fouls": (12, 35), "cards": (0, 9),
    "events_total": (1400, 2800),
}

@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
def test_match_stats_in_top_flight_ranges(seed):
    stats = match_summary(simulate_match(seed))   # helper defined in this test file
    for k, (lo, hi) in RANGES.items():
        assert lo <= stats[k] <= hi, f"seed {seed}: {k}={stats[k]}"
```

Also add `test_both_teams_get_possession`: each team has between 35% and 65% of successful passes.

- [ ] **Step 2:** Run `pytest tests/simulator/test_realism.py -v`. It will likely fail somewhere.
- [ ] **Step 3:** Tune constants (action probability, pass success terms, shot probability, foul probability, pause lengths) until all 5 seeds pass. Record the final constants as named module-level constants at the top of `engine.py`.
- [ ] **Step 4:** Run `pytest -q`. Expected: everything passes, including the earlier tasks.
- [ ] **Step 5: Suggest commit:** `test(sim): calibrate engine against top-flight stat ranges`.

---

### Task 8: Save, load, dataset export and CLI

**Files:**
- Create: `src/jahbadh/simulator/io.py`, `src/jahbadh/simulator/__main__.py`
- Test: `tests/simulator/test_io.py`

**Interfaces:**
- Produces:
  - `save_match(match: Match, out_dir: Path) -> None` writes `meta.json` (`MatchMeta.model_dump_json(indent=2)`), `events.parquet` (one row per event, `detail` stored as a JSON string column) and `tracking.parquet`.
  - `load_match(dir: Path) -> Match`.
  - `export_schema(out_dir: Path) -> None` writes `schema/event.schema.json`, `schema/match_meta.schema.json` (pydantic `model_json_schema()`) and `schema/README.md` describing the coordinate system and tracking columns, in the project's friendly tone.
  - CLI: `python -m jahbadh.simulator --seed 42 [--demo-storyline] [--out data/generated]` writes `data/generated/match-042/` and prints the score plus event and row counts.

- [ ] **Step 1: Write the failing tests**

```python
def test_round_trip_is_exact(tmp_path):
    m = simulate_match(3, storyline=DEMO_STORYLINE)
    save_match(m, tmp_path / "m")
    r = load_match(tmp_path / "m")
    assert r.meta == m.meta
    assert [e.model_dump() for e in r.events] == [e.model_dump() for e in m.events]
    pd.testing.assert_frame_equal(r.tracking, m.tracking)

def test_export_schema_files(tmp_path):
    export_schema(tmp_path)
    assert json.loads((tmp_path / "schema" / "event.schema.json").read_text())["title"] == "Event"
    assert (tmp_path / "schema" / "README.md").exists()

def test_cli_writes_match(tmp_path):
    subprocess.run([sys.executable, "-m", "jahbadh.simulator", "--seed", "42", "--demo-storyline", "--out", str(tmp_path)], check=True)
    assert (tmp_path / "match-042" / "events.parquet").exists()
```

- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement `io.py` and `__main__.py` (argparse).
- [ ] **Step 4:** Run `pytest -q`. Expected: all pass.
- [ ] **Step 5: Suggest commit:** `feat(sim): add match save/load, dataset schema export and CLI`.

---

### Task 9: Analytics base, xG, field tilt and PPDA

**Files:**
- Create: `src/jahbadh/analytics/__init__.py`, `base.py`, `shots.py`, `territory.py`
- Test: `tests/analytics/test_shots.py`, `tests/analytics/test_territory.py`, `tests/analytics/conftest.py`

**Interfaces:**
- Consumes: `Match`, `Event`, `Metric`, `attack_x`, `third`.
- Produces:
  - `base.metric_id(name: str, subject: str, start: float, end: float) -> str` returns `f"{name}:{subject}:{int(start)}-{int(end)}"`.
  - `base.is_home(match: Match, team_id: str) -> bool`.
  - `shots.xg_total(match, team_id, start=0, end=5400) -> Metric` (name `"xg_total"`, unit `"xG"`, evidence is the shot ids).
  - `shots.xg_timeline(match, team_id) -> Metric` (value is the final cumulative xG, `data={"points": [[t, cum_xg], ...]}`).
  - `territory.field_tilt(match, team_id, start=0, end=5400) -> Metric`: the team's share of all **successful passes that start in the passer's final third** (`third(attack_x) == "final"`) within the window. Value in [0, 1], unit `"share"`, evidence is the team's final-third pass ids. `None` plus `note` if there are no final-third passes.
  - `territory.ppda(match, defending_team_id, start=0, end=5400) -> Metric`: the opponent's passes that start in the opponent's defensive 60% (opponent `attack_x < 63`), divided by the defending team's `TACKLE` + `INTERCEPTION` + `FOUL` events located in that same area. Unit `"passes/def_action"`, evidence is the defensive action ids. `None` plus `note` if there are no defensive actions.
- Test helper (in `tests/analytics/conftest.py`): `make_match(events: list[Event], tracking: pd.DataFrame | None = None) -> Match` builds a tiny match from hand-written events so the metric maths can be checked exactly. Its two teams (`NBR` home, `RMU` away, both 4-3-3) are built by hand, not with `make_team`, so the player IDs are predictable: shirts 1 to 16, shirt 1 is the starting GK, shirts 2 to 11 follow the formation's slot order, and 12 to 16 are subs. Also `mirror(match) -> Match`, which swaps home and away and maps x to 105 - x and y to 68 - y.

- [ ] **Step 1: Write the failing tests**

```python
def test_xg_total_sums_and_cites_shots():
    m = make_match([shot(1, "NBR", xg=0.3), shot(2, "NBR", xg=0.1), shot(3, "RMU", xg=0.5)])
    r = xg_total(m, "NBR")
    assert r.value == pytest.approx(0.4) and r.evidence_event_ids == [1, 2]
    assert r.id == "xg_total:NBR:0-5400"

def test_field_tilt_counts_final_third_passes_only():
    # NBR: 3 final-third passes (x=80) + 1 own-half; RMU (away, attacking x=0): 1 final-third pass at x=20
    m = make_match([p(1,"NBR",80), p(2,"NBR",80), p(3,"NBR",80), p(4,"NBR",30), p(5,"RMU",20)])
    assert field_tilt(m, "NBR").value == pytest.approx(0.75)
    assert field_tilt(m, "RMU").value == pytest.approx(0.25)

def test_field_tilt_mirrors(sim_match):
    assert field_tilt(sim_match, "NBR").value == pytest.approx(field_tilt(mirror(sim_match), "NBR").value)

def test_ppda_ratio_and_evidence():
    # RMU makes 10 passes in its own defensive 60%; NBR makes 2 defensive actions there
    m = make_match([p(i, "RMU", 90) for i in range(1, 11)] + [tackle(11, "NBR", 85), intercept(12, "NBR", 80)])
    r = ppda(m, "NBR")
    assert r.value == pytest.approx(5.0) and r.evidence_event_ids == [11, 12]

def test_empty_windows_return_none_with_note():
    m = make_match([p(1, "RMU", 90)])
    assert ppda(m, "NBR").value is None and ppda(m, "NBR").note
    assert field_tilt(m, "NBR", 0, 60).value is None
```

(`p`, `shot`, `tackle` and `intercept` are tiny event builder helpers in the conftest. `p(id, team, x)` builds a successful pass at that pitch x. `sim_match` is a module-scoped `simulate_match(42, storyline=DEMO_STORYLINE)`.)

- [ ] **Step 2:** Run `pytest tests/analytics -q`. Expected: FAIL.
- [ ] **Step 3:** Implement `base.py`, `shots.py` and `territory.py`.
- [ ] **Step 4:** Run `pytest -q`. Expected: all pass.
- [ ] **Step 5: Suggest commit:** `feat(analytics): add xG, field tilt and PPDA with evidence`.

---

### Task 10: Momentum

**Files:**
- Create: `src/jahbadh/analytics/momentum.py`
- Test: `tests/analytics/test_momentum.py`

**Interfaces:**
- Produces: `momentum(match, at_t: float, window_s: float = 600) -> Metric` (subject `"MATCH"`, window `(max(0, at_t - window_s), at_t)`). Per team, `threat = sum(xg of shots) + 0.02 * successful final-third passes` within the window. The value is the home share `home / (home + away)`, `data={"home": h, "away": a}`, and evidence is the contributing ids. `None` plus `note` when both are 0.
- Also `momentum_series(match, step_s: float = 60, window_s: float = 600) -> list[Metric]`, one per minute.

- [ ] **Step 1: Write the failing tests**

```python
def test_momentum_favours_team_with_more_threat():
    m = make_match([shot(1, "NBR", xg=0.4, t=500), p(2, "RMU", 20, t=550)])
    r = momentum(m, at_t=600)
    assert r.value == pytest.approx(0.4 / (0.4 + 0.02)) and set(r.evidence_event_ids) == {1, 2}

def test_momentum_ignores_events_outside_window():
    m = make_match([shot(1, "NBR", xg=0.4, t=10), shot(2, "RMU", xg=0.2, t=1000)])
    assert momentum(m, at_t=1100).value == pytest.approx(0.0)

def test_momentum_none_when_quiet():
    assert momentum(make_match([]), at_t=600).value is None

def test_series_length(sim_match):
    assert len(momentum_series(sim_match)) == 90
```

- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `pytest -q`. Expected: PASS.
- [ ] **Step 5: Suggest commit:** `feat(analytics): add rolling momentum`.

---

### Task 11: Heatmaps, average positions and team shape

**Files:**
- Create: `src/jahbadh/analytics/positional.py`
- Test: `tests/analytics/test_positional.py`

**Interfaces:**
- Produces:
  - `heatmap(match, subject: str, start=0, end=5400, grid: tuple[int, int] = (21, 14)) -> Metric`, where `subject` is a player id or team id. The grid counts tracking positions, normalised to sum to 1, **in the subject team's attacking coordinates** (so every heatmap reads left-to-right as attacking). `data={"grid": list[list[float]], "cells": [21, 14], "samples": n}`, `value=n` samples, `evidence_frames=(start, end-1)`. Only rows where the entity is on the pitch. `None` if there are no samples.
  - `average_positions(match, team_id, start=0, end=5400) -> Metric`: `data={"players": {player_id: [ax, y]}}` in attacking coordinates, value = number of players.
  - `shape(match, team_id, start=0, end=5400) -> dict[str, Metric]`, with keys `"line_height"`, `"length"`, `"width"`. Per second, over outfield players only: line height is the attacking-x of the **second-deepest** outfield player, length is max ax minus min ax, and width is max y minus min y. Each value is the **median** across seconds, unit `"m"`, and each Metric's `name` equals its dict key.

- [ ] **Step 1: Write the failing tests**

```python
def test_heatmap_sums_to_one_and_respects_window(sim_match):
    h = heatmap(sim_match, "NBR", 0, 600)
    assert sum(map(sum, h.data["grid"])) == pytest.approx(1.0)
    assert h.evidence_frames == (0, 599)

def test_heatmap_is_in_attacking_coordinates():
    # an away player standing near x=10 (deep in the attacking end for the away team) lands in the last columns
    m = make_match([], tracking=static_tracking({"RMU-9": (10, 34)}, seconds=60))
    grid = heatmap(m, "RMU-9", 0, 60).data["grid"]
    assert max(range(21), key=lambda c: sum(grid[c])) >= 18

def test_subbed_player_only_counts_on_pitch_seconds(sim_match_demo):
    sub = sim_match_demo.events_of(EventType.SUBSTITUTION)[0]
    assert heatmap(sim_match_demo, sub.related_player_id, 0, 3600).value is None
    assert heatmap(sim_match_demo, sub.player_id, 3000, 4200).value == 600

def test_shape_line_height_uses_second_deepest():
    m = make_match([], tracking=static_tracking({"NBR-2": (20, 10), "NBR-3": (25, 30), "NBR-4": (40, 50), "NBR-9": (70, 34), "NBR-1": (5, 34)}, gk="NBR-1", seconds=10))
    s = shape(m, "NBR")
    assert s["line_height"].value == pytest.approx(25)
    assert s["length"].value == pytest.approx(50) and s["width"].value == pytest.approx(40)
```

(`static_tracking` and `sim_match_demo` are added to `tests/analytics/conftest.py`. `static_tracking` takes the GK id so shape can exclude him. Player roles come from the match meta.)

- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement using pandas groupby on `t`, and numpy `histogram2d` for the grid.
- [ ] **Step 4:** Run `pytest -q`. Expected: PASS.
- [ ] **Step 5: Suggest commit:** `feat(analytics): add heatmaps, average positions and team shape`.

---

### Task 12: Zone overloads

**Files:**
- Create: `src/jahbadh/analytics/overloads.py`
- Test: `tests/analytics/test_overloads.py`

**Interfaces:**
- Produces: `zone_overloads(match, team_id, start=0, end=5400, margin: int = 2) -> Metric`. Zones are a 3 x 3 grid in the team's attacking coordinates: thirds by `third()`, lanes by `lane()`. Zone names look like `"final-left"`. Per second, count team players vs opponent outfield players in each zone, and record an overload when `team - opp >= margin`. The value is the **share of seconds** in which the most-overloaded zone was overloaded. `data={"zone": name, "typical": "4v2", "by_zone": {name: share}}`, where `typical` is the modal `"{team}v{opp}"` count during overloaded seconds. `evidence_frames=(start, end-1)`. `None` if no second shows an overload.

- [ ] **Step 1: Write the failing tests**

```python
def test_detects_left_flank_overload():
    # NBR has 4 players in its final-left zone, RMU has 2 there, for 30 seconds
    pos = {"NBR-7": (80, 60), "NBR-8": (78, 58), "NBR-10": (82, 62), "NBR-11": (85, 55),
           "RMU-2": (80, 59), "RMU-5": (83, 61)}
    r = zone_overloads(make_match([], tracking=static_tracking(pos, seconds=30)), "NBR")
    assert r.data["zone"] == "final-left" and r.data["typical"] == "4v2" and r.value == pytest.approx(1.0)

def test_away_overload_uses_away_view():
    pos = {"RMU-7": (25, 8), "RMU-8": (27, 10), "RMU-10": (23, 6), "NBR-2": (25, 9)}
    r = zone_overloads(make_match([], tracking=static_tracking(pos, seconds=10)), "RMU")
    assert r.data["zone"] == "final-left"   # low y is the away team's left when attacking toward x=0

def test_no_overload_returns_none():
    pos = {"NBR-7": (80, 60), "RMU-2": (80, 59)}
    assert zone_overloads(make_match([], tracking=static_tracking(pos, seconds=10)), "NBR").value is None

def test_demo_storyline_shows_rmu_overload_after_switch(sim_match_demo):
    after = zone_overloads(sim_match_demo, "RMU", 3600, 4500)
    assert after.value is not None
```

- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement, vectorised over seconds with pandas.
- [ ] **Step 4:** Run `pytest -q`. Expected: PASS. If the last test fails, nudge the `3-4-3` wide slots or `DEMO_STORYLINE` so the switch genuinely creates a flank overload. The demo story depends on it.
- [ ] **Step 5: Suggest commit:** `feat(analytics): add zone overload detection`.

---

### Task 13: Pass networks and before/after comparisons

**Files:**
- Create: `src/jahbadh/analytics/networks.py`, `src/jahbadh/analytics/compare.py`
- Modify: `src/jahbadh/analytics/__init__.py` (re-export every public metric function)
- Test: `tests/analytics/test_networks.py`, `tests/analytics/test_compare.py`

**Interfaces:**
- Produces:
  - `pass_network(match, team_id, start=0, end=5400, min_passes: int = 3) -> Metric`: `data={"nodes": {player_id: {"pos": [ax, y], "passes": n}}, "edges": [[passer, receiver, count], ...]}`. Node positions are the mean attacking-x/y of that player's pass start locations. Keep edges with `count >= min_passes`. Evidence is the successful pass ids. Value is the number of edges.
  - `before_after(fn: Callable[..., Metric], match, subject: str, at_t: float, window_s: float = 900, value_key: str | None = None) -> Metric`. Calls `fn(match, subject, at_t - window_s, at_t)` and `fn(match, subject, at_t, at_t + window_s)`, clamping both windows to [0, 5400]. Name is `f"{before.name}_change"`, value is `after - before` (or `None` if either is `None`), `data={"before": before.model_dump(), "after": after.model_dump()}`, and evidence is the union of both. For `fn` returning a dict (like `shape`), `value_key` picks the entry.

- [ ] **Step 1: Write the failing tests**

```python
def test_pass_network_edges_and_threshold():
    evs = [pr(i, "NBR", "NBR-4", "NBR-8") for i in range(1, 5)] + [pr(5, "NBR", "NBR-8", "NBR-9")]
    r = pass_network(make_match(evs), "NBR")
    assert r.data["edges"] == [["NBR-4", "NBR-8", 4]] and r.value == 1
    assert r.evidence_event_ids == [1, 2, 3, 4, 5]

def test_before_after_on_field_tilt(sim_match_demo):
    r = before_after(field_tilt, sim_match_demo, "RMU", at_t=3600)
    assert r.name == "field_tilt_change"
    assert r.data["before"]["window"] == (2700.0, 3600.0) and r.data["after"]["window"] == (3600.0, 4500.0)
    assert r.value == pytest.approx(r.data["after"]["value"] - r.data["before"]["value"])

def test_before_after_clamps_to_match_bounds(sim_match_demo):
    r = before_after(field_tilt, sim_match_demo, "NBR", at_t=300)
    assert r.data["before"]["window"] == (0.0, 300.0)

def test_before_after_with_dict_metric(sim_match_demo):
    r = before_after(shape, sim_match_demo, "RMU", at_t=3600, value_key="line_height")
    assert r.name == "line_height_change"
```

(`pr(id, team, passer, receiver)` builds a successful pass with a receiver.)

- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement both modules and update the `__init__` re-exports.
- [ ] **Step 4:** Run `pytest -q`. Expected: the whole suite passes.
- [ ] **Step 5: Suggest commit:** `feat(analytics): add pass networks and before/after comparisons`.

---

### Task 14: Preview script (eyeball check) and Plan 1 wrap-up

**Files:**
- Create: `scripts/preview_match.py`
- Modify: `README.md` (create it: a short friendly intro, how to set up the venv, run the tests and generate a match)
- Test: `tests/test_preview_script.py`

**Interfaces:**
- Produces: `python scripts/preview_match.py data/generated/match-042 --out previews/` writes 4 PNGs: `heatmap_RMU_before.png` and `heatmap_RMU_after.png` (windows 2700 to 3600 and 3600 to 4500), `shape_RMU.png` (average positions before and after, side by side) and `momentum.png`. Uses matplotlib with a simple drawn pitch. Add `previews/` to `.gitignore`.

- [ ] **Step 1: Write the failing test**

```python
def test_preview_script_writes_pngs(tmp_path):
    save_match(simulate_match(42, storyline=DEMO_STORYLINE), tmp_path / "m")
    subprocess.run([sys.executable, "scripts/preview_match.py", str(tmp_path / "m"), "--out", str(tmp_path / "p")], check=True)
    assert {f.name for f in (tmp_path / "p").glob("*.png")} == {
        "heatmap_RMU_before.png", "heatmap_RMU_after.png", "shape_RMU.png", "momentum.png"}
```

- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement the script and write the README section.
- [ ] **Step 4:** Run `pytest -q`. Expected: all pass. Then run `python -m jahbadh.simulator --seed 42 --demo-storyline` and the preview script, **open the PNGs and show them to the user**. The RMU heatmaps should visibly change after minute 60. If they don't, the demo story isn't there yet, so go back to Task 6 and 12 constants.
- [ ] **Step 5: Suggest commit:** `feat: add match preview script and README quickstart`.

**Plan 1 is done when:** the full suite passes, the demo match shows a visible tactical shift at 60', and the user has committed each task. Then write Plan 2 (agents).
