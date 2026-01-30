"""Tests for launchd integration module."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest


class TestConstants:
    """Tests for launchd module constants."""

    def test_label_format(self):
        """Test LABEL follows reverse-DNS convention."""
        from vmlx.daemon.launchd import LABEL

        assert LABEL == "com.vmlx.daemon"

    def test_plist_name_matches_label(self):
        """Test PLIST_NAME is derived from LABEL."""
        from vmlx.daemon.launchd import LABEL, PLIST_NAME

        assert PLIST_NAME == f"{LABEL}.plist"


class TestGetPlistPath:
    """Tests for get_plist_path function."""

    def test_plist_path_in_launch_agents(self):
        """Test plist path is in LaunchAgents directory."""
        from vmlx.daemon.launchd import get_plist_path

        path = get_plist_path()
        assert "LaunchAgents" in str(path)

    def test_plist_path_is_absolute(self):
        """Test plist path is absolute."""
        from vmlx.daemon.launchd import get_plist_path

        path = get_plist_path()
        assert path.is_absolute()

    def test_plist_path_ends_with_correct_name(self):
        """Test plist path has correct filename."""
        from vmlx.daemon.launchd import LABEL, get_plist_path

        path = get_plist_path()
        assert path.name == f"{LABEL}.plist"


class TestGetLogDir:
    """Tests for get_log_dir function."""

    def test_log_dir_in_vmlx_directory(self):
        """Test log directory is under .vmlx."""
        from vmlx.daemon.launchd import get_log_dir

        log_dir = get_log_dir()
        assert ".vmlx" in str(log_dir)
        assert "logs" in str(log_dir)

    def test_log_dir_is_absolute(self):
        """Test log directory path is absolute."""
        from vmlx.daemon.launchd import get_log_dir

        log_dir = get_log_dir()
        assert log_dir.is_absolute()


class TestGetPythonPath:
    """Tests for get_python_path function."""

    def test_returns_current_python(self):
        """Test returns current Python interpreter path."""
        from vmlx.daemon.launchd import get_python_path

        python_path = get_python_path()
        assert python_path == sys.executable


class TestGeneratePlist:
    """Tests for generate_plist function."""

    def test_has_label(self):
        """Test plist has Label key."""
        from vmlx.daemon.launchd import LABEL, generate_plist

        plist = generate_plist()
        assert plist["Label"] == LABEL

    def test_has_program_arguments(self):
        """Test plist has ProgramArguments."""
        from vmlx.daemon.launchd import generate_plist

        plist = generate_plist()
        assert "ProgramArguments" in plist
        assert len(plist["ProgramArguments"]) >= 3

    def test_program_arguments_uses_current_python(self):
        """Test plist uses current Python interpreter."""
        from vmlx.daemon.launchd import generate_plist

        plist = generate_plist()
        assert sys.executable in plist["ProgramArguments"]

    def test_program_arguments_runs_daemon_module(self):
        """Test plist runs vmlx.daemon as module."""
        from vmlx.daemon.launchd import generate_plist

        plist = generate_plist()
        args = plist["ProgramArguments"]
        assert "-m" in args
        assert "vmlx.daemon" in args

    def test_run_at_load_is_true(self):
        """Test RunAtLoad is enabled."""
        from vmlx.daemon.launchd import generate_plist

        plist = generate_plist()
        assert plist["RunAtLoad"] is True

    def test_has_keep_alive(self):
        """Test plist has KeepAlive configuration."""
        from vmlx.daemon.launchd import generate_plist

        plist = generate_plist()
        assert "KeepAlive" in plist

    def test_keep_alive_restarts_on_crash(self):
        """Test KeepAlive restarts on non-zero exit."""
        from vmlx.daemon.launchd import generate_plist

        plist = generate_plist()
        # SuccessfulExit: false means restart on crash, not clean exit
        assert plist["KeepAlive"]["SuccessfulExit"] is False

    def test_has_standard_out_path(self):
        """Test plist has stdout log path."""
        from vmlx.daemon.launchd import generate_plist

        plist = generate_plist()
        assert "StandardOutPath" in plist
        assert "daemon.log" in plist["StandardOutPath"]

    def test_has_standard_error_path(self):
        """Test plist has stderr log path."""
        from vmlx.daemon.launchd import generate_plist

        plist = generate_plist()
        assert "StandardErrorPath" in plist
        assert "daemon.error.log" in plist["StandardErrorPath"]

    def test_has_environment_variables(self):
        """Test plist has environment variables."""
        from vmlx.daemon.launchd import generate_plist

        plist = generate_plist()
        assert "EnvironmentVariables" in plist
        assert "PATH" in plist["EnvironmentVariables"]
        assert "HOME" in plist["EnvironmentVariables"]

    def test_has_working_directory(self):
        """Test plist has working directory set to home."""
        from vmlx.daemon.launchd import generate_plist

        plist = generate_plist()
        assert "WorkingDirectory" in plist
        assert plist["WorkingDirectory"] == str(Path.home())


class TestInstallPlist:
    """Tests for install_plist function."""

    def test_creates_plist_file(self, tmp_path, monkeypatch):
        """Test install_plist creates the plist file."""
        from vmlx.daemon import launchd

        # Mock the plist path to use temp directory
        plist_path = tmp_path / "LaunchAgents" / "com.vmlx.daemon.plist"
        monkeypatch.setattr(launchd, "get_plist_path", lambda: plist_path)

        # Mock log dir to use temp directory
        log_dir = tmp_path / ".vmlx" / "logs"
        monkeypatch.setattr(launchd, "get_log_dir", lambda: log_dir)

        launchd.install_plist()

        assert plist_path.exists()

    def test_creates_parent_directories(self, tmp_path, monkeypatch):
        """Test install_plist creates parent directories."""
        from vmlx.daemon import launchd

        plist_path = tmp_path / "deep" / "path" / "com.vmlx.daemon.plist"
        monkeypatch.setattr(launchd, "get_plist_path", lambda: plist_path)
        monkeypatch.setattr(launchd, "get_log_dir", lambda: tmp_path / "logs")

        launchd.install_plist()

        assert plist_path.parent.exists()


class TestUninstallPlist:
    """Tests for uninstall_plist function."""

    def test_removes_existing_plist(self, tmp_path, monkeypatch):
        """Test uninstall_plist removes existing plist file."""
        from vmlx.daemon import launchd

        # Create a mock plist file
        plist_path = tmp_path / "com.vmlx.daemon.plist"
        plist_path.write_text("test")
        monkeypatch.setattr(launchd, "get_plist_path", lambda: plist_path)

        launchd.uninstall_plist()

        assert not plist_path.exists()

    def test_handles_nonexistent_plist(self, tmp_path, monkeypatch):
        """Test uninstall_plist handles missing file gracefully."""
        from vmlx.daemon import launchd

        plist_path = tmp_path / "nonexistent.plist"
        monkeypatch.setattr(launchd, "get_plist_path", lambda: plist_path)

        # Should not raise
        launchd.uninstall_plist()


class TestLoadDaemon:
    """Tests for load_daemon function."""

    def test_raises_if_plist_not_found(self, tmp_path, monkeypatch):
        """Test load_daemon raises if plist doesn't exist."""
        from vmlx.daemon import launchd

        plist_path = tmp_path / "nonexistent.plist"
        monkeypatch.setattr(launchd, "get_plist_path", lambda: plist_path)

        with pytest.raises(FileNotFoundError):
            launchd.load_daemon()

    def test_calls_launchctl_load(self, tmp_path, monkeypatch):
        """Test load_daemon calls launchctl load."""
        from vmlx.daemon import launchd

        # Create mock plist
        plist_path = tmp_path / "com.vmlx.daemon.plist"
        plist_path.write_text("test")
        monkeypatch.setattr(launchd, "get_plist_path", lambda: plist_path)

        # Mock subprocess.run
        mock_run = MagicMock(return_value=MagicMock(returncode=0, stderr=""))
        monkeypatch.setattr("subprocess.run", mock_run)

        result = launchd.load_daemon()

        assert result is True
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[0] == "launchctl"
        assert args[1] == "load"

    def test_handles_already_loaded(self, tmp_path, monkeypatch):
        """Test load_daemon handles already loaded state."""
        from vmlx.daemon import launchd

        plist_path = tmp_path / "com.vmlx.daemon.plist"
        plist_path.write_text("test")
        monkeypatch.setattr(launchd, "get_plist_path", lambda: plist_path)

        # Mock subprocess.run returning "already loaded" error
        mock_run = MagicMock(
            return_value=MagicMock(returncode=1, stderr="service already loaded")
        )
        monkeypatch.setattr("subprocess.run", mock_run)

        result = launchd.load_daemon()
        assert result is True


