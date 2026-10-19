"""Shared helpers for the eval tests.

No conftest.py lives in tests/eval, for the same reason as tests/agents and tests/api. The agent fakes are loaded
by file path, reusing the module if the API helpers already loaded it in this run.
"""

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SHOWCASE_ROOT = REPO / "data" / "showcase"

if "agent_fakes" in sys.modules:
    _fakes = sys.modules["agent_fakes"]
else:
    _spec = importlib.util.spec_from_file_location("agent_fakes", REPO / "tests" / "agents" / "fakes.py")
    _fakes = importlib.util.module_from_spec(_spec)
    sys.modules["agent_fakes"] = _fakes        # its dataclasses look their module up while it loads
    _spec.loader.exec_module(_fakes)

ScriptedChatClient, demo_match = _fakes.ScriptedChatClient, _fakes.demo_match
scripted_full_desk_client, full_time_moment = _fakes.scripted_full_desk_client, _fakes.full_time_moment
