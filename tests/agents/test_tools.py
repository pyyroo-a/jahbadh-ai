import json

from agent_framework import tool

from fakes import demo_match
from jahbadh.agents.evidence import EvidenceStore
from jahbadh.agents.tools import ANALYST_TOOLS, TACTICAL_TOOLS, make_tools


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
    assert "error" in json.loads(tools["get_player_impact"]("NBR-0", 0, 90))


def test_compare_before_after_stays_inside_known_time():
    _, _, tools = tools_for(horizon=4000.0)
    out = json.loads(tools["compare_before_after"]("width", "RMU", 60, 15))
    assert out["id"].endswith("at=3600:window=400")


def test_compare_before_after_needs_time_after():
    _, _, tools = tools_for(horizon=3600.0)
    assert "error" in json.loads(tools["compare_before_after"]("field_tilt", "RMU", 60, 15))


def test_list_events_hides_the_future_and_noise():
    _, _, tools = tools_for(horizon=3601.0)
    lines = json.loads(tools["list_events"](55, 90))
    assert lines and all(int(line.split("'")[0].split()[-1]) <= 61 for line in lines)
    assert not any(" PRESSURE " in line or " CARRY " in line for line in lines)
    assert any("FORMATION_CHANGE" in line for line in lines)


def test_list_events_by_type_and_team():
    _, _, tools = tools_for()
    lines = json.loads(tools["list_events"](0, 90, "GOAL", "RMU"))
    assert lines and all(" RMU GOAL " in line for line in lines)


def test_get_shape_stores_all_three():
    _, store, tools = tools_for()
    out = json.loads(tools["get_shape"]("RMU", 45, 60))
    assert [o["name"] for o in out] == ["line_height", "length", "width"] and all(o["id"] in store for o in out)


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