class TestUnloadDaemon:
    """Tests for unload_daemon function."""

    def test_handles_not_found_plist(self, tmp_path, monkeypatch):
        """Test unload_daemon handles missing plist."""
        from vmlx.daemon import launchd

        plist_path = tmp_path / "nonexistent.plist"
        monkeypatch.setattr(launchd, "get_plist_path", lambda: plist_path)

        result = launchd.unload_daemon()
        assert result is True

    def test_calls_launchctl_unload(self, tmp_path, monkeypatch):
        """Test unload_daemon calls launchctl unload."""
        from vmlx.daemon import launchd

        plist_path = tmp_path / "com.vmlx.daemon.plist"
        plist_path.write_text("test")
        monkeypatch.setattr(launchd, "get_plist_path", lambda: plist_path)

        mock_run = MagicMock(return_value=MagicMock(returncode=0, stderr=""))
        monkeypatch.setattr("subprocess.run", mock_run)

        result = launchd.unload_daemon()

        assert result is True
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[0] == "launchctl"
        assert args[1] == "unload"


class TestIsDaemonRunning:
    """Tests for is_daemon_running function."""

    def test_returns_true_when_running(self, monkeypatch):
        """Test returns True when daemon is running."""
        from vmlx.daemon import launchd

        mock_run = MagicMock(return_value=MagicMock(returncode=0))
        monkeypatch.setattr("subprocess.run", mock_run)

        assert launchd.is_daemon_running() is True

    def test_returns_false_when_not_running(self, monkeypatch):
        """Test returns False when daemon is not running."""
        from vmlx.daemon import launchd

        mock_run = MagicMock(return_value=MagicMock(returncode=1))
        monkeypatch.setattr("subprocess.run", mock_run)

        assert launchd.is_daemon_running() is False


