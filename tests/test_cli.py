from pathlib import Path

from solaxtopvoutput.cli import resolve_config_path


def test_resolve_config_path_prefers_existing_user_path(
    workspace_tmp_path: Path,
    monkeypatch,
) -> None:
    user_config_dir = workspace_tmp_path / "SolaxToPVOutput"
    user_config_dir.mkdir()
    user_config = user_config_dir / "config.yml"
    user_config.write_text("test", encoding="utf-8")

    repo_dir = workspace_tmp_path / "repo"
    repo_dir.mkdir()
    monkeypatch.setenv("APPDATA", str(workspace_tmp_path))
    monkeypatch.chdir(repo_dir)

    resolved = resolve_config_path(None)

    assert resolved == user_config


def test_resolve_config_path_uses_repo_fallback(
    workspace_tmp_path: Path,
    monkeypatch,
) -> None:
    repo_dir = workspace_tmp_path / "repo"
    repo_dir.mkdir()
    repo_config = repo_dir / "config.yml"
    repo_config.write_text("test", encoding="utf-8")

    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.chdir(repo_dir)

    resolved = resolve_config_path(None)

    assert resolved == repo_config
