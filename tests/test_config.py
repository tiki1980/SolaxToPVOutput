from pathlib import Path

import pytest

from solaxtopvoutput.config import (
    ENV_PVOUTPUT_API_KEY,
    ENV_SOLAX_TOKEN_ID,
    config_search_paths,
    load_config,
)


def write_config(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "SolaxToPVOutput:",
                "  logLevel: INFO",
                "  pollIntervalSeconds: 60",
                "  logFile: app.log",
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


def test_load_config_reads_expected_values(workspace_tmp_path: Path) -> None:
    config_path = workspace_tmp_path / "config.yml"
    write_config(config_path)

    config = load_config(config_path)

    assert config.app.log_level == "INFO"
    assert config.app.poll_interval_seconds == 60
    assert config.app.log_file == "app.log"
    assert config.solax_cloud.registration_nr == "wifi"
    assert config.pvoutput.system_id == 123
    assert config.log_path == workspace_tmp_path / "app.log"


def test_load_config_applies_environment_overrides(
    workspace_tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = workspace_tmp_path / "config.yml"
    write_config(config_path)
    monkeypatch.setenv(ENV_SOLAX_TOKEN_ID, "env-token")
    monkeypatch.setenv(ENV_PVOUTPUT_API_KEY, "env-key")

    config = load_config(config_path)

    assert config.solax_cloud.token_id == "env-token"
    assert config.pvoutput.api_key == "env-key"


def test_load_config_rejects_invalid_log_level(
    workspace_tmp_path: Path,
) -> None:
    config_path = workspace_tmp_path / "config.yml"
    config_path.write_text(
        "\n".join(
            [
                "SolaxToPVOutput:",
                "  logLevel: NOPE",
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

    with pytest.raises(ValueError, match="Invalid log level"):
        load_config(config_path)


def test_config_search_paths_prefers_explicit_env(
    workspace_tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    explicit_path = workspace_tmp_path / "custom.yml"
    monkeypatch.setenv("SOLAXTOPVOUTPUT_CONFIG", str(explicit_path))

    paths = config_search_paths()

    assert paths == [explicit_path]
