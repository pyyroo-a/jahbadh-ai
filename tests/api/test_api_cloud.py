"""The cloud app with no key and no Azure sign-in: replay still works, live and ingest say no kindly."""

from fastapi.testclient import TestClient

from apifakes import api_settings, no_sleep, parse_sse
from jahbadh.api.app import create_app

CLOUD_VARS = ("FOUNDRY_API_KEY", "TRANSLATOR_KEY", "JAHBADH_AZURE_IDENTITY", "TRANSLATOR_RESOURCE_ID",
              "APPLICATIONINSIGHTS_CONNECTION_STRING")


def test_no_key_and_no_identity_still_serves_replay(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)                      # no .env with keys to find
    for var in CLOUD_VARS:
        monkeypatch.delenv(var, raising=False)
    app = create_app(api_settings(tmp_path, live_mode=True), sleep=no_sleep)
    assert app.state.tracing is False
    with TestClient(app) as client:
        replay = client.get("/api/replay/match-042/stream", params={"from_t": 5390, "speed": 60})
        assert replay.status_code == 200
        messages = parse_sse(replay.text)
        assert messages[0]["event"] == "match" and messages[-1]["event"] == "end"

        live = client.post("/api/live")
        assert live.status_code == 503 and live.json()["detail"] == "Live mode is not set up on this server."
        assert client.get("/api/config").json()["live_remaining"] == 3       # nothing spent

        assert client.post("/api/ingest", json={}).status_code == 404
