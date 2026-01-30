"""Tests for daemon CLI commands."""

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from vmlx.cli.daemon_cmd import daemon


@pytest.fixture
def runner():
    """Create a Click test runner."""
    return CliRunner()


class TestDaemonGroup:
    """Tests for the daemon command group."""

    def test_daemon_help(self, runner):
        """Test daemon --help shows subcommands."""
        result = runner.invoke(daemon, ["--help"])
        assert result.exit_code == 0
        assert "start" in result.output
        assert "stop" in result.output
        assert "restart" in result.output
        assert "status" in result.output
        assert "logs" in result.output


class TestDaemonStart:
    """Tests for `vmlx daemon start`."""

    def test_start_when_already_running(self, runner):
        """Test start shows message when daemon already running."""
        with patch("vmlx.cli.daemon_cmd.is_daemon_running", return_value=True):
            result = runner.invoke(daemon, ["start"])
            assert result.exit_code == 0
            assert "already running" in result.output.lower()

    def test_start_installs_plist_if_missing(self, runner):
        """Test start installs plist if not present."""
        with (
            patch("vmlx.cli.daemon_cmd.is_daemon_running", return_value=False),
            patch("vmlx.cli.daemon_cmd.get_plist_path") as mock_plist_path,
            patch("vmlx.cli.daemon_cmd.install_plist") as mock_install,
            patch("vmlx.cli.daemon_cmd.load_daemon", return_value=True),
        ):
            mock_plist_path.return_value = MagicMock(exists=MagicMock(return_value=False))
            runner.invoke(daemon, ["start"])
            mock_install.assert_called_once()

    def test_start_loads_daemon(self, runner):
        """Test start loads daemon with launchctl."""
        with (
            patch("vmlx.cli.daemon_cmd.is_daemon_running", return_value=False),
            patch("vmlx.cli.daemon_cmd.get_plist_path") as mock_plist_path,
            patch("vmlx.cli.daemon_cmd.install_plist"),
            patch("vmlx.cli.daemon_cmd.load_daemon", return_value=True) as mock_load,
        ):
            mock_plist_path.return_value = MagicMock(exists=MagicMock(return_value=True))
            result = runner.invoke(daemon, ["start"])
            assert result.exit_code == 0
            mock_load.assert_called_once()

    def test_start_shows_success_message(self, runner):
        """Test start shows success message on completion."""
        with (
            patch("vmlx.cli.daemon_cmd.is_daemon_running", return_value=False),
            patch("vmlx.cli.daemon_cmd.get_plist_path") as mock_plist_path,
            patch("vmlx.cli.daemon_cmd.install_plist"),
            patch("vmlx.cli.daemon_cmd.load_daemon", return_value=True),
        ):
            mock_plist_path.return_value = MagicMock(exists=MagicMock(return_value=True))
            result = runner.invoke(daemon, ["start"])
            assert "started" in result.output.lower()

    def test_start_shows_failure_on_load_error(self, runner):
        """Test start shows failure message when load fails."""
        with (
            patch("vmlx.cli.daemon_cmd.is_daemon_running", return_value=False),
            patch("vmlx.cli.daemon_cmd.get_plist_path") as mock_plist_path,
            patch("vmlx.cli.daemon_cmd.install_plist"),
            patch("vmlx.cli.daemon_cmd.load_daemon", return_value=False),
        ):
            mock_plist_path.return_value = MagicMock(exists=MagicMock(return_value=True))
            result = runner.invoke(daemon, ["start"])
            assert result.exit_code == 1
            assert "failed" in result.output.lower()


class TestDaemonStop:
    """Tests for `vmlx daemon stop`."""

    def test_stop_when_not_running(self, runner):
        """Test stop shows message when daemon not running."""
        with patch("vmlx.cli.daemon_cmd.is_daemon_running", return_value=False):
            result = runner.invoke(daemon, ["stop"])
            assert result.exit_code == 0
            assert "not running" in result.output.lower()

    def test_stop_unloads_daemon(self, runner):
        """Test stop unloads daemon with launchctl."""
        with (
            patch("vmlx.cli.daemon_cmd.is_daemon_running", return_value=True),
            patch("vmlx.cli.daemon_cmd.unload_daemon", return_value=True) as mock_unload,
        ):
            result = runner.invoke(daemon, ["stop"])
            assert result.exit_code == 0
            mock_unload.assert_called_once()

    def test_stop_shows_success_message(self, runner):
        """Test stop shows success message on completion."""
        with (
            patch("vmlx.cli.daemon_cmd.is_daemon_running", return_value=True),
            patch("vmlx.cli.daemon_cmd.unload_daemon", return_value=True),
        ):
            result = runner.invoke(daemon, ["stop"])
            assert "stopped" in result.output.lower()

    def test_stop_shows_failure_on_unload_error(self, runner):
        """Test stop shows failure message when unload fails."""
        with (
            patch("vmlx.cli.daemon_cmd.is_daemon_running", return_value=True),
            patch("vmlx.cli.daemon_cmd.unload_daemon", return_value=False),
        ):
            result = runner.invoke(daemon, ["stop"])
            assert result.exit_code == 1
            assert "failed" in result.output.lower()


