# Jahbadh Plan 2: The Agents Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A multi-agent match desk on Microsoft Agent Framework and our Foundry `gpt-5-mini` deployment that turns flagged match moments into grounded claims (every number and id checked), rewrites or drops anything the Referee rejects, and renders the survivors for three personas in English, Arabic and Spanish.

**Architecture:** A deterministic detector flags moments. For each moment an Agent Framework **Workflow** runs Analyst, Tactical, Writer, Referee (with a conditional edge back to the Writer for one rewrite), Persona, Localization and Publish executors. Analyst and Tactical are Agent Framework `Agent`s whose tools wrap `jahbadh.analytics`; every metric a tool computes lands in a per-moment `EvidenceStore`, and the Referee checks claims against that store (pure Python first, then an LLM judge). All model calls go through one thin client module, so unit tests swap in a scripted fake chat client and never touch Azure.

**Tech Stack:** Python 3.13, `agent-framework-core` 1.22.0 and `agent-framework-openai` 1.17.0 (Responses API client), `openai` 3.33.0, `azure-ai-translation-text` 2.0.0, `python-dotenv` 1.2.4, pydantic v2, pytest. Model: Foundry deployment `gpt-5-mini` (GlobalStandard, UAE North) on the OpenAI v1 endpoint.

**Spec:** `docs/superpowers/specs/2026-10-17-jahbadh-design.md`

### How the build is split

| Plan | Covers | Roadmap days |
|---|---|---|
| 1. Data foundation (done, `6b5b6d1`) | Schemas, simulator, analytics library | 1 to 3 |
| **2. Agents (this file)** | Config, model client, Analyst, Tactical, Writers, Referee, Persona, Localization, orchestrator, player spotlight | 4 to 6 |
| 3. Desk | FastAPI + SSE, live and replay modes, React desk UI, template lines for routine events, on-demand persona/language combos, a highlights strip built from approved commentary (no extra LLM call) | 6 to 8 |
| 4. Ship | Eval harness (planted false claims), tracing, Azure Container Apps, CI, README, video | 8 to 10 |

### What I checked before writing this (17 Oct)

Everything below was verified against the real packages in a scratch venv, not from memory:

- **Versions on PyPI today:** `agent-framework-core` 1.22.0 (15 Oct), `agent-framework-openai` 1.17.0 (15 Oct), `openai` 3.33.0, `azure-ai-translation-text` 2.0.0 (API version `2026-06-06`), `python-dotenv` 1.2.4. The `agent-framework` meta package pulls every integration; we only need core + openai.
- **Model client:** `agent_framework.openai.OpenAIChatClient` is the Responses API client. Built as `OpenAIChatClient(model="gpt-5-mini", async_client=AsyncOpenAI(base_url=<our v1 endpoint>, api_key=...))`, a captured request goes to `https://jahbadh-foundry.services.ai.azure.com/openai/v1/responses` with `Authorization: Bearer <key>`, which matches Microsoft's Responses API docs (plain `OpenAI` client, `base_url=.../openai/v1/`, no `api_version`).
- **Reasoning effort:** `default_options={"reasoning": {"effort": "low"}}` on the `Agent` is sent as `"reasoning": {"effort": "low"}`.
- **Structured output:** `agent.run(prompt, options={"response_format": SomePydanticModel})` is sent as `text.format = {"type": "json_schema", "strict": true, ...}` and `response.value` is the parsed model. Strict mode means our LLM-output models must avoid `dict` fields (all fields become required, which is fine).
- **Tools:** plain Python functions with type hints and a docstring passed as `tools=[...]` become Responses `function` tools, and the framework runs the call loop for us.
- **Offline fake:** a subclass of `FunctionInvocationLayer, BaseChatClient` that implements `_inner_get_response` can script tool calls and JSON replies. With it, a real `Agent` called the real tool and returned the parsed model, no network.
- **Workflows:** `WorkflowBuilder(start_executor=...)` with class-based `Executor`s and `add_edge(a, b, condition=...)` supports the Referee to Writer rewrite loop. `WorkflowViz(workflow).to_mermaid()` draws it (handy for the README).
- **Translator:** `TextTranslationClient(credential=AzureKeyCredential(key), region=region)` and `translate(body=[TranslateInputItem(text=..., language="en", text_type="html", targets=[TranslationTarget(language="ar")])])`. HTML mode lets us wrap team and player names in `<span class="notranslate">`.
- **Moment counts (measured, seeds 42, 1, 2, 3, 7):** goals 2 to 8, unscored shots with xG >= 0.3: 0 to 1, cards 1 to 5, momentum swings of 0.4 home share over 10 minutes with a 10-minute cooldown: 3 to 5. With check-ins every 10 minutes that lands at roughly 18 to 30 moments per match, inside the spec's 15 to 30.

Not verifiable without the key, so the opt-in live smoke test covers it: that the Foundry endpoint accepts the key as a Bearer token, that `store=False` plus tool calls works on Azure, and the Translator round trip.

## Global Constraints

