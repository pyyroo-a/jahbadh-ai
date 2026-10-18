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


def test_match_stats_by_half_respects_the_horizon():
    _, _, tools = tools_for(horizon=3000.0)
    assert json.loads(tools["get_match_stats"]("RMU", "second_half"))["window"] == "46'-50'"
    assert json.loads(tools["get_match_stats"]("RMU", "first_half"))["window"] == "1'-45'"
    assert "error" in json.loads(tools_for(horizon=2000.0)[2]["get_match_stats"]("RMU", "second_half"))


def test_shot_map_summary_lists_every_shot():
    _, _, tools = tools_for()
    out = json.loads(tools["get_shot_map"]("RMU", 0, 90))
    assert len(out["extra"]["shots"]) == out["fields"]["value"]
    assert {"get_match_stats"} <= set(ANALYST_TOOLS) and {"get_shot_map", "get_attacking_sides"} <= set(TACTICAL_TOOLS)


def test_new_tools_store_their_metrics():
    _, store, tools = tools_for()
    physical = json.loads(tools["get_physical"]("RMU-33"))
    passing = json.loads(tools["get_pass_quality"]("NBR"))
    rhythm = json.loads(tools["get_game_rhythm"]())
    alerts = json.loads(tools["get_physical_alerts"]())
    assert physical["id"] == "physical:RMU-33:0-5400" and passing["id"] == "pass_quality:NBR:0-5400"
    assert rhythm["id"] == "game_rhythm:MATCH:0-5400" and rhythm["fields"]["label"] in ("controlled", "balanced", "chaotic")
    assert 0 < len(alerts) <= 15 and all(a["id"] in store for a in alerts)
    assert {physical["id"], passing["id"], rhythm["id"]} <= {m.id for m in store.metrics()}
    assert {"get_physical", "get_physical_alerts", "get_pass_quality", "get_game_rhythm"} <= set(TACTICAL_TOOLS)


def test_tools_clamp_new_metrics_to_the_horizon():
    _, store, tools = tools_for(horizon=601.0)
    assert json.loads(tools["get_physical"]("RMU-33", 0, 90))["window"] == "1'-11'"
    assert json.loads(tools["get_game_rhythm"](0, 90))["id"] == "game_rhythm:MATCH:0-601"
    assert json.loads(tools["get_pass_quality"]("RMU", 0, 90))["id"] == "pass_quality:RMU:0-601"
    alerts = json.loads(tools["get_physical_alerts"](90))
    assert alerts and all(store.get(a["id"]).window[1] <= 601 for a in alerts)
    assert "error" in json.loads(tools["get_physical"]("XYZ-1"))


def test_shot_map_summary_carries_shot_speed():
    _, _, tools = tools_for()
    shots = json.loads(tools["get_shot_map"]("RMU", 0, 90))["extra"]["shots"]
    assert all(len(s) == 7 and 35 <= s[6] <= 125 for s in shots)


def test_tactical_instructions_mention_the_new_tools():
    from jahbadh.agents.prompts import INSTRUCTIONS
    for name in ("get_physical", "get_physical_alerts", "get_pass_quality", "get_game_rhythm"):
        assert name in INSTRUCTIONS["tactical"]