class TestDaemonRestart:
    """Tests for `vmlx daemon restart`."""

    def test_restart_stops_then_starts(self, runner):
        """Test restart calls unload then load."""
        with (
            patch("vmlx.cli.daemon_cmd.unload_daemon", return_value=True) as mock_unload,
            patch("vmlx.cli.daemon_cmd.get_plist_path") as mock_plist_path,
            patch("vmlx.cli.daemon_cmd.install_plist"),
            patch("vmlx.cli.daemon_cmd.load_daemon", return_value=True) as mock_load,
            patch("time.sleep"),  # Don't actually sleep in tests
        ):
            mock_plist_path.return_value = MagicMock(exists=MagicMock(return_value=True))
            result = runner.invoke(daemon, ["restart"])
            assert result.exit_code == 0
            mock_unload.assert_called_once()
            mock_load.assert_called_once()

    def test_restart_installs_plist_if_missing(self, runner):
        """Test restart installs plist if not present."""
        with (
            patch("vmlx.cli.daemon_cmd.unload_daemon", return_value=True),
            patch("vmlx.cli.daemon_cmd.get_plist_path") as mock_plist_path,
            patch("vmlx.cli.daemon_cmd.install_plist") as mock_install,
            patch("vmlx.cli.daemon_cmd.load_daemon", return_value=True),
            patch("time.sleep"),
        ):
            mock_plist_path.return_value = MagicMock(exists=MagicMock(return_value=False))
            runner.invoke(daemon, ["restart"])
            mock_install.assert_called_once()


class TestDaemonStatus:
    """Tests for `vmlx daemon status`."""

    def test_status_shows_running(self, runner):
        """Test status shows running state."""
        with (
            patch("vmlx.cli.daemon_cmd.is_daemon_running", return_value=True),
            patch("vmlx.cli.daemon_cmd.get_daemon_pid", return_value=12345),
            patch("vmlx.cli.daemon_cmd.Config") as mock_config,
            patch("vmlx.cli.daemon_cmd.httpx"),
        ):
            mock_config.load.return_value = MagicMock(daemon=MagicMock(port=11434))
            result = runner.invoke(daemon, ["status"])
            assert result.exit_code == 0
            assert "running" in result.output.lower()
            assert "12345" in result.output

    def test_status_shows_stopped(self, runner):
        """Test status shows stopped state."""
        with (
            patch("vmlx.cli.daemon_cmd.is_daemon_running", return_value=False),
            patch("vmlx.cli.daemon_cmd.get_daemon_pid", return_value=None),
            patch("vmlx.cli.daemon_cmd.Config") as mock_config,
        ):
            mock_config.load.return_value = MagicMock(daemon=MagicMock(port=11434))
            result = runner.invoke(daemon, ["status"])
            assert result.exit_code == 0
            assert "stopped" in result.output.lower()


class TestDaemonLogs:
    """Tests for `vmlx daemon logs`."""

    def test_logs_shows_missing_file_message(self, runner, tmp_path, monkeypatch):
        """Test logs shows message when log file missing."""
        from pathlib import Path

        # Patch Path.home to use temp directory
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        result = runner.invoke(daemon, ["logs"])
        assert "not found" in result.output.lower()

    def test_logs_default_lines(self, runner, tmp_path, monkeypatch):
        """Test logs shows default number of lines."""
        from pathlib import Path

        # Create mock log file
        log_dir = tmp_path / ".vmlx" / "logs"
        log_dir.mkdir(parents=True)
        log_file = log_dir / "daemon.log"
        log_file.write_text("log line 1\nlog line 2\n")

        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            runner.invoke(daemon, ["logs"])
            # Should call tail with -n50 by default
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert "tail" in args
            assert "-n50" in args

    def test_logs_custom_lines(self, runner, tmp_path, monkeypatch):
        """Test logs with custom line count."""
        from pathlib import Path

        log_dir = tmp_path / ".vmlx" / "logs"
        log_dir.mkdir(parents=True)
        log_file = log_dir / "daemon.log"
        log_file.write_text("log content")

        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            runner.invoke(daemon, ["logs", "-n", "100"])
            args = mock_run.call_args[0][0]
            assert "-n100" in args

    def test_logs_follow_flag(self, runner, tmp_path, monkeypatch):
        """Test logs with --follow flag."""
        from pathlib import Path

        log_dir = tmp_path / ".vmlx" / "logs"
        log_dir.mkdir(parents=True)
        log_file = log_dir / "daemon.log"
        log_file.write_text("log content")

        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            runner.invoke(daemon, ["logs", "-f"])
            args = mock_run.call_args[0][0]
            assert "-f" in args
