"""Integration tests for daemon lifecycle management.

These tests verify the daemon CLI commands work together properly.
Most tests use mocking to avoid actually starting/stopping launchd services.
"""

import subprocess
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from vmlx.cli.main import cli


@pytest.fixture
def runner():
    """Create a Click test runner."""
    return CliRunner()


class TestDaemonLifecycleCommands:
    """Integration tests for daemon command lifecycle."""

    def test_daemon_command_registered(self, runner):
        """Test daemon command is available in main CLI."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "daemon" in result.output

    def test_daemon_start_help(self, runner):
        """Test daemon start --help shows documentation."""
        result = runner.invoke(cli, ["daemon", "start", "--help"])
        assert result.exit_code == 0
        assert "Start the vmlx daemon" in result.output

    def test_daemon_stop_help(self, runner):
        """Test daemon stop --help shows documentation."""
        result = runner.invoke(cli, ["daemon", "stop", "--help"])
        assert result.exit_code == 0
        assert "Stop the vmlx daemon" in result.output

    def test_daemon_restart_help(self, runner):
        """Test daemon restart --help shows documentation."""
        result = runner.invoke(cli, ["daemon", "restart", "--help"])
        assert result.exit_code == 0
        assert "Restart the vmlx daemon" in result.output

    def test_daemon_status_help(self, runner):
        """Test daemon status --help shows documentation."""
        result = runner.invoke(cli, ["daemon", "status", "--help"])
        assert result.exit_code == 0
        assert "Show daemon status" in result.output

    def test_daemon_logs_help(self, runner):
        """Test daemon logs --help shows documentation."""
        result = runner.invoke(cli, ["daemon", "logs", "--help"])
        assert result.exit_code == 0
        assert "View daemon logs" in result.output
        assert "--follow" in result.output
        assert "--lines" in result.output


class TestDaemonStartStopCycle:
    """Tests for complete start/stop cycle."""

    def test_start_stop_cycle_mocked(self, runner):
        """Test full start/stop cycle with mocked launchctl."""
        with (
            patch("vmlx.cli.daemon_cmd.is_daemon_running") as mock_running,
            patch("vmlx.cli.daemon_cmd.get_plist_path") as mock_path,
            patch("vmlx.cli.daemon_cmd.install_plist") as mock_install,
            patch("vmlx.cli.daemon_cmd.load_daemon", return_value=True),
            patch("vmlx.cli.daemon_cmd.unload_daemon", return_value=True),
        ):
            # Set up mock for start command
            mock_running.side_effect = [False, True]  # First call: not running, second: running
            mock_path.return_value = MagicMock(exists=MagicMock(return_value=False))

            # Start daemon
            result = runner.invoke(cli, ["daemon", "start"])
            assert result.exit_code == 0
            assert "started" in result.output.lower()
            mock_install.assert_called_once()

            # Stop daemon
            result = runner.invoke(cli, ["daemon", "stop"])
            assert result.exit_code == 0
            assert "stopped" in result.output.lower()


class TestPlistGeneration:
    """Tests for plist generation and installation."""

    def test_plist_structure(self, tmp_path, monkeypatch):
        """Test generated plist has required structure."""
        import plistlib

        from vmlx.daemon import launchd

        # Use temp directory
        plist_path = tmp_path / "com.vmlx.daemon.plist"
        monkeypatch.setattr(launchd, "get_plist_path", lambda: plist_path)
        monkeypatch.setattr(launchd, "get_log_dir", lambda: tmp_path / "logs")

        # Install plist
        launchd.install_plist()

        # Verify file exists and is valid plist
        assert plist_path.exists()

        with open(plist_path, "rb") as f:
            plist = plistlib.load(f)

        # Verify required keys
        assert plist["Label"] == "com.vmlx.daemon"
        assert plist["RunAtLoad"] is True
        assert "KeepAlive" in plist
        assert "ProgramArguments" in plist
        assert "-m" in plist["ProgramArguments"]
        assert "vmlx.daemon" in plist["ProgramArguments"]


class TestDaemonEntryPoint:
    """Tests for daemon __main__.py entry point."""

    def test_daemon_main_file_exists(self):
        """Test vmlx.daemon.__main__.py exists and has correct structure."""
        from pathlib import Path

        # Find the module file
        import vmlx.daemon

        daemon_pkg_path = Path(vmlx.daemon.__file__).parent
        main_file = daemon_pkg_path / "__main__.py"

        # Verify file exists
        assert main_file.exists()

        # Read and verify content
        content = main_file.read_text()
        assert "from vmlx.config import Config" in content
        assert "from vmlx.daemon.server import run_server" in content
        assert "run_server(" in content


class TestDaemonStatusIntegration:
    """Integration tests for daemon status display."""

    def test_status_table_format(self, runner):
        """Test status command outputs table format."""
        with (
            patch("vmlx.cli.daemon_cmd.is_daemon_running", return_value=False),
            patch("vmlx.cli.daemon_cmd.get_daemon_pid", return_value=None),
            patch("vmlx.cli.daemon_cmd.Config") as mock_config,
        ):
            mock_config.load.return_value = MagicMock(daemon=MagicMock(port=11434))
            result = runner.invoke(cli, ["daemon", "status"])

            assert result.exit_code == 0
            # Should contain table elements
            assert "Status" in result.output
            assert "PID" in result.output
            assert "Port" in result.output


class TestDaemonLogsIntegration:
    """Integration tests for daemon logs functionality."""

    def test_logs_with_existing_file(self, runner, tmp_path, monkeypatch):
        """Test logs command with existing log file."""
        from pathlib import Path

        # Create mock log file
        log_dir = tmp_path / ".vmlx" / "logs"
        log_dir.mkdir(parents=True)
        log_file = log_dir / "daemon.log"
        log_content = "\n".join([f"Log line {i}" for i in range(100)])
        log_file.write_text(log_content)

        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            runner.invoke(cli, ["daemon", "logs", "-n", "20"])

            # Verify tail was called with correct arguments
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert "tail" in args
            assert "-n20" in args


@pytest.mark.slow
class TestRealLaunchctlCommands:
    """Real launchctl tests - only run manually.

    These tests actually interact with launchctl and should be
    run in isolation to avoid affecting the real system daemon.

    Skip by default - run with: pytest -m slow
    """

    def test_launchctl_list_format(self):
        """Test launchctl list output format understanding."""
        # This tests our parsing of launchctl output
        result = subprocess.run(
            ["launchctl", "list"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        # Output should contain header-like content with PID/Status/Label
        assert "PID" in result.stdout or "-" in result.stdout

    def test_launchctl_list_nonexistent(self):
        """Test launchctl list for nonexistent service."""
        result = subprocess.run(
            ["launchctl", "list", "com.nonexistent.service.12345"],
            capture_output=True,
            text=True,
        )
        # Should fail for nonexistent service
        assert result.returncode != 0
