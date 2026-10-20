"""The one place the desk talks to a model: the Foundry client, agent construction and structured asks.

Everything else builds agents through make_agent and asks through ask, so tests can hand in a
scripted chat client and never reach Azure.
"""

from collections.abc import Callable, Sequence
from typing import Literal, TypeVar

import httpx2
from agent_framework import Agent
from agent_framework.openai import OpenAIChatClient
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

from jahbadh.agents.config import Settings

AgentName = Literal["analyst", "tactical", "writer", "referee", "persona", "polish"]
T = TypeVar("T", bound=BaseModel)

AI_SCOPE = "https://ai.azure.com/.default"     # needs "Cognitive Services OpenAI User" on the Foundry resource
RETRY_NOTE ="\n\nYour last reply did not match the required JSON schema. Reply again with valid JSON only."


class AgentOutputError(RuntimeError):
    pass


def make_chat_client(settings: Settings, http_client: httpx2.AsyncClient | None = None) -> OpenAIChatClient:
    """Agent Framework's Responses API client pointed at our Foundry deployment, signed in with the key or, in the
    cloud, with the app's Azure identity (a fresh token for every request, refreshed before it runs out)."""
    if settings.uses_identity:
        api_key = get_bearer_token_provider(DefaultAzureCredential(), AI_SCOPE)
    else:
        settings.require("foundry_api_key")
        api_key = settings.foundry_api_key.get_secret_value()
    openai = AsyncOpenAI(base_url=settings.foundry_base_url, api_key=api_key,
                         max_retries=5, timeout=90, http_client=http_client)
    return OpenAIChatClient(model=settings.foundry_model, async_client=openai,
                            function_invocation_configuration={"max_iterations": 8, "max_function_calls": 16})


def make_agent(client, name: AgentName, instructions: str, tools: Sequence[Callable] = (),
               effort: str = "low") -> Agent:
    return Agent(client=client, name=name, instructions=f"Role: {name}\n{instructions}", tools=list(tools),
                 default_options={"reasoning": {"effort": effort}, "store": False})


async def ask(agent: Agent, prompt: str, schema: type[T]) -> T:
    """Run the agent for a reply shaped like schema. One retry on a bad reply, then AgentOutputError."""
    for attempt in (prompt, prompt + RETRY_NOTE):
        response = await agent.run(attempt, options={"response_format": schema})
        try:
            value = response.value
        except (ValidationError, ValueError):
            continue
        if value is not None:
            return value
    raise AgentOutputError(f"{agent.name}: no valid {schema.__name__} after a retry")
