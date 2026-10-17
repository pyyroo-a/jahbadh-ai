"""Opt-in checks against the real Azure services. They cost a little credit, so they only run with
JAHBADH_LIVE=1 (and the keys in .env). Unit tests never call Azure."""

import asyncio
import os

import pytest
from pydantic import BaseModel

from jahbadh.agents.config import load_settings
from jahbadh.agents.llm import ask, make_agent, make_chat_client

pytestmark = [pytest.mark.live,
              pytest.mark.skipif(os.environ.get("JAHBADH_LIVE") != "1", reason="set JAHBADH_LIVE=1 to call Azure")]


class Out(BaseModel):
    answer: str


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