class TestGetDaemonPid:
    """Tests for get_daemon_pid function."""

    def test_returns_none_when_not_running(self, monkeypatch):
        """Test returns None when daemon is not running."""
        from vmlx.daemon import launchd

        mock_run = MagicMock(return_value=MagicMock(returncode=1, stdout=""))
        monkeypatch.setattr("subprocess.run", mock_run)

        assert launchd.get_daemon_pid() is None

    def test_returns_pid_when_running(self, monkeypatch):
        """Test returns PID when daemon is running."""
        from vmlx.daemon import launchd

        # launchctl list output format: PID\tStatus\tLabel
        mock_run = MagicMock(
            return_value=MagicMock(returncode=0, stdout="12345\t0\tcom.vmlx.daemon")
        )
        monkeypatch.setattr("subprocess.run", mock_run)

        assert launchd.get_daemon_pid() == 12345

    def test_returns_none_when_pid_is_dash(self, monkeypatch):
        """Test returns None when PID shows as dash (not running)."""
        from vmlx.daemon import launchd

        # When service is loaded but not running, PID shows as "-"
        mock_run = MagicMock(
            return_value=MagicMock(returncode=0, stdout="-\t0\tcom.vmlx.daemon")
        )
        monkeypatch.setattr("subprocess.run", mock_run)

        assert launchd.get_daemon_pid() is None
