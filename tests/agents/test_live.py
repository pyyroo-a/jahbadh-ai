"""Opt-in checks against the real Azure services. They cost a little credit, so they only run with
JAHBADH_LIVE=1 (and the keys in .env). Unit tests never call Azure."""

import asyncio
import os

import pytest
from pydantic import BaseModel

from jahbadh.agents.config import load_settings
from jahbadh.agents.llm import ask, make_agent, make_chat_client
from jahbadh.agents.desk import Desk
from jahbadh.agents.localize import AzureTranslator, survives
from jahbadh.agents.moments import detect_moments
from jahbadh.agents.pipeline import run_moment
from jahbadh.simulator import simulate_match
from jahbadh.simulator.storyline import DEMO_STORYLINE

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


def test_live_translator_keeps_numbers_and_names():
    tr = AzureTranslator(load_settings())
    src = "Northbridge FC had 79% of the final-third passes and 1.13 xG by 61'."
    for lang in ("ar", "es"):
        out = tr.translate([src], lang, ["Northbridge FC"])[0]
        print(lang, out)
        assert survives(src, out, ["Northbridge FC"]) == [], out


def test_live_one_moment_end_to_end():
    m = simulate_match(42, storyline=DEMO_STORYLINE)
    desk = Desk(client=make_chat_client(load_settings()), match=m)
    moment = next(x for x in detect_moments(m) if x.kind == "formation_change")
    item = asyncio.run(run_moment(desk, moment))
    print(item.model_dump_json(indent=2, exclude={"metrics"}))
    assert item.claims or item.rejections      # the desk produced something and the Referee looked at it
