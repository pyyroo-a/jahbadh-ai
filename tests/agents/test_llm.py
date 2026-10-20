import asyncio
import json
import time

import httpx2
import pytest
from azure.core.credentials import AccessToken, AccessTokenInfo, AzureKeyCredential
from pydantic import BaseModel

from fakes import ScriptedChatClient, ToolCall, responses_api_body
from jahbadh.agents import llm, localize
from jahbadh.agents.config import MissingSetting, Settings, load_settings
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


def test_a_key_wins_over_the_identity():
    assert Settings(azure_identity=True).uses_identity is True
    assert Settings(azure_identity=True, foundry_api_key="k").uses_identity is False
    assert Settings().uses_identity is False


def test_the_identity_switch_is_read_from_the_environment(tmp_path, monkeypatch):
    for var in ("FOUNDRY_API_KEY", "JAHBADH_AZURE_IDENTITY", "TRANSLATOR_RESOURCE_ID"):
        monkeypatch.delenv(var, raising=False)
    assert load_settings(None).azure_identity is False
    monkeypatch.setenv("JAHBADH_AZURE_IDENTITY", "on")
    monkeypatch.setenv("TRANSLATOR_RESOURCE_ID", "/subscriptions/s/resourceGroups/g/providers/x/accounts/t")
    settings = load_settings(None)
    assert settings.uses_identity and settings.translator_resource_id.endswith("/accounts/t")
    monkeypatch.setenv("JAHBADH_AZURE_IDENTITY", "off")
    assert load_settings(None).azure_identity is False


class FakeAsyncCredential:
    def __init__(self):
        self.scopes = []

    async def get_token(self, *scopes, **kwargs):
        self.scopes.append(scopes)
        return AccessToken("identity-token", int(time.time()) + 3600)

    async def get_token_info(self, *scopes, options=None):
        self.scopes.append(scopes)
        return AccessTokenInfo("identity-token", int(time.time()) + 3600)

    async def close(self):
        pass


def test_identity_uses_a_token_provider_for_the_ai_scope(monkeypatch):
    credential = FakeAsyncCredential()
    monkeypatch.setattr(llm, "DefaultAzureCredential", lambda: credential)
    seen = []

    def handler(req):
        seen.append(req.headers["authorization"])
        return httpx2.Response(200, json=responses_api_body('{"answer": "hi"}'))

    http = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    client = make_chat_client(Settings(azure_identity=True), http_client=http)
    out = asyncio.run(ask(make_agent(client, "writer", "be brief"), "go", Out))
    assert out == Out(answer="hi")
    assert seen == ["Bearer identity-token"]
    assert credential.scopes and all(s == ("https://ai.azure.com/.default",) for s in credential.scopes)


def test_translator_signs_in_with_the_identity_when_it_has_no_key(monkeypatch):
    made = []
    monkeypatch.setattr(localize, "DefaultAzureCredential", lambda: "the-identity")
    monkeypatch.setattr(localize, "TextTranslationClient", lambda **kw: made.append(kw))
    resource = "/subscriptions/s/resourceGroups/g/providers/Microsoft.CognitiveServices/accounts/t"
    localize.AzureTranslator(Settings(azure_identity=True, translator_resource_id=resource,
                                      translator_region="uaenorth"))
    assert made[-1]["credential"] == "the-identity"
    assert made[-1]["resource_id"] == resource and made[-1]["region"] == "uaenorth"

    localize.AzureTranslator(Settings(azure_identity=True, translator_resource_id=resource,
                                      translator_key="k", translator_region="uaenorth"))
    assert isinstance(made[-1]["credential"], AzureKeyCredential) and "resource_id" not in made[-1]

    with pytest.raises(MissingSetting, match="TRANSLATOR_KEY"):
        localize.AzureTranslator(Settings(azure_identity=True, translator_region="uaenorth"))


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