- Python 3.13. New runtime deps only: `agent-framework-core>=1.22,<2`, `agent-framework-openai>=1.17,<2`, `openai>=3.33,<4`, `azure-ai-translation-text>=2.0,<3`, `python-dotenv>=1.2`. No new dev deps (tests use `asyncio.run`, not pytest-asyncio).
- Model: deployment `gpt-5-mini` on `https://jahbadh-foundry.services.ai.azure.com/openai/v1/`, reasoning effort `low`, `store=False`.
- **Secrets:** keys only in `.env` (gitignored) or the shell. `.env.example` is committed with empty values. Keys are `SecretStr` and never printed, logged or put in exceptions.
- **Unit tests never call Azure.** They use `ScriptedChatClient` and `FakeTranslator`. Live checks live only in `tests/agents/test_live.py`, skipped unless `JAHBADH_LIVE=1`.
- **Minutes:** agents and checks quote the broadcast minute `Event.minute` (60:00 is 61'). A window `[start, end)` is quoted as `int(start // 60) + 1` to `int((end - 1) // 60) + 1`, so `[3600, 4500)` is 61' to 75'.
- **No future leakage:** for a moment at time `t`, tools and checks only see data before `horizon = min(5400, floor(t) + 1)`.
- **Data-true:** agents describe what the metrics show. Midfield control is descriptive, never a cause. `Player.role` is a natural position, not the current slot. Nobody tunes the simulator to fit a story.
- LLM-output pydantic models (anything passed as `response_format`) have no `dict` fields.
- Docs and user-facing text: friendly, no em dashes. Generated commentary also avoids em dashes.
- **Commits:** the user commits every change through GitHub Desktop. Each task ends with a suggested commit (files, title, body). Never run `git commit` or `git push`.

## Review Focus

1. **Number formats in claims:** a writer says "79%" for a share of 0.787, "1.1" or "1.2" for 1.13, or "60'" for an event at 61'. Expected: "79%" and "1.1" pass (they round correctly at the precision written), "1.2" and "60'" are rejected. Pinned in Task 8.
2. **Broken model output:** invalid JSON, a missing Referee verdict, or a writer returning zero claims. Expected: one retry, then fail closed (claim rejected, moment publishes nothing) without crashing the match run. Pinned in Tasks 2, 9 and 12.
3. **Future leakage in live mode:** a tool asked for minutes past the moment, or a claim citing a later event. Expected: tools clamp to the horizon, the Referee rejects the claim. Pinned in Tasks 4 and 8.
4. **Translation mangling numbers or names:** Arabic-Indic digits, a Spanish decimal comma, a translated team name. Expected: equivalent digits pass, changed numbers or lost names fall back (polished, then raw, then English) with a logged rejection. Pinned in Task 11.
5. **One moment failing in a 25-moment run** (rate limit, exception). Expected: that moment is recorded as a failure and every other moment still publishes. Pinned in Task 12.

---

## File Structure

```
.env.example                    # every setting, empty values (modified)
pyproject.toml                  # new deps, "live" marker (modified)
src/jahbadh/analytics/          # Task 1: window validation, two-sided evidence (modified)
src/jahbadh/agents/
  __init__.py
  __main__.py                   # CLI: python -m jahbadh.agents MATCH_DIR ...
  config.py                     # Settings from .env / environment
  llm.py                        # Foundry chat client factory, make_agent, ask (structured output + retry)
  contracts.py                  # Moment, Finding, Figure, Claim, Rejection, RenderedClaim, FeedItem, DeskRun ...
  evidence.py                   # EvidenceStore, summarize, resolve, describe_event, score/formation helpers
  tools.py                      # analytics wrapped as agent tools, horizon clamping
  moments.py                    # deterministic moment detector
  desk.py                       # Desk, MomentRun, Translator protocol
  prompts.py                    # agent instructions and prompt builders
  analysts.py                   # Analyst and Tactical agents
  writers.py                    # Writer (draft + rewrite)
  numbers.py                    # digit normalisation, number matching
  grounding.py                  # Referee layer 1 (deterministic)
  referee.py                    # Referee layer 2 (semantic) + combined referee
  persona.py                    # Persona rewrite + re-check
  localize.py                   # AzureTranslator, polish, survival check
  pipeline.py                   # Agent Framework Workflow per moment, run_desk
  spotlight.py                  # player spotlight moments
tests/analytics/test_windows.py
tests/agents/
  fakes.py                      # ScriptedChatClient, ToolCall, FakeTranslator, demo_match(), tiny-match helpers
  test_config.py  test_llm.py  test_evidence.py  test_tools.py  test_moments.py  test_analysts.py
  test_writers.py  test_numbers.py  test_grounding.py  test_referee.py  test_persona.py
  test_localize.py  test_pipeline.py  test_spotlight.py  test_cli.py
  test_live.py                  # opt-in, real Azure
```

Note on test helpers: `tests/agents/` gets **no** `conftest.py`. The analytics tests do `from conftest import make_match`, and a second same-named conftest on `sys.path` could shadow it. `fakes.py` loads `tests/analytics/conftest.py` by file path (`importlib.util.spec_from_file_location("analytics_helpers", ...)`) and re-exports `make_match`, `p`, `pr`, `shot`, `shot_by`, `tackle`, `intercept`, `static_tracking`. `demo_match()` is a `functools.cache`d `simulate_match(42, storyline=DEMO_STORYLINE)`.

### Data flow for one moment

```
detect_moments(match) ──> Moment
   Workflow (built per moment):
   Analyst ──> Tactical ──> Writer ──> Referee ──(rejected, first time)──> Writer
                                          │
                                          └──(otherwise)──> Persona ──> Localization ──> Publish ──> FeedItem
   Analyst/Tactical tools ──write──> EvidenceStore <──read── Referee, Persona check, Localization check
```

---

### Task 1: Plan 1 leftovers: window validation and two-sided evidence

**Files:**
- Modify: `src/jahbadh/analytics/base.py`, `shots.py`, `territory.py`, `momentum.py`, `positional.py`, `overloads.py`, `networks.py`, `midfield.py`, `players.py`, `compare.py`
- Modify: `tests/analytics/test_territory.py:11,23`, `tests/analytics/test_midfield.py:14`, `tests/analytics/test_compare.py:29-31`
- Test: `tests/analytics/test_windows.py`

**Interfaces:**
- Produces (in `jahbadh.analytics.base`): `MATCH_END = 5400.0`; `check_window(start: float, end: float) -> None` raising `ValueError` whose message contains `"window"` unless `0 <= start < end <= 5400`.
- Called first thing in `xg_total`, `field_tilt`, `ppda`, `heatmap`, `average_positions`, `shape`, `zone_overloads`, `pass_network`, `midfield_control`, `player_impact`, `player_rankings`.
- `momentum` raises `ValueError` ("window") unless `0 < at_t <= 5400` and `window_s > 0`. `before_after` raises unless `0 < at_t < 5400` and `window_s > 0` (a comparison needs both sides). `compare.MATCH_END` now imports from `base`.
- Evidence becomes two-sided (the ledger's deferred minor): `field_tilt` evidence = sorted ids of **both** teams' counted final-third passes, plus `data = {"team_passes": int, "opponent_passes": int}`. `ppda` evidence = sorted ids of the defensive actions **and** the opponent passes in the zone (data unchanged). `midfield_control` evidence = sorted ids of both teams' counted middle-third passes and duels (data unchanged). The UI can still split sides with `Event.team_id`.

- [ ] **Step 1: Update the three existing evidence asserts and the at_t=0 test**

```python
# tests/analytics/test_territory.py
assert nbr.value == pytest.approx(0.75) and nbr.evidence_event_ids == [1, 2, 3, 5]
assert nbr.data == {"team_passes": 3, "opponent_passes": 1}
# ppda test
assert r.value == pytest.approx(5.0) and r.evidence_event_ids == list(range(1, 13))
# tests/analytics/test_midfield.py
assert r.evidence_event_ids == [1, 2, 3, 4, 5, 6]
# tests/analytics/test_compare.py (add: from conftest import make_match, p): replace test_before_after_none_when_a_side_is_empty
def test_before_after_none_when_a_side_is_empty():
    m = make_match([p(1, "NBR", 80, t=700), p(2, "RMU", 20, t=800)])   # nothing before 600
    r = before_after(field_tilt, m, "NBR", at_t=600, window_s=300)
    assert r.value is None and r.note

def test_before_after_rejects_edges(sim_match_demo):
    for at_t in (0, 5400):
        with pytest.raises(ValueError, match="window"):
            before_after(field_tilt, sim_match_demo, "NBR", at_t=at_t)
```

- [ ] **Step 2: Write `tests/analytics/test_windows.py`**

```python
TEAM_FNS = [xg_total, field_tilt, ppda, average_positions, shape, zone_overloads, pass_network, midfield_control, heatmap]
BAD = [(600, 300), (300, 300), (-60, 600), (0, 6000)]

@pytest.mark.parametrize("fn", TEAM_FNS, ids=lambda f: f.__name__)
@pytest.mark.parametrize("start,end", BAD)
def test_team_metrics_reject_bad_windows(sim_match, fn, start, end):
    with pytest.raises(ValueError, match="window"):
        fn(sim_match, "NBR", start, end)

@pytest.mark.parametrize("start,end", BAD)
def test_player_metrics_reject_bad_windows(sim_match, start, end):
    pid = sim_match.meta.home.players[0].id
    with pytest.raises(ValueError, match="window"):
        player_impact(sim_match, pid, start, end)
    with pytest.raises(ValueError, match="window"):
        player_rankings(sim_match, None, start, end)

@pytest.mark.parametrize("kw", [{"at_t": 0}, {"at_t": 6000}, {"at_t": 600, "window_s": 0}])
def test_momentum_rejects_bad_windows(sim_match, kw):
    with pytest.raises(ValueError, match="window"):
        momentum(sim_match, **kw)

def test_whole_match_window_still_works(sim_match):
    assert xg_total(sim_match, "NBR", 0, 5400).value is not None
```

- [ ] **Step 3: Run the new and changed tests, expect failures**

Run: `.venv/Scripts/python -m pytest tests/analytics/test_windows.py tests/analytics/test_territory.py tests/analytics/test_midfield.py tests/analytics/test_compare.py -q`
Expected: FAIL (no ValueError raised; evidence lists one-sided).

- [ ] **Step 4: Implement `check_window` and the evidence changes listed in Interfaces**

- [ ] **Step 5: Run the full suite**

Run: `.venv/Scripts/python -m pytest -q`
Expected: all pass, 1 xfailed (about 3 minutes).

- [ ] **Step 6: Pause for the user's commit**

Files: `src/jahbadh/analytics/*.py` (the ones above), `tests/analytics/test_windows.py`, `tests/analytics/test_territory.py`, `tests/analytics/test_midfield.py`, `tests/analytics/test_compare.py`.
Title: `fix(analytics): validate metric windows and keep both sides in evidence`
Body: `Bad windows now raise instead of returning plausible numbers. Field tilt, PPDA and midfield control cite the opponent events in their denominators too, so click-to-evidence shows the full picture.`

---

### Task 2: Config, Foundry model client and the scripted fake

**Files:**
- Modify: `pyproject.toml` (deps from Global Constraints; `[tool.pytest.ini_options] markers = ["live: calls real Azure services, opt-in with JAHBADH_LIVE=1"]`), `.env.example`
- Create: `src/jahbadh/agents/__init__.py` (empty docstring module), `src/jahbadh/agents/config.py`, `src/jahbadh/agents/llm.py`
- Create: `tests/agents/fakes.py`, `tests/agents/test_config.py`, `tests/agents/test_llm.py`, `tests/agents/test_live.py`

**Interfaces:**
- Produces (in `jahbadh.agents.config`):
  - `ENV_VARS: dict[str, str]` mapping field name to env var: `foundry_base_url: FOUNDRY_OPENAI_BASE_URL`, `foundry_api_key: FOUNDRY_API_KEY`, `foundry_model: FOUNDRY_MODEL`, `reasoning_effort: FOUNDRY_REASONING_EFFORT`, `translator_key: TRANSLATOR_KEY`, `translator_region: TRANSLATOR_REGION`, `translator_endpoint: TRANSLATOR_ENDPOINT`.
  - `class Settings(BaseModel)`: `foundry_base_url: str = "https://jahbadh-foundry.services.ai.azure.com/openai/v1/"`, `foundry_api_key: SecretStr | None = None`, `foundry_model: str = "gpt-5-mini"`, `reasoning_effort: Literal["low", "medium", "high"] = "low"`, `translator_key: SecretStr | None = None`, `translator_region: str | None = None`, `translator_endpoint: str = "https://api.cognitive.microsofttranslator.com"`. Method `require(*fields: str) -> None` raises `MissingSetting` naming the env vars and pointing at `.env.example`.
  - `class MissingSetting(RuntimeError)`.
  - `load_settings(env_file: Path | None = Path(".env")) -> Settings`: `dotenv_values(env_file)` overlaid by `os.environ` (environment wins), empty strings treated as unset.
- Produces (in `jahbadh.agents.llm`):
  - `AgentName = Literal["analyst", "tactical", "writer", "referee", "persona", "polish"]`
  - `make_chat_client(settings: Settings, http_client: httpx2.AsyncClient | None = None) -> OpenAIChatClient`: requires `foundry_api_key`; builds `AsyncOpenAI(base_url=..., api_key=..., max_retries=5, timeout=90, http_client=http_client)` and `OpenAIChatClient(model=settings.foundry_model, async_client=..., function_invocation_configuration={"max_iterations": 8, "max_function_calls": 16})`. (`openai` 3.x uses the `httpx2` package; import it as `httpx2`.)
  - `make_agent(client, name: AgentName, instructions: str, tools: Sequence[Callable] = (), effort: str = "low") -> Agent`: instructions are prefixed with the line `Role: {name}` (the fake routes on it), `default_options={"reasoning": {"effort": effort}, "store": False}`.
  - `class AgentOutputError(RuntimeError)`.
  - `async def ask(agent: Agent, prompt: str, schema: type[T]) -> T`: runs `agent.run(prompt, options={"response_format": schema})`, returns `response.value`. If reading `.value` raises `ValidationError`/`ValueError` or gives `None`, retries once with `prompt + "\n\nYour last reply did not match the required JSON schema. Reply again with valid JSON only."`, then raises `AgentOutputError(f"{agent.name}: ...")`.
- Produces (in `tests/agents/fakes.py`):
  - `ToolCall(name: str, args: dict)` dataclass.
  - `class ScriptedChatClient(FunctionInvocationLayer, BaseChatClient)`: `__init__(self, script: dict[str, list[Reply]], defaults: dict[str, Reply] | None = None)` (a role's default is used once its list is empty) where `Reply = str | dict | BaseModel | ToolCall | Callable[[list[Message], dict], Reply]`. `_inner_get_response` reads the role from the first line of `options["instructions"]` (`Role: writer`), pops that role's next reply, and returns a `ChatResponse` with either `Content.from_function_call(call_id=f"call-{n}", name=..., arguments=...)` or the reply as JSON text (`model_dump_json()` for models, `json.dumps` for dicts). Records `self.calls: list[tuple[str, list[str], dict]]` (role, message texts, options). An empty or missing script with no default raises `AssertionError(f"no scripted reply left for {role}")`.
  - Shared test helpers also live here and are added by the task that first needs them: `run_for(script, moment=None) -> MomentRun` (Task 6: demo match, formation-change moment by default), `full_time_moment()` (Task 7), `grounded_claim(personas=("pundit",), languages=("en",), translator=None) -> tuple[MomentRun, Claim]` (Task 9), `FakeTranslator` (Task 11), `scripted_full_desk_client()` (Task 13).
  - `responses_api_body(text: str) -> dict`: a minimal completed Responses API JSON body (shape below) for wire tests.
  - `demo_match()`, tiny-match helpers re-exported as described under File Structure. `FakeTranslator` arrives in Task 11.

The fake's core, as verified in the scratch venv:

```python
class ScriptedChatClient(FunctionInvocationLayer, BaseChatClient):
    def __init__(self, script):
        super().__init__()
        self.script = {k: list(v) for k, v in script.items()}
        self.calls = []

    def _inner_get_response(self, *, messages, stream, options, **kwargs):
        assert not stream
        return self._reply(messages, options)

    async def _reply(self, messages, options):
        role = options["instructions"].splitlines()[0].removeprefix("Role: ").strip()
        self.calls.append((role, [m.text for m in messages], dict(options)))
        ...  # pop, resolve callables, build ChatResponse(messages=[Message(role="assistant", contents=[...])])
```

`responses_api_body(text)` returns `{"id": "resp_1", "object": "response", "created_at": 0, "model": "gpt-5-mini", "status": "completed", "output": [{"type": "message", "id": "m1", "role": "assistant", "status": "completed", "content": [{"type": "output_text", "text": text, "annotations": []}]}], "parallel_tool_calls": True, "tool_choice": "auto", "tools": [], "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2, "input_tokens_details": {"cached_tokens": 0}, "output_tokens_details": {"reasoning_tokens": 0}}}`.

- [ ] **Step 1: Write `tests/agents/test_config.py`**

```python
def test_reads_env_file(tmp_path, monkeypatch):
    for var in ENV_VARS.values():
        monkeypatch.delenv(var, raising=False)
    env = tmp_path / ".env"
    env.write_text("FOUNDRY_API_KEY=abc123\nFOUNDRY_MODEL=gpt-5-mini\nTRANSLATOR_REGION=\n")
    s = load_settings(env)
    assert s.foundry_api_key.get_secret_value() == "abc123"
    assert s.reasoning_effort == "low" and s.translator_region is None
    assert s.foundry_base_url == "https://jahbadh-foundry.services.ai.azure.com/openai/v1/"

def test_environment_beats_env_file(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("FOUNDRY_MODEL=from-file\n")
    monkeypatch.setenv("FOUNDRY_MODEL", "from-env")
    assert load_settings(env).foundry_model == "from-env"

def test_key_never_shows_in_repr():
    s = Settings(foundry_api_key="abc123", translator_key="xyz789")
    assert "abc123" not in repr(s) and "xyz789" not in repr(s) and "abc123" not in str(s.model_dump())

def test_require_names_the_env_var():
    with pytest.raises(MissingSetting, match="FOUNDRY_API_KEY"):
        Settings().require("foundry_api_key")

def test_env_example_lists_every_setting_without_values():
    lines = Path(".env.example").read_text().splitlines()
    pairs = dict(l.split("=", 1) for l in lines if "=" in l and not l.startswith("#"))
    assert set(ENV_VARS.values()) <= set(pairs)
    assert pairs["FOUNDRY_API_KEY"] == "" and pairs["TRANSLATOR_KEY"] == ""
```

- [ ] **Step 2: Write `tests/agents/test_llm.py`**

```python
class Out(BaseModel):
    answer: str

def test_client_sends_responses_request_to_foundry():
    seen = []
    def handler(req):
        seen.append((str(req.url), req.headers["authorization"], json.loads(req.content)))
        return httpx2.Response(200, json=responses_api_body('{"answer": "hi"}'))
    client = make_chat_client(Settings(foundry_api_key="k"), http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)))
    out = asyncio.run(ask(make_agent(client, "writer", "be brief"), "go", Out))
    url, auth, body = seen[0]
    assert out == Out(answer="hi")
    assert url == "https://jahbadh-foundry.services.ai.azure.com/openai/v1/responses" and auth == "Bearer k"
    assert body["model"] == "gpt-5-mini" and body["reasoning"] == {"effort": "low"} and body["store"] is False
    assert body["text"]["format"]["type"] == "json_schema" and body["text"]["format"]["strict"] is True
    assert body["instructions"].startswith("Role: writer")

def test_make_chat_client_requires_key():
    with pytest.raises(MissingSetting, match="FOUNDRY_API_KEY"):
        make_chat_client(Settings())

def test_ask_runs_tools_through_the_framework():
    seen = []
    def get_ppda(team_id: str) -> str:
        """PPDA for a team."""
        seen.append(team_id)
        return '{"value": 7.5}'
    fake = ScriptedChatClient({"tactical": [ToolCall("get_ppda", {"team_id": "NBR"}), {"answer": "ok"}]})
    out = asyncio.run(ask(make_agent(fake, "tactical", "x", tools=[get_ppda]), "go", Out))
    assert out.answer == "ok" and seen == ["NBR"]

def test_ask_retries_once_on_bad_json():
    fake = ScriptedChatClient({"writer": ["not json", {"answer": "ok"}]})
    assert asyncio.run(ask(make_agent(fake, "writer", "x"), "go", Out)).answer == "ok"
    assert len(fake.calls) == 2 and "did not match" in fake.calls[1][1][-1]

def test_ask_gives_up_after_two_bad_replies():
    fake = ScriptedChatClient({"writer": ["nope", "still nope"]})
    with pytest.raises(AgentOutputError, match="writer"):
        asyncio.run(ask(make_agent(fake, "writer", "x"), "go", Out))
```

- [ ] **Step 3: Write `tests/agents/test_live.py` (opt-in)**

```python
pytestmark = [pytest.mark.live,
              pytest.mark.skipif(os.environ.get("JAHBADH_LIVE") != "1", reason="set JAHBADH_LIVE=1 to call Azure")]

def test_live_foundry_tool_call_and_structured_output():
    settings = load_settings()
    seen = []
    def get_ppda(team_id: str) -> str:
        """Passes allowed per defensive action for a team over the whole match. Lower means more pressing."""
        seen.append(team_id)
        return '{"id": "ppda:NBR:0-5400", "value": 7.5}'
    agent = make_agent(make_chat_client(settings), "tactical",
                       "Call get_ppda for team NBR, then answer with its value as text.", tools=[get_ppda])
    out = asyncio.run(ask(agent, "What is NBR's PPDA?", Out))
    assert seen == ["NBR"] and "7.5" in out.answer
```

Later tasks add a translator test (Task 11) and a one-moment pipeline test (Task 12) to this file.

- [ ] **Step 4: Run the tests, expect failures**

Run: `.venv/Scripts/python -m pytest tests/agents -q`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 5: Add the deps to `pyproject.toml`, run `.venv/Scripts/pip install -e .[dev]`, then implement `config.py`, `llm.py`, `fakes.py` and update `.env.example`**

`.env.example` gets every var from `ENV_VARS` with empty values except the non-secret defaults (`FOUNDRY_OPENAI_BASE_URL=https://jahbadh-foundry.services.ai.azure.com/openai/v1/`, `FOUNDRY_MODEL=gpt-5-mini`, `FOUNDRY_REASONING_EFFORT=low`, `TRANSLATOR_ENDPOINT=https://api.cognitive.microsofttranslator.com`, `TRANSLATOR_REGION=uaenorth`), plus a comment line per group saying where to find the value in the portal.

- [ ] **Step 6: Run the agent tests**

Run: `.venv/Scripts/python -m pytest tests/agents -q`
Expected: PASS, live test skipped.

- [ ] **Step 7: User action, then live check**

Ask the user to copy `.env.example` to `.env` and paste the Foundry key (Foundry portal, project `jahbadh`, deployment `gpt-5-mini`, Keys). Never ask them to paste it in chat. Then:
Run: `$env:JAHBADH_LIVE=1; .venv/Scripts/python -m pytest tests/agents/test_live.py -q -m live; Remove-Item Env:JAHBADH_LIVE`
Expected: 1 passed. If it fails with 401, try adding `default_headers={"api-key": key}` to `AsyncOpenAI` and report the evidence before changing anything else.

- [ ] **Step 8: Pause for the user's commit**

Files: `pyproject.toml`, `.env.example`, `src/jahbadh/agents/__init__.py`, `config.py`, `llm.py`, `tests/agents/fakes.py`, `test_config.py`, `test_llm.py`, `test_live.py`. (Never `.env`.)
Title: `feat(agents): add Foundry config and model client with an offline fake`
Body: `Settings load from .env with secret keys, the Agent Framework Responses client targets our gpt-5-mini deployment at low reasoning effort, and a scripted fake chat client keeps unit tests offline. Opt-in live smoke test included.`

---

### Task 3: Contracts and the evidence store

**Files:**
- Create: `src/jahbadh/agents/contracts.py`, `src/jahbadh/agents/evidence.py`
- Test: `tests/agents/test_evidence.py`

**Interfaces:**
- Produces (in `jahbadh.agents.contracts`), all pydantic `BaseModel`:
  - `MomentKind = Literal["goal", "big_chance", "card", "substitution", "formation_change", "tactic_change", "momentum_swing", "check_in", "full_time", "spotlight"]`, `Persona = Literal["pundit", "casual", "fantasy"]`, `Language = Literal["en", "ar", "es"]`, `Layer = Literal["deterministic", "semantic", "persona", "localization"]`.
  - `Moment`: `id: str`, `kind: MomentKind`, `t: float`, `team_id: str | None = None`, `player_id: str | None = None`, `event_ids: list[int] = []`, `label: str`. Properties `minute -> int` (`min(90, int(t // 60) + 1)`) and `horizon -> float` (`min(5400.0, floor(t) + 1)`).
  - LLM output models (no dicts): `Finding(text: str, metric_ids: list[str], event_ids: list[int])`, `Findings(findings: list[Finding])`, `Figure(metric_id: str, field: str, written: str)`, `ClaimDraft(text: str, metric_ids: list[str], event_ids: list[int], figures: list[Figure])`, `Draft(claims: list[ClaimDraft])`, `Verdict(claim_id: str, supported: bool, reason: str)`, `Verdicts(verdicts: list[Verdict])`, `Rewrites(texts: list[str])`.
  - `Claim(ClaimDraft)`: adds `id: str`.
  - `Rejection`: `claim_id: str`, `text: str`, `layer: Layer`, `reasons: list[str]`, `attempt: int`, `persona: Persona | None = None`, `language: Language | None = None`.
  - `RenderedClaim`: `claim_id: str`, `persona: Persona`, `language: Language`, `text: str`, `note: str | None = None`.
  - `FeedItem`: `moment: Moment`, `claims: list[Claim]`, `renders: list[RenderedClaim]`, `rejections: list[Rejection]`, `metrics: list[Metric]` (every metric cited by an approved claim), `stats: dict[str, int]` (keys `drafted`, `passed_first`, `rewritten`, `dropped`), `latency_s: float`.
  - `MomentFailure(moment_id: str, error: str)`; `DeskRun(match_id: str, model: str, created: str, items: list[FeedItem], failures: list[MomentFailure])`.
- Produces (in `jahbadh.agents.evidence`):
  - `class EvidenceStore`: `__init__(match)`, `add(metric) -> Metric`, `get(metric_id) -> Metric` (KeyError), `__contains__`, `metrics() -> list[Metric]` (insertion order).
  - `broadcast_window(window: tuple[float, float]) -> str`: `"61'-75'"` per the minute rule in Global Constraints.
  - `resolve(metric: Metric, field: str) -> float | str | None`: `"value"` gives `metric.value`; otherwise walk `metric.data` split on `"."` (so `"before.value"`, `"by_zone.final-left"`, `"typical"`). Missing path raises `KeyError`.
  - `summarize(metric: Metric) -> dict`: `{"id", "name", "subject", "window" (broadcast), "unit", "note", "fields": {path: value}}` plus an optional `"extra"`. `fields` holds every citable scalar: `"value"`, scalar `data` keys, one level of nested scalar dicts as `"key.sub"`, and for `*_change` metrics only `"before.value"` and `"after.value"`. Floats rounded to 3 places. Lists never go in `fields`. `extra` by name: `heatmap` gives `hot_zones` (top 3 of the 3x3 third/lane zones, see test), `pass_network` the top 5 edges, `average_positions` players rounded to 0.1 m. Other list data is dropped.
  - `describe_event(match, event) -> str`: one line, starts with `f"#{e.id} {e.minute}' {e.team_id} {e.type} "` (type in capitals, e.g. `PASS`), then the player name when there is one, plus type details: pass receiver name and outcome, shot xG to 2 places and goal or not, `from -> to` for formation changes, `off -> on` names for subs, press height change, card colour.
  - `score_at(match, t) -> dict[str, int]`: goals per team from `GOAL` events with `e.t < t`, both teams present.
  - `formation_at(match, team_id, t) -> str`: kickoff formation, updated by `FORMATION_CHANGE` events with `e.t < t`.
  - `moment_context(match, moment) -> str`: plain-text block with both teams (id, name, formation at horizon), score at horizon, the moment label and minute, `describe_event` for each trigger event, and a player list (id, name, natural role, starter or sub) for both teams.

- [ ] **Step 1: Write the failing tests**

```python
def test_broadcast_window():
    assert broadcast_window((3600, 4500)) == "61'-75'" and broadcast_window((0, 5400)) == "1'-90'"

def test_store_roundtrip():
    m = make_match([p(1, "NBR", 80), p(2, "RMU", 20)])
    store = EvidenceStore(m)
    tilt = store.add(field_tilt(m, "NBR"))
    assert tilt.id in store and store.get(tilt.id) is tilt and store.metrics() == [tilt]
    with pytest.raises(KeyError):
        store.get("nope")

def test_summary_fields_are_citable():
    s = summarize(field_tilt(make_match([p(1, "NBR", 80), p(2, "RMU", 20)]), "NBR"))
    assert s["window"] == "1'-90'" and s["fields"] == {"value": 0.5, "team_passes": 1, "opponent_passes": 1}

def test_change_metric_exposes_before_and_after():
    r = before_after(field_tilt, demo_match(), "RMU", at_t=3600)
    f = summarize(r)["fields"]
    assert set(f) == {"value", "before.value", "after.value", "at_t"}
    assert resolve(r, "before.value") == r.data["before"]["value"]

def test_resolve_nested_and_missing():
    r = zone_overloads(demo_match(), "RMU", 3600, 4500, margin=1)
    zone = r.data["zone"]
    assert resolve(r, f"by_zone.{zone}") == r.value and resolve(r, "typical") == r.data["typical"]
    with pytest.raises(KeyError):
        resolve(r, "by_zone.nowhere")

def test_heatmap_hot_zones():
    m = make_match([], tracking=static_tracking({"NBR-9": (90, 60)}, seconds=10))
    assert summarize(heatmap(m, "NBR-9", 0, 10))["extra"]["hot_zones"] == [["final-left", 1.0]]

def test_describe_formation_change_uses_broadcast_minute():
    m = demo_match()
    e = next(e for e in m.events if e.type == EventType.FORMATION_CHANGE)
    line = describe_event(m, e)
    assert line.startswith(f"#{e.id} 61'") and "4-3-3 -> 3-4-3" in line

def test_score_and_formation_at():
    m = demo_match()
    first_goal = next(e for e in m.events if e.type == EventType.GOAL)
    assert sum(score_at(m, first_goal.t).values()) == 0
    assert sum(score_at(m, first_goal.t + 1).values()) == 1
    assert formation_at(m, "RMU", 3599) == "4-3-3" and formation_at(m, "RMU", 3601) == "3-4-3"
```

Hot zones: map each heatmap cell centre (`x = (i + 0.5) * 105 / nx`, `y = (j + 0.5) * 68 / ny`) to `f"{third(x)}-{lane}"` with lane `left` if `y >= 68 * 2 / 3`, `right` if `y < 68 / 3`, else `centre` (heatmaps are already in the subject's attacking frame), sum shares, keep the top 3 as `[zone, round(share, 2)]`.

- [ ] **Step 2: Run, expect FAIL** (`.venv/Scripts/python -m pytest tests/agents/test_evidence.py -q`)
- [ ] **Step 3: Implement `contracts.py` and `evidence.py`**
- [ ] **Step 4: Run, expect PASS**
- [ ] **Step 5: Pause for the user's commit**

Files: `src/jahbadh/agents/contracts.py`, `evidence.py`, `tests/agents/test_evidence.py`.
Title: `feat(agents): add desk contracts and the evidence store`
Body: `Typed moments, claims, rejections and feed items, plus a per-moment evidence store with compact metric summaries whose field paths writers can cite.`

---

### Task 4: Analytics as agent tools

**Files:**
- Create: `src/jahbadh/agents/tools.py`
- Test: `tests/agents/test_tools.py`

**Interfaces:**
- Consumes: `EvidenceStore`, `summarize`, `describe_event` (Task 3); all of `jahbadh.analytics`.
- Produces: `make_tools(match: Match, store: EvidenceStore, horizon: float) -> dict[str, Callable[..., str]]`. Each tool is a closure with type hints and a docstring (the docstring is the model's tool description, so it says what the metric means and which direction is "good"). Every tool returns a JSON string: a `summarize()` dict (or list of them) for metrics, or `{"error": "..."}` for any `KeyError`/`ValueError` (never raises). Every metric computed is `store.add`ed.
- Window parameters are clock minutes `from_minute: float = 0, to_minute: float = 90`, converted to seconds and clamped: `end = min(to_minute * 60, horizon)`; if `start >= end` return an error.
- Tools: `list_events(from_minute, to_minute, event_type: str | None = None, team_id: str | None = None)` (at most 40 lines from `describe_event`, latest last; leaves out PRESSURE and CARRY unless asked by type; only `t < horizon`), `get_xg(team_id, from_minute, to_minute)`, `get_momentum(at_minute: float, window_minutes: float = 10)` (at_t clamped to horizon), `get_field_tilt`, `get_ppda(defending_team_id, ...)`, `get_shape(team_id, ...)` (stores all three, returns the three summaries), `get_heatmap(subject_id, ...)`, `get_average_positions`, `get_zone_overloads(team_id, ..., margin: int = 2)`, `get_pass_network`, `get_midfield_control` (docstring says descriptive only), `compare_before_after(metric: Literal["xg", "field_tilt", "ppda", "midfield_control", "zone_overloads", "line_height", "length", "width", "player_impact"], subject_id: str, at_minute: float, window_minutes: float = 15)`, `get_player_impact(player_id, ...)`, `rank_players(by: Literal["value", "progressive_passes", "ball_wins", "final_third_entries", "xa", "xg", "pressures"] = "value", team_id: str | None = None, from_minute=0, to_minute=90, n: int = 3)`.
- `compare_before_after` keeps both sides inside known time: `window_s = min(window_minutes * 60, at_t, horizon - at_t)`; error if `<= 0`. Shape metrics map to `before_after(shape, ..., value_key=...)`.
- `ANALYST_TOOLS = ("list_events", "get_xg", "get_momentum", "get_player_impact", "rank_players")`; `TACTICAL_TOOLS` = every tool name.
- `xg_timeline` and `momentum_series` stay out of the toolset: they are whole-match chart series for the UI and would leak the future in live mode.

- [ ] **Step 1: Write the failing tests**

```python
def tools_for(horizon=5400.0):
    m = demo_match()
    store = EvidenceStore(m)
    return m, store, make_tools(m, store, horizon)

def test_tool_registers_metric_and_returns_summary():
    _, store, tools = tools_for()
    out = json.loads(tools["get_ppda"]("NBR", 0, 90))
    assert out["id"] == "ppda:NBR:0-5400" and out["id"] in store and "value" in out["fields"]

def test_window_is_clamped_to_horizon():
    _, store, tools = tools_for(horizon=601.0)
    out = json.loads(tools["get_field_tilt"]("NBR", 0, 90))
    assert out["id"] == "field_tilt:NBR:0-601" and out["window"] == "1'-11'"

def test_errors_are_returned_not_raised():
    _, _, tools = tools_for()
    assert "error" in json.loads(tools["get_ppda"]("XXX", 0, 90))
    assert "error" in json.loads(tools["get_xg"]("NBR", 50, 40))

def test_compare_before_after_stays_inside_known_time():
    _, _, tools = tools_for(horizon=4000.0)
    out = json.loads(tools["compare_before_after"]("width", "RMU", 60, 15))
    assert out["id"].endswith("at=3600:window=400")

def test_list_events_hides_the_future_and_noise():
    m, _, tools = tools_for(horizon=3601.0)
    lines = json.loads(tools["list_events"](55, 90))
    assert lines and all(int(l.split("'")[0].split()[-1]) <= 61 for l in lines)
    assert not any(" PRESSURE " in l or " CARRY " in l for l in lines)

def test_rank_players_stores_each_player():
    _, store, tools = tools_for()
    out = json.loads(tools["rank_players"]("ball_wins", None, 0, 90, 3))
    assert len(out) == 3 and all(o["id"] in store for o in out)

def test_every_tool_converts_to_a_function_schema():
    _, _, tools = tools_for()
    for name, fn in tools.items():
        spec = tool(fn).to_json_schema_spec()
        assert spec["function"]["name"] == name and fn.__doc__
    assert set(ANALYST_TOOLS) <= set(tools) and set(TACTICAL_TOOLS) == set(tools)
```

(`tool` is `agent_framework.tool`. If `to_json_schema_spec()` nests differently in this version, assert on the name it reports. The point is that every signature converts.)

- [ ] **Step 2: Run, expect FAIL**
- [ ] **Step 3: Implement `tools.py`**
- [ ] **Step 4: Run, expect PASS**
- [ ] **Step 5: Pause for the user's commit**

Files: `src/jahbadh/agents/tools.py`, `tests/agents/test_tools.py`.
Title: `feat(agents): expose the analytics library as agent tools`
Body: `Fourteen tools wrap the metric functions in clock minutes, clamp to the moment so live mode never sees the future, return compact JSON summaries and record every metric as evidence.`

---

### Task 5: Moment detector

**Files:**
- Create: `src/jahbadh/agents/moments.py`
- Test: `tests/agents/test_moments.py`

**Interfaces:**
- Produces: constants `BIG_CHANCE_XG = 0.3`, `SWING_DELTA = 0.4`, `SWING_LOOKBACK_MIN = 10`, `SWING_COOLDOWN_MIN = 10`, `CHECK_IN_MINUTES = (10, 20, 30, 40, 50, 60, 70, 80)`, `CHECK_IN_CLEARANCE_S = 120`; `detect_moments(match: Match) -> list[Moment]`, sorted by `t` (full time last).
- Rules:
  - `goal`: per `GOAL` event; `t` = goal time, `event_ids = [shot_id, goal_id]` (shot id from `detail["shot_id"]`), team = scorer's team.
  - `big_chance`: per unscored `SHOT` with `xg >= 0.3`.
  - `card`: per `CARD` event.
  - Storyline events (`SUBSTITUTION`, `FORMATION_CHANGE`, `TACTIC_CHANGE`) of the same team at the same `t` form **one** moment: kind `formation_change` if any formation change, else `tactic_change`, else `substitution`; all their ids in `event_ids`.
  - `momentum_swing`: on `momentum_series(match)` (60 s step, 600 s window), at step `i` compare value `i` with `i - 10`; flag when both are not `None`, `abs(delta) >= 0.4` and no swing flagged in the previous 10 minutes. `t = (i + 1) * 60`, team = the side that gained (home if delta > 0).
  - `check_in` at each `CHECK_IN_MINUTES` minute (`t = m * 60`) unless another moment lies within 120 s.
  - `full_time` at `t = 5400`, always.
  - `id = f"{kind}-{int(t)}"`; when two moments share an id, add `-2`, `-3`. Labels are short and deterministic, e.g. `"61' Rivermouth United switch to 3-4-3"`, `"15' Goal for Northbridge FC"`.

- [ ] **Step 1: Write the failing tests**

```python
def kinds(ms): return [(m.kind, m.minute) for m in ms]

def test_goal_and_big_chance_rules():
    evs = [shot_by(1, "NBR", "NBR-9", 0.5, t=100, goal=True),
           Event(id=2, t=101, period=1, team_id="NBR", player_id="NBR-9", type=EventType.GOAL, x=105, y=34, detail={"shot_id": 1.0}),
           shot_by(3, "RMU", "RMU-9", 0.29, t=1000), shot_by(4, "RMU", "RMU-9", 0.3, t=1300)]
    ms = detect_moments(make_match(evs))
    goal = next(m for m in ms if m.kind == "goal")
    assert goal.event_ids == [1, 2] and goal.team_id == "NBR" and goal.minute == 2
    assert [m.event_ids for m in ms if m.kind == "big_chance"] == [[4]]

def test_storyline_events_at_the_same_second_are_one_moment():
    ms = detect_moments(demo_match())
    switch = [m for m in ms if m.kind == "formation_change"]
    assert len(switch) == 1 and switch[0].minute == 61 and len(switch[0].event_ids) == 2
    assert not any(m.kind == "substitution" and m.t == switch[0].t for m in ms)

def test_check_ins_make_room_for_real_moments():
    evs = [shot_by(1, "NBR", "NBR-9", 0.4, t=590)]    # big chance 10 s before the 10' check-in
    assert ("check_in", 11) not in kinds(detect_moments(make_match(evs)))

def test_momentum_swing():
    evs = [shot_by(i, "NBR", "NBR-9", 0.2, t=60 * i) for i in range(1, 10)] + \
          [shot_by(20 + i, "RMU", "RMU-9", 0.2, t=600 + 60 * i) for i in range(1, 10)]
    swings = [m for m in detect_moments(make_match(evs)) if m.kind == "momentum_swing"]
    # worked by hand: at t=900 the home share is 1.0/1.8 = 0.556 against 1.0 at t=300, a drop of 0.444
    assert swings and swings[0].team_id == "RMU" and swings[0].t == 900

def test_full_time_is_always_last():
    assert detect_moments(make_match([]))[-1].kind == "full_time"

@pytest.mark.parametrize("seed", [1, 2, 3])
def test_moment_count_is_in_the_spec_range(seed):
    assert 12 <= len(detect_moments(simulate_match(seed))) <= 35

def test_ids_are_unique():
    ms = detect_moments(demo_match())
    assert len({m.id for m in ms}) == len(ms)
```

- [ ] **Step 2: Run, expect FAIL**
- [ ] **Step 3: Implement `moments.py`**
- [ ] **Step 4: Run, expect PASS.** Also print `kinds(detect_moments(demo_match()))` once and paste it into the task report so the user sees the real demo-match moment list.
- [ ] **Step 5: Pause for the user's commit**

Files: `src/jahbadh/agents/moments.py`, `tests/agents/test_moments.py`.
Title: `feat(agents): flag key match moments deterministically`
Body: `Goals, big chances, cards, tactical changes, momentum swings, check-ins and full time, so the desk never misses a goal and the LLM only runs about 20 to 30 times a match.`

---

### Task 6: Desk, prompts, and the Analyst and Tactical agents

**Files:**
- Create: `src/jahbadh/agents/desk.py`, `src/jahbadh/agents/prompts.py`, `src/jahbadh/agents/analysts.py`
- Test: `tests/agents/test_analysts.py`

**Interfaces:**
- Produces (in `jahbadh.agents.desk`):
  - `class Translator(Protocol)`: `def translate(self, texts: list[str], to: str, keep: list[str]) -> list[str]` (sync; callers use `asyncio.to_thread`).
  - `@dataclass class Desk`: `client` (any Agent Framework chat client), `match: Match`, `translator: Translator | None = None`, `personas: tuple[Persona, ...] = ("pundit",)`, `languages: tuple[Language, ...] = ("en",)`, `effort: str = "low"`. Methods `agent(name: AgentName, tools: Sequence[Callable] = ()) -> Agent` (wraps `make_agent` with `INSTRUCTIONS[name]`) and `start(moment) -> MomentRun`.
  - `@dataclass class MomentRun`: `desk`, `moment`, `store: EvidenceStore`, `tools: dict[str, Callable[..., str]]` (from `make_tools(match, store, moment.horizon)`).
- Produces (in `jahbadh.agents.prompts`): `INSTRUCTIONS: dict[AgentName, str]` (filled in across Tasks 6 to 11) and prompt builders. Every instruction must state the shared rules: use only numbers that come from tools or the given metric summaries and never compute new ones; quote minutes as broadcast minutes (an event's minute, 60:00 is 61'); midfield control is descriptive and never a cause; a player's role is their natural position; use team and player names exactly as given; no em dashes.
  - `analyst`: investigates what happened at the moment with its tools (for `spotlight` moments: the player; for `full_time`: the whole match) and returns 2 to 5 findings, each citing the metric ids from tool results and event ids it relies on.
  - `tactical`: gets the analyst's findings and explains why, using the full toolset (shape, overloads, before/after around tactical changes), 1 to 4 findings.
- Produces (in `jahbadh.agents.analysts`):
  - `async def analyse(run: MomentRun) -> list[Finding]` (Analyst agent, `ANALYST_TOOLS`).
  - `async def explain(run: MomentRun, brief: list[Finding]) -> list[Finding]` (Tactical agent, `TACTICAL_TOOLS`).
  - Both prompt with `moment_context(match, moment)` plus the moment's horizon as a clock time, and both pass results through `keep_grounded(run, findings) -> list[Finding]`: drops metric ids not in the store, event ids not in the match or at/after the horizon, then any finding left with no evidence.

- [ ] **Step 1: Write the failing tests**

`run_for` goes in `fakes.py`:

```python
def run_for(script, moment=None, **desk_kw):
    m = demo_match()
    moment = moment or next(x for x in detect_moments(m) if x.kind == "formation_change")
    return Desk(client=ScriptedChatClient(script), match=m, **desk_kw).start(moment)
```

```python
WIDTH_CHANGE = "width_change:RMU:2700-4500:at=3600:window=900"
COMPARE = ToolCall("compare_before_after", {"metric": "width", "subject_id": "RMU", "at_minute": 60, "window_minutes": 15})

def test_tactical_uses_tools_and_keeps_only_grounded_findings():
    real = Finding(text="RMU got wider", metric_ids=[WIDTH_CHANGE], event_ids=[])
    fake = Finding(text="made up", metric_ids=["ppda:XXX:0-1"], event_ids=[])
    run = run_for({"tactical": [COMPARE, Findings(findings=[real, fake])]}, moment=full_time_moment())  # horizon 5400
    assert asyncio.run(explain(run, [])) == [real] and WIDTH_CHANGE in run.store

def test_tactical_cannot_see_past_the_switch():
    # at the 61' switch the horizon is 3601, so the before/after window shrinks to 1 s and the 900 s id never exists
    stale = Finding(text="RMU got wider", metric_ids=[WIDTH_CHANGE], event_ids=[])
    run = run_for({"tactical": [COMPARE, Findings(findings=[stale])]})
    assert asyncio.run(explain(run, [])) == [] and "width_change:RMU:3599-3601:at=3600:window=1" in run.store

def test_analyst_only_gets_analyst_tools():
    run = run_for({"analyst": [Findings(findings=[])]})
    asyncio.run(analyse(run))
    tools = run.desk.client.calls[0][2]["tools"]
    assert sorted(t.name for t in tools) == sorted(ANALYST_TOOLS)

def test_prompts_carry_the_moment_and_rules():
    run = run_for({"analyst": [Findings(findings=[])]})
    asyncio.run(analyse(run))
    role, texts, options = run.desk.client.calls[0]
    assert "3-4-3" in texts[-1] and "61'" in texts[-1]
    assert "broadcast minute" in options["instructions"] and "descriptive" in options["instructions"]

def test_findings_citing_future_events_are_dropped():
    m = demo_match()
    late = next(e for e in m.events if e.t > 4000)
    run = run_for({"analyst": [Findings(findings=[Finding(text="later", metric_ids=[], event_ids=[late.id])])]})
    assert asyncio.run(analyse(run)) == []
```

- [ ] **Step 2: Run, expect FAIL**
- [ ] **Step 3: Implement `desk.py`, `prompts.py` (analyst and tactical), `analysts.py`**
- [ ] **Step 4: Run, expect PASS**
- [ ] **Step 5: Pause for the user's commit**

Files: `src/jahbadh/agents/desk.py`, `prompts.py`, `analysts.py`, `tests/agents/test_analysts.py`.
Title: `feat(agents): add Analyst and Tactical agents with analytics tools`
Body: `Both agents run on Agent Framework with their own toolsets, see only data up to the moment, and anything they cite that is not in the evidence store is dropped before the writers see it.`

---

### Task 7: Writer

**Files:**
- Create: `src/jahbadh/agents/writers.py`; modify `prompts.py` (writer instructions)
- Test: `tests/agents/test_writers.py`

**Interfaces:**
- Consumes: `MomentRun`, `Finding`, `summarize`, `describe_event`, `ask`.
- Produces:
  - `WriterKind = Literal["commentary", "recap", "spotlight"]`; `kind_for(moment) -> WriterKind` (`full_time` gives `recap`, `spotlight` gives `spotlight`, everything else `commentary`).
  - `async def write(run: MomentRun, findings: list[Finding]) -> list[Claim]`: no tools. The prompt holds `moment_context`, the findings, `summarize()` of every metric the findings cite (so `fields` names are visible), and `describe_event` for every cited event. Claim ids are `f"{moment.id}:c{i}"` from 1.
  - `async def rewrite(run: MomentRun, rejected: list[tuple[Claim, list[str]]], findings: list[Finding]) -> list[Claim]`: shows each rejected claim with its reasons and asks for fixed versions in the same order. Returned claims keep the original ids by position; extra claims are ignored; missing ones are simply not returned (they count as dropped later).
- Writer instructions add: studio pundit voice (this is the `pundit` persona, so it costs no extra call); one sentence per claim; 1 to 3 claims for commentary, 4 to 7 for a recap, 2 to 4 for a spotlight; every number in the text must appear in `figures` with `written` copied exactly from the text and `field` taken from that metric's `fields`; percentages are written from shares (0.787 as "79%"); a minute needs a cited event or metric window that shows it; no number may be invented.

- [ ] **Step 1: Write the failing tests**

```python
CLAIM = ClaimDraft(text="Rivermouth have gone 12.5 metres wider since 61'.", metric_ids=["width_change:RMU:2700-4500:at=3600:window=900"],
                   event_ids=[975], figures=[Figure(metric_id="width_change:RMU:2700-4500:at=3600:window=900", field="value", written="12.5")])

def test_write_assigns_ids_and_shows_fields():
    run = run_for({"writer": [Draft(claims=[CLAIM, CLAIM])]}, moment=full_time_moment())
    run.store.add(before_after(shape, run.desk.match, "RMU", at_t=3600, value_key="width"))
    finding = Finding(text="wider", metric_ids=[CLAIM.metric_ids[0]], event_ids=[])
    claims = asyncio.run(write(run, [finding]))
    assert [c.id for c in claims] == ["full_time-5400:c1", "full_time-5400:c2"]
    prompt = run.desk.client.calls[0][1][-1]
    assert '"before.value"' in prompt and "wider" in prompt

def test_rewrite_keeps_ids_by_position():
    run = run_for({"writer": [Draft(claims=[CLAIM])]}, moment=full_time_moment())
    old = Claim(id="full_time-5400:c2", **CLAIM.model_dump())
    out = asyncio.run(rewrite(run, [(old, ["unsupported number '13'"])], []))
    assert [c.id for c in out] == ["full_time-5400:c2"]
    assert "unsupported number '13'" in run.desk.client.calls[0][1][-1]

def test_kind_for():
    assert kind_for(Moment(id="x", kind="full_time", t=5400, label="FT")) == "recap"
```

(`full_time_moment()` is a small helper in `fakes.py`: the last moment of `detect_moments(demo_match())`. The writer prompt embeds each metric summary with `json.dumps`, which is why the test can look for `'"before.value"'`.)

- [ ] **Step 2: Run, expect FAIL**
- [ ] **Step 3: Implement**
- [ ] **Step 4: Run, expect PASS**
- [ ] **Step 5: Pause for the user's commit**

Files: `src/jahbadh/agents/writers.py`, `prompts.py`, `tests/agents/fakes.py`, `tests/agents/test_writers.py`.
Title: `feat(agents): add the Writer with structured, evidence-tagged claims`
Body: `Writers have no tools and only see what Analyst and Tactical found. Every claim lists its metric ids, event ids and each number exactly as written, ready for the Referee.`

---

### Task 8: Referee layer 1: the deterministic check

**Files:**
- Create: `src/jahbadh/agents/numbers.py`, `src/jahbadh/agents/grounding.py`
- Test: `tests/agents/test_numbers.py`, `tests/agents/test_grounding.py`

**Interfaces:**
- Produces (in `jahbadh.agents.numbers`):
  - `normalize_digits(text: str) -> str`: Arabic-Indic (U+0660 to U+0669) and Extended Arabic-Indic (U+06F0 to U+06F9) digits to ASCII, `٫` to `.`, `٪` to `%`, a comma between digits followed by 1 to 3 digits and no further digit to `.` (Spanish "0,79"), and `79 %` to `79%`.
  - `numeric_tokens(text: str) -> list[str]`: `re.findall(r"\d+(?:\.\d+)?", normalize_digits(text))`.
  - `number_matches(written: str, value: float | str) -> bool`: string values must equal `written` ignoring case and spaces. Otherwise parse the number in `written` (after `normalize_digits`); `d` = decimals written; `tol = 0.5 * 10**-d + 1e-9`. With a `%`, compare against `value * 100`. Compare against `abs(value)` (direction words are the semantic layer's job).
- Produces (in `jahbadh.agents.grounding`): `check_claim(claim: Claim, match: Match, store: EvidenceStore, horizon: float) -> list[str]` returning reasons (empty means it passes). In order:
  1. No metric ids and no event ids: `"no evidence cited"`.
  2. Unknown metric id: `f"unknown metric {id}"`. Unknown event id: `f"unknown event {id}"`. Event at or after the horizon: `f"event {id} is after this moment"`.
  3. Each figure: its metric must be in `claim.metric_ids` (`f"figure cites {id} which is not in the evidence"`); `resolve` must succeed and not be `None` (`f"{id} has no field {field}"`); `written` must occur in the text (`f"'{written}' is not in the text"`); `number_matches` must hold (`f"'{written}' does not match {id} {field} = {value}"`, value to 3 places). Then remove that occurrence of `written` from a working copy of the text.
  4. Minute mentions in the working copy: `(\d{1,2})['’]`, `\b(\d{1,2})(?:st|nd|rd|th)[- ]minute\b`, `\bminute (\d{1,2})\b`. Allowed minutes: `Event.minute` of cited events, the two broadcast edges of every cited metric window, the broadcast minute of `data["at_t"]` when present. Otherwise `f"minute {n}' is not backed by the evidence"`. Remove each match.
  5. Durations `\b(\d{1,2}) minutes\b` are allowed when equal to `(end - start) / 60` of a cited metric window, or for change metrics to `(at_t - start) / 60` or `(end - at_t) / 60` ("in the 15 minutes since the switch"); else `f"unsupported duration '{n} minutes'"`. Remove.
  6. Formations `\b\d(?:-\d){2,3}\b` allowed if equal to either team's kickoff formation or a `FORMATION_CHANGE` from/to before the horizon. Remove.
  7. Scores `\b(\d{1,2})-(\d{1,2})\b` allowed if equal to `score_at(match, horizon)` in either order. Remove.
  8. Any digit left: `f"unsupported number '{token}'"` per token.

- [ ] **Step 1: Write `tests/agents/test_numbers.py`**

```python
@pytest.mark.parametrize("written,value,ok", [
    ("79%", 0.787, True), ("78%", 0.787, False), ("78.7%", 0.787, True),
    ("1.1", 1.13, True), ("1.2", 1.13, False), ("1.13", 1.134, True),
    ("12.5", -12.5, True), ("7", 7.4, True), ("7", 7.6, False),
    ("4v2", "4v2", True), ("4v3", "4v2", False),
])
def test_number_matches(written, value, ok):
    assert number_matches(written, value) is ok

def test_normalize_digits():
    assert normalize_digits("٧٩٪ و ٠٫٧٩") == "79% و 0.79"
    assert normalize_digits("un 0,79 y 1.500 pases") == "un 0.79 y 1.500 pases"
    assert numeric_tokens("79 % de 3-4-3") == ["79", "3", "4", "3"]
```

- [ ] **Step 2: Write `tests/agents/test_grounding.py`**

```python
def setup():
    m = make_match([p(1, "NBR", 80, t=100), p(2, "NBR", 80, t=200), p(3, "NBR", 80, t=300), p(4, "RMU", 20, t=400),
                    p(5, "NBR", 80, t=4000)])
    store = EvidenceStore(m)
    tilt = store.add(field_tilt(m, "NBR", 0, 600))      # 0.75, 3 of 4
    return m, store, tilt

def claim(text, figures=(), metric_ids=None, event_ids=()):
    _, _, tilt = setup()
    return Claim(id="m:c1", text=text, metric_ids=[tilt.id] if metric_ids is None else metric_ids,
                 event_ids=list(event_ids), figures=list(figures))

def check(c, horizon=601.0):
    m, store, _ = setup()
    return check_claim(c, m, store, horizon)

def fig(written, field="value"): return Figure(metric_id="field_tilt:NBR:0-600", field=field, written=written)

def test_good_claim_passes():
    assert check(claim("Northbridge had 75% of final-third passes, 3 of them theirs.", [fig("75%"), fig("3", "team_passes")])) == []

def test_wrong_number_is_rejected():
    assert check(claim("Northbridge had 80% of final-third passes.", [fig("80%")])) == \
        ["'80%' does not match field_tilt:NBR:0-600 value = 0.750"]

def test_number_without_figure_is_rejected():
    assert check(claim("Northbridge had 75% of it with 11 players.", [fig("75%")])) == ["unsupported number '11'"]

def test_unknown_ids_and_future_events():
    r = check(claim("x", metric_ids=["ppda:NBR:0-1"], event_ids=[999, 5]))
    assert "unknown metric ppda:NBR:0-1" in r and "unknown event 999" in r and "event 5 is after this moment" in r

def test_no_evidence():
    assert check(claim("Big game.", metric_ids=[])) == ["no evidence cited"]

def test_minutes_follow_the_broadcast_rule():
    assert check(claim("Since 1' they have tilted it, up to 10'.")) == []            # window 0-600 shows as 1'-10'
    assert check(claim("Their pass in 2' and the spell from 1'.", event_ids=[1])) == []   # event 1 is at t=100, so 2'
    off_by_one = claim("Their pass in 1' set it up.", metric_ids=[], event_ids=[1])
    assert check(off_by_one) == ["minute 1' is not backed by the evidence"]

def test_formation_and_true_score_pass_but_a_wrong_score_fails():
    m = demo_match()
    store = EvidenceStore(m)
    switch = next(e for e in m.events if e.type == EventType.FORMATION_CHANGE)
    s = score_at(m, switch.t + 1)
    ok = Claim(id="x:c1", text=f"Rivermouth went to a 3-4-3 at 61' with the score at {s['NBR']}-{s['RMU']}.",
               metric_ids=[], event_ids=[switch.id], figures=[])
    assert check_claim(ok, m, store, switch.t + 1) == []
    wrong = ok.model_copy(update={"text": "Rivermouth went to a 3-4-3 at 61' with the score at 9-9."})
    assert check_claim(wrong, m, store, switch.t + 1) == ["unsupported number '9'", "unsupported number '9'"]
```

- [ ] **Step 3: Run, expect FAIL**
- [ ] **Step 4: Implement `numbers.py` and `grounding.py`**
- [ ] **Step 5: Run, expect PASS**
- [ ] **Step 6: Pause for the user's commit**

Files: `src/jahbadh/agents/numbers.py`, `grounding.py`, `tests/agents/test_numbers.py`, `test_grounding.py`.
Title: `feat(agents): add the Referee's deterministic grounding check`
Body: `Every id must exist, every number must match its metric within the precision it is written at, minutes follow the broadcast rule, and any number nobody can back up gets the claim rejected. No LLM involved.`

---

### Task 9: Referee layer 2: the semantic judge

**Files:**
- Create: `src/jahbadh/agents/referee.py`; modify `prompts.py` (referee instructions)
- Test: `tests/agents/test_referee.py`

**Interfaces:**
- Consumes: `check_claim`, `summarize`, `describe_event`, `ask`, `Verdicts`.
- Produces:
  - `async def judge(run: MomentRun, claims: list[Claim], mode: Literal["support", "faithful"] = "support", originals: dict[str, str] | None = None) -> dict[str, str | None]`: one `referee` agent call for the whole batch; returns `claim_id -> None` (supported) or the reason. `support`: does the cited evidence (summaries and event lines) really support the sentence, including direction words, causality and names? `faithful` (Persona): does each rewrite say the same as `originals[claim_id]` with no new fact? A claim with no verdict in the reply gets `"referee gave no verdict"` (fail closed). An `AgentOutputError` gives every claim `"referee unavailable"`.
  - `async def referee(run: MomentRun, claims: list[Claim], attempt: int) -> tuple[list[Claim], list[Rejection]]`: deterministic first (`horizon = moment.horizon`); only claims that pass go to `judge`; returns approved claims and one `Rejection` per failure (`layer` = which check failed, `attempt` as given).
- Referee instructions: strict but fair; reject causal claims built only on midfield control; reject direction words that contradict a change metric's sign; reject wrong player or team attribution; never reject only for style.

- [ ] **Step 1: Write the failing tests**

```python
def test_deterministic_failures_never_reach_the_llm():
    run = run_for({"referee": []}, moment=full_time_moment())
    bad = Claim(id="x:c1", text="They scored 99 goals.", metric_ids=[], event_ids=[], figures=[])
    approved, rejected = asyncio.run(referee(run, [bad], attempt=0))
    assert approved == [] and rejected[0].layer == "deterministic" and run.desk.client.calls == []

def test_semantic_rejection_is_recorded():
    run, good = grounded_claim()          # helper: run with one real metric in the store and a claim that passes layer 1
    run.desk.client.script["referee"] = [Verdicts(verdicts=[Verdict(claim_id=good.id, supported=False, reason="says wider, metric says narrower")])]
    approved, rejected = asyncio.run(referee(run, [good], attempt=1))
    assert approved == [] and rejected[0].layer == "semantic" and rejected[0].attempt == 1
    assert rejected[0].reasons == ["says wider, metric says narrower"]

def test_missing_verdict_fails_closed():
    run, good = grounded_claim()
    run.desk.client.script["referee"] = [Verdicts(verdicts=[])]
    approved, rejected = asyncio.run(referee(run, [good], attempt=0))
    assert approved == [] and rejected[0].reasons == ["referee gave no verdict"]

def test_supported_claim_is_approved():
    run, good = grounded_claim()
    run.desk.client.script["referee"] = [Verdicts(verdicts=[Verdict(claim_id=good.id, supported=True, reason="ok")])]
    assert asyncio.run(referee(run, [good], attempt=0)) == ([good], [])
```

(`grounded_claim()` lives in `fakes.py`: full-time run, `store.add(field_tilt(match, "NBR"))`, and the claim `f"Northbridge FC had {pct} of the final-third passes."` where `pct` is the tilt as a whole percentage, with a matching figure. Its name matters for Task 11's keep-term checks.)

- [ ] **Step 2: Run, expect FAIL**
- [ ] **Step 3: Implement**
- [ ] **Step 4: Run, expect PASS**
- [ ] **Step 5: Pause for the user's commit**

Files: `src/jahbadh/agents/referee.py`, `prompts.py`, `tests/agents/fakes.py`, `tests/agents/test_referee.py`.
Title: `feat(agents): add the Referee's semantic judge`
Body: `Claims that pass the numbers check go to an LLM judge that reads the same evidence. Missing verdicts fail closed, and every rejection keeps its layer, reasons and attempt for the UI.`

---

### Task 10: Persona

**Files:**
- Create: `src/jahbadh/agents/persona.py`; modify `prompts.py` (persona instructions)
- Test: `tests/agents/test_persona.py`

**Interfaces:**
- Produces: `async def render_personas(run: MomentRun, claims: list[Claim]) -> tuple[list[RenderedClaim], list[Rejection]]`.
  - `pundit` renders are the approved texts as they are (no call).
  - For each other persona in `desk.personas`: one `persona` agent call returning `Rewrites(texts=[...])` in claim order. Each rewrite becomes a copy of the claim with the new text and only the figures whose `written` still appears (a casual fan line may drop a number, never add one). It must pass `check_claim`, then `judge(..., mode="faithful", originals=...)`. A failure, or a length mismatch, falls back to the pundit text with `note="persona fallback"` and a `Rejection(layer="persona", persona=...)`.
  - Persona styles: `casual` (plain words, explain jargon like PPDA or field tilt in a few words, warm), `fantasy` (lead with the players involved and what it means for their output). Neither adds facts or numbers.

- [ ] **Step 1: Write the failing tests**

```python
def test_pundit_is_free_and_casual_is_checked():
    run, good = grounded_claim(personas=("pundit", "casual"))
    pct = good.figures[0].written
    run.desk.client.script["persona"] = [Rewrites(texts=[f"Northbridge spent loads of time near goal: {pct} of the final-third passes."])]
    run.desk.client.script["referee"] = [Verdicts(verdicts=[Verdict(claim_id=good.id, supported=True, reason="same")])]
    renders, rejected = asyncio.run(render_personas(run, [good]))
    assert [(r.persona, r.note) for r in renders] == [("pundit", None), ("casual", None)] and rejected == []

def test_new_number_falls_back_to_pundit():
    run, good = grounded_claim(personas=("pundit", "casual"))
    run.desk.client.script["persona"] = [Rewrites(texts=["They had 99% of it, wow."])]
    renders, rejected = asyncio.run(render_personas(run, [good]))
    casual = next(r for r in renders if r.persona == "casual")
    assert casual.text == good.text and casual.note == "persona fallback"
    assert rejected[0].layer == "persona" and rejected[0].persona == "casual"

def test_length_mismatch_falls_back():
    run, good = grounded_claim(personas=("pundit", "fantasy"))
    run.desk.client.script["persona"] = [Rewrites(texts=[])]
    renders, _ = asyncio.run(render_personas(run, [good]))
    assert next(r for r in renders if r.persona == "fantasy").note == "persona fallback"
```

- [ ] **Step 2: Run, expect FAIL**
- [ ] **Step 3: Implement**
- [ ] **Step 4: Run, expect PASS**
- [ ] **Step 5: Pause for the user's commit**

Files: `src/jahbadh/agents/persona.py`, `prompts.py`, `tests/agents/fakes.py`, `tests/agents/test_persona.py`.
Title: `feat(agents): add casual and fantasy personas with a re-check`
Body: `Persona rewrites go back through the numbers check and a faithfulness judge, so no new claim can sneak in. Anything that fails falls back to the pundit line and the rejection is kept.`

---

### Task 11: Localization (EN/AR/ES)

**Before this task (user action):** create a Translator resource, free tier F0, in an allowed region (try UAE North, fall back to Germany West Central), resource group `rg-jahbadh-ai`. Put its key and region in `.env` (`TRANSLATOR_KEY`, `TRANSLATOR_REGION`). The unit tests do not need it, only the live test does.

**Files:**
- Create: `src/jahbadh/agents/localize.py`; modify `prompts.py` (polish instructions), `tests/agents/fakes.py` (`FakeTranslator`), `tests/agents/test_live.py`
- Test: `tests/agents/test_localize.py`

**Interfaces:**
- Produces (in `jahbadh.agents.localize`):
  - `class AzureTranslator` (implements `Translator`): `__init__(settings)` requires `translator_key` and `translator_region`, builds `TextTranslationClient(endpoint=settings.translator_endpoint, credential=AzureKeyCredential(key), region=region)`. `translate(texts, to, keep)`: HTML-escapes each text, wraps every `keep` term (longest first) in `<span class="notranslate">...</span>`, sends `TranslateInputItem(text=..., language="en", text_type="html", targets=[TranslationTarget(language=to)])` items in one request, then strips tags and unescapes.
  - `keep_terms(match) -> list[str]`: team names, team ids and every player name.
  - `survives(source: str, translated: str, keep: list[str]) -> list[str]`: reasons; numbers compared as multisets of `numeric_tokens` (after normalisation), and every `keep` term present in the source must be present in the translation.
  - `async def localize(run: MomentRun, renders: list[RenderedClaim]) -> tuple[list[RenderedClaim], list[Rejection]]`: for each `en` render and each language in `desk.languages` other than `en`, grouped per persona into one batch: Translator (via `asyncio.to_thread`), then one `polish` agent call (`Rewrites`, same order: fix football terms, keep names and numbers exactly), then `survives` per text. Use polished if it survives, else raw (`note="raw translation"`), else the English text (`note="english fallback"`). Each render that did not use the polished text logs exactly one `Rejection(layer="localization", persona=..., language=...)` whose reasons list what failed in each attempt. Claim ids and evidence never change, because only text is translated.

- [ ] **Step 1: Write the failing tests**

```python
class FakeTranslator:                      # in fakes.py
    def __init__(self, mangle=None): self.mangle, self.calls = mangle, []
    def translate(self, texts, to, keep):
        self.calls.append((list(texts), to, list(keep)))
        return [self.mangle(t) if self.mangle else f"[{to}] {t}" for t in texts]

def test_survives_accepts_arabic_digits_and_spanish_commas():
    assert survives("Field tilt 79% and 0.79 xG for Northbridge FC", "ميل الملعب ٧٩٪ و ٠٫٧٩ لـ Northbridge FC", ["Northbridge FC"]) == []
    assert survives("0.79 xG", "0,79 xG", []) == []

def test_survives_catches_changed_numbers_and_lost_names():
    r = survives("Northbridge FC had 79%", "Puente Norte tuvo 80%", ["Northbridge FC"])
    assert any("79" in x for x in r) and any("Northbridge FC" in x for x in r)

def test_polished_translation_is_used_when_it_survives():
    run, good = grounded_claim(languages=("en", "ar"), translator=FakeTranslator())
    run.desk.client.script["polish"] = [Rewrites(texts=[f"[ar*] {good.text}"])]
    renders, rejected = asyncio.run(localize(run, [RenderedClaim(claim_id=good.id, persona="pundit", language="en", text=good.text)]))
    assert [(r.language, r.text, r.note) for r in renders] == [("ar", f"[ar*] {good.text}", None)] and rejected == []

def test_falls_back_to_raw_then_english():
    run, good = grounded_claim(languages=("en", "es"), translator=FakeTranslator(mangle=lambda t: "sin numeros"))
    run.desk.client.script["polish"] = [Rewrites(texts=["tampoco"])]
    renders, rejected = asyncio.run(localize(run, [RenderedClaim(claim_id=good.id, persona="pundit", language="en", text=good.text)]))
    assert renders[0].text == good.text and renders[0].note == "english fallback"
    assert rejected[0].layer == "localization" and rejected[0].language == "es"

def test_names_are_sent_as_keep_terms():
    t = FakeTranslator()
    run, good = grounded_claim(languages=("en", "ar"), translator=t)
    run.desk.client.script["polish"] = [Rewrites(texts=[f"[ar] {good.text}"])]
    asyncio.run(localize(run, [RenderedClaim(claim_id=good.id, persona="pundit", language="en", text=good.text)]))
    assert "Northbridge FC" in t.calls[0][2]

def test_azure_translator_wraps_names_in_notranslate(monkeypatch):
    sent = []
    tr = AzureTranslator(Settings(translator_key="k", translator_region="uaenorth"))
    monkeypatch.setattr(tr.client, "translate", lambda body: sent.extend(body) or [fake_item("<span class=\"notranslate\">Northbridge FC</span> ganó")])
    assert tr.translate(["Northbridge FC won"], "es", ["Northbridge FC"]) == ["Northbridge FC ganó"]
    assert sent[0].text_type == "html" and 'class="notranslate">Northbridge FC<' in sent[0].text
```

(`fake_item(text)` builds a `TranslatedTextItem`-like object with `.translations[0].text`; check the real attribute names in `azure.ai.translation.text.models` while implementing.)

Add to `tests/agents/test_live.py`:

```python
def test_live_translator_keeps_numbers_and_names():
    tr = AzureTranslator(load_settings())
    src = "Northbridge FC had 79% of the final-third passes and 1.13 xG by 61'."
    for lang in ("ar", "es"):
        out = tr.translate([src], lang, ["Northbridge FC"])[0]
        assert survives(src, out, ["Northbridge FC"]) == [], out
```

- [ ] **Step 2: Run, expect FAIL**
- [ ] **Step 3: Implement**
- [ ] **Step 4: Run unit tests, expect PASS; then the live test once the user has set the Translator key**

Run: `$env:JAHBADH_LIVE=1; .venv/Scripts/python -m pytest tests/agents/test_live.py -q -m live; Remove-Item Env:JAHBADH_LIVE`
Expected: 2 passed. If Arabic output fails `survives`, paste the output into the report before changing the normaliser.

- [ ] **Step 5: Pause for the user's commit**

Files: `src/jahbadh/agents/localize.py`, `prompts.py`, `tests/agents/fakes.py`, `tests/agents/test_localize.py`, `tests/agents/test_live.py`, `.env.example` (if comments changed).
Title: `feat(agents): add Arabic and Spanish localization with a survival check`
Body: `Azure AI Translator handles the translation with team and player names protected, an LLM polish pass fixes football terms, and a deterministic check makes sure every number and name survived before anything is published.`

---

### Task 12: Orchestrator: an Agent Framework workflow per moment

**Files:**
- Create: `src/jahbadh/agents/pipeline.py`
- Test: `tests/agents/test_pipeline.py`; modify `tests/agents/test_live.py`

**Interfaces:**
- Consumes: everything above.
- Produces:
  - `class MomentState(BaseModel)`: `moment: Moment`, `findings: list[Finding] = []`, `approved: list[Claim] = []`, `pending: list[Claim] = []`, `retry: list[tuple[Claim, list[str]]] = []`, `rejections: list[Rejection] = []`, `renders: list[RenderedClaim] = []`, `attempt: int = 0`, `stats: dict[str, int] = {}`. This is the single message type every executor receives and sends.
  - Executors (class-based `agent_framework.Executor`, each built with the `MomentRun`, one `@handler` taking `MomentState`): `AnalystStep` (`analyse`), `TacticalStep` (`explain`, findings appended), `WriterStep` (first visit: `write`, sets `pending` and `stats["drafted"]`; when `retry` is set: `rewrite`, `attempt = 1`, `stats["rewritten"]`), `RefereeStep` (`referee(run, pending, attempt)`; passes go to `approved`; on attempt 0 failures move to `retry` with their reasons, on attempt 1 they are dropped, counted in `stats["dropped"]`; `stats["passed_first"]` counts attempt-0 passes), `PersonaStep` (`render_personas`), `LocalizeStep` (`localize`), `PublishStep` (yields the `FeedItem`; `metrics` = the store metrics cited by approved claims).
  - `build_workflow(run: MomentRun) -> Workflow`: `WorkflowBuilder(start_executor=analyst, name="moment")`, chain analyst to tactical to writer to referee, then `add_edge(referee, writer, condition=lambda s: bool(s.retry) and s.attempt == 0)` and `add_edge(referee, persona, condition=lambda s: not (s.retry and s.attempt == 0))`, then persona to localize to publish. Built fresh per moment.
  - `async def run_moment(desk: Desk, moment: Moment) -> FeedItem`: builds the run and workflow, `await workflow.run(MomentState(moment=moment))`, returns the single output with `latency_s` set.
  - `async def run_desk(desk: Desk, moments: list[Moment], concurrency: int = 3) -> DeskRun`: `asyncio.Semaphore(concurrency)` and `gather`; an exception in one moment becomes a `MomentFailure` (type and message, never a key) and the rest carry on; items sorted by `moment.t`.
  - `workflow_mermaid(desk: Desk) -> str`: `WorkflowViz(build_workflow(<full time run>)).to_mermaid()`. Building a workflow creates no agents (they are made inside the handlers), so this works with `Desk(client=None, ...)`.
  - Persona and Localize steps make no model or Translator call when there is nothing to render (zero approved claims).

- [ ] **Step 1: Write the failing tests**

```python
def scripted_moment(writer_replies, referee_replies, **desk_kw):
    """Full-time moment; the tactical agent computes NBR field tilt so the writer has something real to cite."""

def test_happy_path_publishes_approved_claims():
    item = asyncio.run(run_moment(*scripted_moment(writer_replies=[good_draft()], referee_replies=[all_supported()])))
    assert len(item.claims) == 1 and item.rejections == []
    assert item.stats == {"drafted": 1, "passed_first": 1, "rewritten": 0, "dropped": 0}
    assert [m.id for m in item.metrics] == item.claims[0].metric_ids

def test_one_rewrite_then_publish():
    item = asyncio.run(run_moment(*scripted_moment(writer_replies=[bad_number_draft(), good_draft()], referee_replies=[all_supported()])))
    assert len(item.claims) == 1 and item.stats["rewritten"] == 1
    assert item.rejections[0].layer == "deterministic" and item.rejections[0].attempt == 0

def test_second_failure_drops_the_claim_and_keeps_both_rejections():
    item = asyncio.run(run_moment(*scripted_moment(writer_replies=[bad_number_draft(), bad_number_draft()], referee_replies=[])))
    assert item.claims == [] and item.stats["dropped"] == 1 and [r.attempt for r in item.rejections] == [0, 1]

def test_zero_claims_publishes_an_empty_item():
    item = asyncio.run(run_moment(*scripted_moment(writer_replies=[Draft(claims=[])], referee_replies=[])))
    assert item.claims == [] and item.renders == []

def test_one_failing_moment_does_not_stop_the_run(monkeypatch):
    desk, moment = scripted_moment(writer_replies=[good_draft()], referee_replies=[all_supported()])
    broken = Moment(id="check_in-600", kind="check_in", t=600, label="10' check-in")
    real = pipeline.analyse
    async def flaky(run):
        if run.moment.id == broken.id:
            raise RuntimeError("429 rate limited")
        return await real(run)
    monkeypatch.setattr(pipeline, "analyse", flaky)        # pipeline must call analyse through its module namespace
    run = asyncio.run(run_desk(desk, [broken, moment], concurrency=2))
    assert [i.moment.id for i in run.items] == [moment.id]
    assert run.failures[0].moment_id == broken.id and "rate limited" in run.failures[0].error

def test_full_pipeline_renders_every_combo():
    desk, moment = scripted_moment(writer_replies=[good_draft()], referee_replies=[all_supported(), all_supported()],
                                   persona_replies=[same_text_rewrite()], polish_replies=[Rewrites(texts=[])] * 2,
                                   personas=("pundit", "casual"), languages=("en", "ar"), translator=FakeTranslator())
    item = asyncio.run(run_moment(desk, moment))
    assert sorted((r.persona, r.language) for r in item.renders) == [("casual", "ar"), ("casual", "en"), ("pundit", "ar"), ("pundit", "en")]

def test_workflow_diagram_shows_the_rewrite_loop():
    desk, _ = scripted_moment(writer_replies=[], referee_replies=[])
    assert "referee -. conditional .-> writer" in workflow_mermaid(desk)
```

(Helpers in the test file: `scripted_moment(writer_replies, referee_replies, persona_replies=(), polish_replies=(), **desk_kw) -> tuple[Desk, Moment]` uses the full-time moment and scripts the analyst with an empty `Findings`, and the tactical agent with `ToolCall("get_field_tilt", {"team_id": "NBR"})` then a finding citing `field_tilt:NBR:0-5400`. `good_draft()` is one claim quoting that tilt as a percentage with a matching figure, `bad_number_draft()` the same claim with a wrong percentage, `all_supported()` a `Verdicts` reply built by a callable that approves every claim id it is shown, `same_text_rewrite()` a callable that returns the pundit texts unchanged. Empty polish replies make localization fall back to the raw translation, which is enough here. Executor ids are `analyst`, `tactical`, `writer`, `referee`, `persona`, `localize`, `publish`.)

Add to `tests/agents/test_live.py`:

```python
def test_live_one_moment_end_to_end():
    m = demo_match()
    desk = Desk(client=make_chat_client(load_settings()), match=m)
    moment = next(x for x in detect_moments(m) if x.kind == "formation_change")
    item = asyncio.run(run_moment(desk, moment))
    print(item.model_dump_json(indent=2))
    assert item.claims or item.rejections      # the desk produced something and the Referee looked at it
```

- [ ] **Step 2: Run, expect FAIL**
- [ ] **Step 3: Implement `pipeline.py`**
- [ ] **Step 4: Run, expect PASS**
- [ ] **Step 5: Live check (about 6 to 10 model calls, a few cents at most).** Run the live tests, paste the printed `FeedItem` into the report, and read it with the user: are the claims true to the data, are the minutes right, did anything get rejected and why?
- [ ] **Step 6: Pause for the user's commit**

Files: `src/jahbadh/agents/pipeline.py`, `tests/agents/test_pipeline.py`, `tests/agents/test_live.py`.
Title: `feat(agents): orchestrate each moment as an Agent Framework workflow`
Body: `Analyst, Tactical, Writer, Referee, Persona and Localization run as workflow executors with a conditional rewrite edge. Moments run concurrently with a cap, and one failing moment never stops the match.`

---

### Task 13: Player spotlight, the desk CLI and the README

**Files:**
- Create: `src/jahbadh/agents/spotlight.py`, `src/jahbadh/agents/__main__.py`
- Modify: `README.md`, `prompts.py` (analyst guidance for spotlight moments if not already there)
- Test: `tests/agents/test_spotlight.py`, `tests/agents/test_cli.py`

**Interfaces:**
- Produces (in `jahbadh.agents.spotlight`):
  - `SPOTLIGHT_ANGLES = (("value", "most expected goal involvement"), ("progressive_passes", "most progressive passes"), ("ball_wins", "most ball wins"))`.
  - `spotlight_moment(match, player_id: str, angle_label: str, t: float = 5400) -> Moment`: kind `spotlight`, id `f"spotlight-{player_id}"`, team from the player, label `f"Spotlight: {name} ({angle_label})"`.
  - `spotlight_moments(match, t: float = 5400) -> list[Moment]`: for each angle take `player_rankings(match, None, 0, t, by=key, n=5)`, pick the first player not already chosen whose ranked value is above 0. Data-true: if nobody has a positive value for an angle, that angle is skipped.
- Produces (in `jahbadh.agents.__main__`): `main(argv: list[str] | None = None) -> int`. `python -m jahbadh.agents MATCH_DIR [--limit N] [--personas pundit,casual,fantasy] [--languages en,ar,es] [--concurrency 3] [--no-spotlight] [--mermaid]`. Loads `.env` settings and the match, builds the moment list (`detect_moments` plus `spotlight_moments` unless disabled; `--limit N` keeps the earliest N moments and adds full time if it was cut), creates `AzureTranslator` only when a non-English language is asked for, runs `run_desk`, writes `MATCH_DIR/desk.json` (`DeskRun`), and prints a summary: moments, failures, approved claims, first-draft pass rate (`passed_first / drafted`), rejections by layer, mean latency. `--mermaid` prints `workflow_mermaid` and exits without calling the model. A missing key exits with code 2 and the `MissingSetting` message.
- README: a "Run the agent desk" section (copy `.env.example` to `.env`, fill the keys, the CLI command, what `desk.json` holds, the opt-in live tests) and a short "How the desk checks itself" paragraph. Friendly, no em dashes.

- [ ] **Step 1: Write the failing tests**

```python
def test_spotlights_pick_distinct_players_with_real_numbers():
    m = demo_match()
    ms = spotlight_moments(m)
    assert 1 <= len(ms) <= 3 and len({x.player_id for x in ms}) == len(ms)
    top = player_rankings(m, None, 0, 5400, by="value", n=1)[0]
    assert ms[0].player_id == top.subject and ms[0].kind == "spotlight"

def test_angle_with_nobody_above_zero_is_skipped():
    m = make_match([pr(1, "NBR", "NBR-4", "NBR-9")], tracking=static_tracking({"NBR-4": (50, 34), "NBR-9": (60, 34)}, seconds=60))
    assert [x.label for x in spotlight_moments(m, t=60)] == []

def test_cli_mermaid_needs_no_key(capsys, monkeypatch, tmp_path):
    save_match(demo_match(), tmp_path / "m")
    for var in ENV_VARS.values():
        monkeypatch.delenv(var, raising=False)
    assert main([str(tmp_path / "m"), "--mermaid"]) == 0 and "flowchart" in capsys.readouterr().out

def test_cli_without_key_exits_cleanly(capsys, monkeypatch, tmp_path):
    save_match(demo_match(), tmp_path / "m")
    monkeypatch.chdir(tmp_path)                     # no .env here
    for var in ENV_VARS.values():
        monkeypatch.delenv(var, raising=False)
    assert main([str(tmp_path / "m"), "--limit", "1"]) == 2 and "FOUNDRY_API_KEY" in capsys.readouterr().err

def test_cli_writes_desk_json(monkeypatch, tmp_path):
    save_match(demo_match(), tmp_path / "m")
    monkeypatch.setattr("jahbadh.agents.__main__.make_chat_client", lambda s: scripted_full_desk_client())
    monkeypatch.setenv("FOUNDRY_API_KEY", "test")
    assert main([str(tmp_path / "m"), "--limit", "1", "--no-spotlight", "--languages", "en", "--personas", "pundit"]) == 0
    run = DeskRun.model_validate_json((tmp_path / "m" / "desk.json").read_text(encoding="utf-8"))
    assert run.items and run.items[-1].moment.kind == "full_time"
```

(`scripted_full_desk_client()` in `fakes.py` returns a `ScriptedChatClient` whose replies are callables that always produce a valid empty-but-well-formed reply per role, so any number of moments can run.)

- [ ] **Step 2: Run, expect FAIL**
- [ ] **Step 3: Implement `spotlight.py`, `__main__.py`, README section**
- [ ] **Step 4: Run the full suite**

Run: `.venv/Scripts/python -m pytest -q`
Expected: all pass, 1 xfailed, live tests skipped.

- [ ] **Step 5: Real run on the demo match (with the user's go-ahead, it costs a little credit)**

Run: `.venv/Scripts/python -m jahbadh.agents data/generated/match-042 --limit 6 --personas pundit,casual --languages en,ar`
Expected: `desk.json` written, summary printed. Read a few claims and rejections together with the user and check they are data-true before calling Plan 2 done. Do not edit generated text.

- [ ] **Step 6: Pause for the user's commit**

Files: `src/jahbadh/agents/spotlight.py`, `__main__.py`, `prompts.py`, `README.md`, `tests/agents/fakes.py`, `tests/agents/test_spotlight.py`, `tests/agents/test_cli.py`. (Never `desk.json` or anything under `data/generated/`.)
Title: `feat(agents): add player spotlights and the desk CLI`
Body: `Spotlights pick the standout players from the impact rankings (involvement, progression, ball wins). One command runs the whole desk over a match and writes a desk.json with every approved claim, render and rejection.`

---

## After Plan 2

- Update the project memory note with the status and anything that surprised us (prompt changes, rejection patterns, real latency per moment).
- Numbers to carry into Plan 4's eval: first-draft pass rate and latency from the Task 13 run.
- Plan 3 picks up: FastAPI + SSE over `run_moment`/`DeskRun`, on-demand persona/language combos with caching, template lines for routine events, pass-network edges without nodes, evidence-frame clamping.
