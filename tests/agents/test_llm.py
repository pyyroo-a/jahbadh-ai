import asyncio
import json

import httpx2
import pytest
from pydantic import BaseModel

from fakes import ScriptedChatClient, ToolCall, responses_api_body
from jahbadh.agents.config import MissingSetting, Settings
from jahbadh.agents.llm import AgentOutputError, ask, make_agent, make_chat_client


class Out(BaseModel):
    answer: str


def test_client_sends_responses_request_to_foundry():
    seen = []

    def handler(req):
        seen.append((str(req.url), req.headers["authorization"], json.loads(req.content)))
        return httpx2.Response(200, json=responses_api_body('{"answer": "hi"}'))

    http = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    client = make_chat_client(Settings(foundry_api_key="k"), http_client=http)
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
