from fakes import demo_match, scripted_full_desk_client
from jahbadh.agents.__main__ import main
from jahbadh.agents.config import ENV_VARS
from jahbadh.agents.contracts import DeskRun
from jahbadh.simulator.io import save_match


def clear_env(monkeypatch):
    for var in ENV_VARS.values():
        monkeypatch.delenv(var, raising=False)


def test_cli_mermaid_needs_no_key(capsys, monkeypatch, tmp_path):
    save_match(demo_match(), tmp_path / "m")
    monkeypatch.chdir(tmp_path)
    clear_env(monkeypatch)
    assert main([str(tmp_path / "m"), "--mermaid"]) == 0 and "flowchart" in capsys.readouterr().out


def test_cli_without_key_exits_cleanly(capsys, monkeypatch, tmp_path):
    save_match(demo_match(), tmp_path / "m")
    monkeypatch.chdir(tmp_path)                     # no .env here
    clear_env(monkeypatch)
    assert main([str(tmp_path / "m"), "--limit", "1"]) == 2 and "FOUNDRY_API_KEY" in capsys.readouterr().err


def test_cli_writes_desk_json(capsys, monkeypatch, tmp_path):
    save_match(demo_match(), tmp_path / "m")
    monkeypatch.chdir(tmp_path)
    clear_env(monkeypatch)
    monkeypatch.setattr("jahbadh.agents.__main__.make_chat_client", lambda s: scripted_full_desk_client())
    monkeypatch.setenv("FOUNDRY_API_KEY", "test")
    assert main([str(tmp_path / "m"), "--limit", "1", "--no-spotlight", "--languages", "en", "--personas", "pundit"]) == 0
    run = DeskRun.model_validate_json((tmp_path / "m" / "desk.json").read_text(encoding="utf-8"))
    assert [i.moment.kind for i in run.items] == ["card", "full_time"] and run.failures == []
    out = capsys.readouterr().out
    assert "2 moments" in out and "first-draft pass rate" in out


def test_cli_rejects_unknown_persona(capsys, monkeypatch, tmp_path):
    save_match(demo_match(), tmp_path / "m")
    monkeypatch.chdir(tmp_path)
    assert main([str(tmp_path / "m"), "--personas", "pundit,poet"]) == 2 and "poet" in capsys.readouterr().err
