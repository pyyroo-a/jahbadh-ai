"""Offline stand-ins for the model and translator, plus shared match helpers for the agent tests.

No conftest.py lives in tests/agents on purpose: the analytics tests do `from conftest import ...`,
and a second module named conftest on sys.path could shadow theirs. The analytics helpers are
loaded here by file path instead.
"""

from __future__ import annotations

import importlib.util
import json
from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

from agent_framework import BaseChatClient, ChatResponse, Content, FunctionInvocationLayer, Message
from pydantic import BaseModel

from jahbadh.schemas import Match
from jahbadh.simulator import simulate_match
from jahbadh.simulator.storyline import DEMO_STORYLINE

_spec = importlib.util.spec_from_file_location(
    "analytics_helpers", Path(__file__).resolve().parents[1] / "analytics" / "conftest.py")
_helpers = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_helpers)
make_match, p, pr, shot, shot_by = _helpers.make_match, _helpers.p, _helpers.pr, _helpers.shot, _helpers.shot_by
tackle, intercept, static_tracking, pass_xy = _helpers.tackle, _helpers.intercept, _helpers.static_tracking, _helpers.pass_xy


@cache
def demo_match() -> Match:
    """Seed 42 with the demo storyline (the 61' switch to a back three). Shared, so never mutate it."""
    return simulate_match(42, storyline=DEMO_STORYLINE)


@dataclass
class ToolCall:
    name: str
    args: dict


Reply = str | dict | BaseModel | ToolCall | Callable[[list[Message], dict], Any]


class ScriptedChatClient(FunctionInvocationLayer, BaseChatClient):
    """A chat client that answers from a script instead of a model.

    Each agent's instructions start with "Role: <name>", so replies are scripted per role. A reply can be
    a tool call (the real Agent Framework loop then runs the tool), a model or dict (sent as JSON text),
    plain text, or a callable that builds one of those from the messages and options.
    """

    def __init__(self, script: dict[str, list[Reply]], defaults: dict[str, Reply] | None = None):
        super().__init__()
        self.script = {role: list(replies) for role, replies in script.items()}
        self.defaults = dict(defaults or {})
        self.calls: list[tuple[str, list[str], dict]] = []

    def _inner_get_response(self, *, messages, stream, options, **kwargs):
        assert not stream, "the desk never streams"
        return self._reply(messages, options)

    async def _reply(self, messages, options) -> ChatResponse:
        role = options["instructions"].splitlines()[0].removeprefix("Role: ").strip()
        self.calls.append((role, [m.text for m in messages], dict(options)))
        queue = self.script.get(role, [])
        if queue:
            reply = queue.pop(0)
        elif role in self.defaults:
            reply = self.defaults[role]
        else:
            raise AssertionError(f"no scripted reply left for {role}")
        while callable(reply) and not isinstance(reply, (BaseModel, ToolCall)):
            reply = reply(list(messages), dict(options))
        if isinstance(reply, ToolCall):
            content = Content.from_function_call(call_id=f"call-{len(self.calls)}", name=reply.name, arguments=reply.args)
            return ChatResponse(messages=[Message(role="assistant", contents=[content])])
        if isinstance(reply, BaseModel):
            text = reply.model_dump_json()
        elif isinstance(reply, dict):
            text = json.dumps(reply)
        else:
            text = reply
        return ChatResponse(messages=[Message(role="assistant", contents=[text])])


class FakeTranslator:
    """Stands in for Azure AI Translator: tags each text with the target language, or mangles it on request."""

    def __init__(self, mangle=None):
        self.mangle, self.calls = mangle, []

    def translate(self, texts, to, keep):
        self.calls.append((list(texts), to, list(keep)))
        return [self.mangle(t) if self.mangle else f"[{to}] {t}" for t in texts]


def full_time_moment():
    from jahbadh.agents.moments import detect_moments
    return detect_moments(demo_match())[-1]


def run_for(script: dict, moment=None, **desk_kw):
    """A MomentRun on the demo match with a scripted client; the 61' switch unless a moment is given."""
    from jahbadh.agents.desk import Desk
    from jahbadh.agents.moments import detect_moments
    m = demo_match()
    moment = moment or next(x for x in detect_moments(m) if x.kind == "formation_change")
    return Desk(client=ScriptedChatClient(script), match=m, **desk_kw).start(moment)


def grounded_claim(personas=("pundit",), languages=("en",), translator=None):
    """A full-time run with NBR's field tilt in the store and a claim that passes the deterministic check."""
    from jahbadh.agents.contracts import Claim, Figure
    from jahbadh.analytics import field_tilt
    run = run_for({}, moment=full_time_moment(), personas=personas, languages=languages, translator=translator)
    tilt = run.store.add(field_tilt(run.desk.match, "NBR"))
    pct = f"{round(tilt.value * 100)}%"
    claim = Claim(id="full_time-5400:c1", text=f"Northbridge FC had {pct} of the final-third passes.",
                  metric_ids=[tilt.id], event_ids=[], figures=[Figure(metric_id=tilt.id, field="value", written=pct)])
    return run, claim


def responses_api_body(text: str) -> dict:
    """A minimal completed Responses API reply, for tests that fake the HTTP layer."""
    return {
        "id": "resp_1", "object": "response", "created_at": 0, "model": "gpt-5-mini", "status": "completed",
        "output": [{"type": "message", "id": "m1", "role": "assistant", "status": "completed",
                    "content": [{"type": "output_text", "text": text, "annotations": []}]}],
        "parallel_tool_calls": True, "tool_choice": "auto", "tools": [],
        "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2,
                  "input_tokens_details": {"cached_tokens": 0}, "output_tokens_details": {"reasoning_tokens": 0}},
    }
