"""Tests for `vllmlx run` CLI behavior."""

from types import SimpleNamespace
from unittest.mock import patch

from click.testing import CliRunner

from vllmlx.cli.main import cli
from vllmlx.config import RuntimeConfigError


def test_run_help_has_no_daemon_flag():
    runner = CliRunner()
    result = runner.invoke(cli, ["run", "--help"])

    assert result.exit_code == 0
    assert "--daemon" not in result.output


def test_run_rejects_legacy_daemon_flag():
    runner = CliRunner()
    result = runner.invoke(cli, ["run", "--daemon"])

    assert result.exit_code != 0
    assert "No such option" in result.output


def test_run_starts_daemon_when_not_running():
    runner = CliRunner()
    config = SimpleNamespace(
        daemon=SimpleNamespace(host="127.0.0.1", port=8000),
        backend=SimpleNamespace(port=8001),
        models=SimpleNamespace(default=""),
        aliases={},
        validate_runtime=lambda: None,
    )

    with (
        patch("vllmlx.config.Config.load", return_value=config),
        patch("vllmlx.cli.run._ensure_daemon_ready", return_value=True) as mock_ready,
        patch("vllmlx.models.aliases.resolve_alias", return_value="mlx-community/Qwen3-8B-4bit"),
        patch("vllmlx.chat.repl.start_chat") as mock_start_chat,
    ):
        result = runner.invoke(cli, ["run", "qwen3-8b-4bit"])

    assert result.exit_code == 0
    mock_ready.assert_called_once_with(config)
    mock_start_chat.assert_called_once_with(
        "mlx-community/Qwen3-8B-4bit",
        "http://127.0.0.1:8000",
    )


def test_run_exits_when_daemon_cannot_be_started():
    runner = CliRunner()
    config = SimpleNamespace(
        daemon=SimpleNamespace(host="127.0.0.1", port=8000),
        backend=SimpleNamespace(port=8001),
        models=SimpleNamespace(default=""),
        aliases={},
        validate_runtime=lambda: None,
    )

    with (
        patch("vllmlx.config.Config.load", return_value=config),
        patch("vllmlx.cli.run._ensure_daemon_ready", return_value=False),
        patch("vllmlx.models.aliases.resolve_alias", return_value="mlx-community/Qwen3-8B-4bit"),
        patch("vllmlx.chat.repl.start_chat") as mock_start_chat,
    ):
        result = runner.invoke(cli, ["run", "qwen3-8b-4bit"])

    assert result.exit_code == 1
    assert "Failed to start daemon" in result.output
    mock_start_chat.assert_not_called()


def test_run_exits_when_backend_port_matches_daemon_port():
    runner = CliRunner()
    config = SimpleNamespace(
        daemon=SimpleNamespace(host="127.0.0.1", port=8000),
        backend=SimpleNamespace(port=8000),
        models=SimpleNamespace(default=""),
        aliases={},
        validate_runtime=lambda: (_ for _ in ()).throw(
            RuntimeConfigError("backend.port must differ from daemon.port")
        ),
    )

    with (
        patch("vllmlx.config.Config.load", return_value=config),
        patch("vllmlx.chat.repl.start_chat") as mock_start_chat,
    ):
        result = runner.invoke(cli, ["run", "qwen3-8b-4bit"])

    assert result.exit_code == 1
    assert "backend.port must differ from daemon.port" in result.output
    mock_start_chat.assert_not_called()
