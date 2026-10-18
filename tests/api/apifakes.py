"""Shared helpers for the API tests.

No conftest.py lives in tests/api, for the same reason as tests/agents: the analytics tests do
`from conftest import ...`, and a second conftest on sys.path could shadow theirs. The agent fakes are loaded
by file path instead, so these tests also run on their own.
"""

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SHOWCASE_ROOT = REPO / "data" / "showcase"

_spec = importlib.util.spec_from_file_location("agent_fakes", REPO / "tests" / "agents" / "fakes.py")
_fakes = importlib.util.module_from_spec(_spec)
sys.modules["agent_fakes"] = _fakes            # its dataclasses look their module up while it loads
_spec.loader.exec_module(_fakes)
ScriptedChatClient, FakeTranslator, demo_match = _fakes.ScriptedChatClient, _fakes.FakeTranslator, _fakes.demo_match
scripted_full_desk_client, grounded_claim = _fakes.scripted_full_desk_client, _fakes.grounded_claim


async def no_sleep(_s: float) -> None:
    return None


def parse_sse(text: str) -> list[dict]:
    """Server-sent events as {"event", "id", "data"}, data JSON-decoded; keep-alive comments are skipped."""
    messages = []
    for block in text.replace("\r\n", "\n").split("\n\n"):
        msg: dict = {}
        for line in block.split("\n"):
            if not line or line.startswith(":"):
                continue
            key, _, value = line.partition(":")
            value = value.removeprefix(" ")
            if key == "data":
                msg["data"] = msg.get("data", "") + value
            elif key in ("event", "id"):
                msg[key] = value
        if msg:
            if "data" in msg:
                msg["data"] = json.loads(msg["data"])
            messages.append(msg)
    return messages
