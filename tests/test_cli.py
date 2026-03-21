import signal
from pathlib import Path

from solaxtopvoutput.cli import (
    install_signal_handlers,
    main,
    resolve_config_path,
)
from solaxtopvoutput.service import UploadResult


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


def test_install_signal_handlers_registers_sigterm(monkeypatch) -> None:
    captured = {}

    def fake_signal(sig, handler):
        captured["sig"] = sig
        captured["handler"] = handler

    monkeypatch.setattr(signal, "signal", fake_signal)

    install_signal_handlers()

    assert captured["sig"] == signal.SIGTERM
    assert callable(captured["handler"])


def test_main_once_uses_configured_log_path(
    workspace_tmp_path: Path,
    monkeypatch,
) -> None:
    config_path = workspace_tmp_path / "config.yml"
    config_path.write_text(
        "\n".join(
            [
                "SolaxToPVOutput:",
                "  logLevel: INFO",
                "  pollIntervalSeconds: 60",
                "  logFile: cli.log",
                "SolaxCloud:",
                "  apiUrl: https://global.solaxcloud.com",
                "  tokenId: token",
                "  registrationNr: wifi",
                "PVOutput:",
                "  systemid: 123",
                "  apikey: key",
            ]
        ),
        encoding="utf-8",
    )

    class DummySession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("solaxtopvoutput.cli.requests.Session", DummySession)
    monkeypatch.setattr(
        "solaxtopvoutput.cli.poll_once",
        lambda config, session, logger: UploadResult(True, 200, "OK"),
    )

    exit_code = main(["--once", "--config", str(config_path)])

    assert exit_code == 0
    assert (workspace_tmp_path / "cli.log").exists()
