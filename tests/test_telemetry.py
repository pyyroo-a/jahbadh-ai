from jahbadh import telemetry
from jahbadh.telemetry import setup_tracing


def test_tracing_is_off_without_a_connection_string(monkeypatch):
    calls = []
    monkeypatch.setattr(telemetry, "_started", False)
    monkeypatch.setattr(telemetry, "configure_azure_monitor", lambda **kw: calls.append(("configure", kw)))
    monkeypatch.setattr(telemetry, "enable_instrumentation", lambda **kw: calls.append(("enable", kw)))
    assert setup_tracing({}) is False
    assert setup_tracing({"APPLICATIONINSIGHTS_CONNECTION_STRING": "  "}) is False
    assert calls == []


def test_tracing_turns_on_once_with_a_connection_string(monkeypatch):
    calls = []
    monkeypatch.setattr(telemetry, "_started", False)
    monkeypatch.setattr(telemetry, "create_resource", lambda **kw: ("resource", kw["service_name"]))
    monkeypatch.setattr(telemetry, "configure_azure_monitor", lambda **kw: calls.append(("configure", kw)))
    monkeypatch.setattr(telemetry, "enable_instrumentation", lambda **kw: calls.append(("enable", kw)))
    env = {"APPLICATIONINSIGHTS_CONNECTION_STRING": "InstrumentationKey=00000000-0000-0000-0000-000000000000"}
    assert setup_tracing(env) is True
    assert setup_tracing(env) is True
    assert calls == [
        ("configure", {"connection_string": env["APPLICATIONINSIGHTS_CONNECTION_STRING"],
                       "resource": ("resource", "jahbadh")}),
        ("enable", {"enable_sensitive_data": True}),
    ]
