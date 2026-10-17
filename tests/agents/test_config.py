from pathlib import Path

import pytest

from jahbadh.agents.config import ENV_VARS, MissingSetting, Settings, load_settings

REPO = Path(__file__).resolve().parents[2]


def test_reads_env_file(tmp_path, monkeypatch):
    for var in ENV_VARS.values():
        monkeypatch.delenv(var, raising=False)
    env = tmp_path / ".env"
    env.write_text("FOUNDRY_API_KEY=abc123\nFOUNDRY_MODEL=gpt-5-mini\nTRANSLATOR_REGION=\n")
    s = load_settings(env)
    assert s.foundry_api_key.get_secret_value() == "abc123"
    assert s.reasoning_effort == "low" and s.translator_region is None
    assert s.foundry_base_url == "https://jahbadh-foundry.services.ai.azure.com/openai/v1/"


def test_environment_beats_env_file(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("FOUNDRY_MODEL=from-file\n")
    monkeypatch.setenv("FOUNDRY_MODEL", "from-env")
    assert load_settings(env).foundry_model == "from-env"


def test_missing_env_file_is_fine(tmp_path, monkeypatch):
    for var in ENV_VARS.values():
        monkeypatch.delenv(var, raising=False)
    assert load_settings(tmp_path / "nope.env").foundry_api_key is None


def test_key_never_shows_in_repr():
    s = Settings(foundry_api_key="abc123", translator_key="xyz789")
    assert "abc123" not in repr(s) and "xyz789" not in repr(s) and "abc123" not in str(s.model_dump())


def test_require_names_the_env_var():
    with pytest.raises(MissingSetting, match="FOUNDRY_API_KEY"):
        Settings().require("foundry_api_key")
    Settings(foundry_api_key="k").require("foundry_api_key")


def test_env_example_lists_every_setting_without_values():
    lines = (REPO / ".env.example").read_text().splitlines()
    pairs = dict(line.split("=", 1) for line in lines if "=" in line and not line.startswith("#"))
    assert set(ENV_VARS.values()) <= set(pairs)
    assert pairs["FOUNDRY_API_KEY"] == "" and pairs["TRANSLATOR_KEY"] == ""
