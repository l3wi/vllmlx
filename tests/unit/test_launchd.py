"""Tests for launchd integration module."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest


class TestConstants:
    """Tests for launchd module constants."""

    def test_label_format(self):
        """Test LABEL follows reverse-DNS convention."""
        from vllmlx.daemon.launchd import LABEL

        assert LABEL == "com.vllmlx.daemon"

    def test_plist_name_matches_label(self):
        """Test PLIST_NAME is derived from LABEL."""
        from vllmlx.daemon.launchd import LABEL, PLIST_NAME

        assert PLIST_NAME == f"{LABEL}.plist"


class TestGetPlistPath:
    """Tests for get_plist_path function."""

    def test_plist_path_in_launch_agents(self):
        """Test plist path is in LaunchAgents directory."""
        from vllmlx.daemon.launchd import get_plist_path

        path = get_plist_path()
        assert "LaunchAgents" in str(path)

    def test_plist_path_is_absolute(self):
        """Test plist path is absolute."""
        from vllmlx.daemon.launchd import get_plist_path

        path = get_plist_path()
        assert path.is_absolute()

    def test_plist_path_ends_with_correct_name(self):
        """Test plist path has correct filename."""
        from vllmlx.daemon.launchd import LABEL, get_plist_path

        path = get_plist_path()
        assert path.name == f"{LABEL}.plist"

    def test_plist_path_uses_override_directory_and_label(self, tmp_path, monkeypatch):
        """Test plist path honors launchd directory and label overrides."""
        from vllmlx.daemon.launchd import get_plist_path

        monkeypatch.setenv("VLLMLX_LAUNCHD_DIR", str(tmp_path / "agents"))
        monkeypatch.setenv("VLLMLX_LAUNCHD_LABEL", "dev.vllmlx.e2e")

        path = get_plist_path()

        assert path == tmp_path / "agents" / "dev.vllmlx.e2e.plist"


class TestGetLogDir:
    """Tests for get_log_dir function."""

    def test_log_dir_in_vmlx_directory(self):
        """Test log directory is under .vllmlx."""
        from vllmlx.daemon.launchd import get_log_dir

        log_dir = get_log_dir()
        assert ".vllmlx" in str(log_dir)
        assert "logs" in str(log_dir)

    def test_log_dir_is_absolute(self):
        """Test log directory path is absolute."""
        from vllmlx.daemon.launchd import get_log_dir

        log_dir = get_log_dir()
        assert log_dir.is_absolute()


class TestGetPythonPath:
    """Tests for get_python_path function."""

    def test_returns_current_python(self):
        """Test returns current Python interpreter path."""
        from vllmlx.daemon.launchd import get_python_path

        python_path = get_python_path()
        assert python_path == sys.executable


class TestGeneratePlist:
    """Tests for generate_plist function."""

    def test_has_label(self):
        """Test plist has Label key."""
        from vllmlx.daemon.launchd import LABEL, generate_plist

        plist = generate_plist()
        assert plist["Label"] == LABEL

    def test_has_program_arguments(self):
        """Test plist has ProgramArguments."""
        from vllmlx.daemon.launchd import generate_plist

        plist = generate_plist()
        assert "ProgramArguments" in plist
        assert len(plist["ProgramArguments"]) >= 3

    def test_program_arguments_uses_current_python(self):
        """Test plist uses current Python interpreter."""
        from vllmlx.daemon.launchd import generate_plist

        plist = generate_plist()
        assert sys.executable in plist["ProgramArguments"]

    def test_program_arguments_runs_daemon_module(self):
        """Test plist runs vllmlx.daemon as module."""
        from vllmlx.daemon.launchd import generate_plist

        plist = generate_plist()
        args = plist["ProgramArguments"]
        assert "-m" in args
        assert "vllmlx.daemon" in args

    def test_run_at_load_is_true(self):
        """Test RunAtLoad is enabled."""
        from vllmlx.daemon.launchd import generate_plist

        plist = generate_plist()
        assert plist["RunAtLoad"] is True

    def test_has_keep_alive(self):
        """Test plist has KeepAlive configuration."""
        from vllmlx.daemon.launchd import generate_plist

        plist = generate_plist()
        assert "KeepAlive" in plist

    def test_keep_alive_restarts_on_crash(self):
        """Test KeepAlive restarts on non-zero exit."""
        from vllmlx.daemon.launchd import generate_plist

        plist = generate_plist()
        # SuccessfulExit: false means restart on crash, not clean exit
        assert plist["KeepAlive"]["SuccessfulExit"] is False

    def test_has_standard_out_path(self):
        """Test plist has stdout log path."""
        from vllmlx.daemon.launchd import generate_plist

        plist = generate_plist()
        assert "StandardOutPath" in plist
        assert "daemon.log" in plist["StandardOutPath"]

    def test_has_standard_error_path(self):
        """Test plist has stderr log path."""
        from vllmlx.daemon.launchd import generate_plist

        plist = generate_plist()
        assert "StandardErrorPath" in plist
        assert "daemon.error.log" in plist["StandardErrorPath"]

    def test_has_environment_variables(self):
        """Test plist has environment variables."""
        from vllmlx.daemon.launchd import generate_plist

        plist = generate_plist()
        assert "EnvironmentVariables" in plist
        assert "PATH" in plist["EnvironmentVariables"]
        assert "HOME" in plist["EnvironmentVariables"]

    def test_has_working_directory(self):
        """Test plist has working directory set to home."""
        from vllmlx.daemon.launchd import generate_plist

        plist = generate_plist()
        assert "WorkingDirectory" in plist
        assert plist["WorkingDirectory"] == str(Path.home())

    def test_generate_plist_uses_isolated_runtime_overrides(self, tmp_path, monkeypatch):
        """Test plist forwards runtime isolation env vars when present."""
        from vllmlx.daemon.launchd import generate_plist

        monkeypatch.setenv("VLLMLX_HOME", str(tmp_path / "runtime-home"))
        monkeypatch.setenv("VLLMLX_STATE_DIR", str(tmp_path / "state"))
        monkeypatch.setenv("VLLMLX_LAUNCHD_LABEL", "dev.vllmlx.e2e")
        monkeypatch.setenv("VLLMLX_LAUNCHD_DIR", str(tmp_path / "agents"))

        plist = generate_plist()
        env = plist["EnvironmentVariables"]

        assert plist["Label"] == "dev.vllmlx.e2e"
        assert plist["WorkingDirectory"] == str(tmp_path / "runtime-home")
        assert env["HOME"] == str(tmp_path / "runtime-home")
        assert env["VLLMLX_STATE_DIR"] == str(tmp_path / "state")
        assert env["VLLMLX_LAUNCHD_LABEL"] == "dev.vllmlx.e2e"
        assert env["VLLMLX_LAUNCHD_DIR"] == str(tmp_path / "agents")


class TestInstallPlist:
    """Tests for install_plist function."""

    def test_creates_plist_file(self, tmp_path, monkeypatch):
        """Test install_plist creates the plist file."""
        from vllmlx.daemon import launchd

        # Mock the plist path to use temp directory
        plist_path = tmp_path / "LaunchAgents" / "com.vllmlx.daemon.plist"
        monkeypatch.setattr(launchd, "get_plist_path", lambda: plist_path)

        # Mock log dir to use temp directory
        log_dir = tmp_path / ".vllmlx" / "logs"
        monkeypatch.setattr(launchd, "get_log_dir", lambda: log_dir)

        launchd.install_plist()

        assert plist_path.exists()

    def test_creates_parent_directories(self, tmp_path, monkeypatch):
        """Test install_plist creates parent directories."""
        from vllmlx.daemon import launchd

        plist_path = tmp_path / "deep" / "path" / "com.vllmlx.daemon.plist"
        monkeypatch.setattr(launchd, "get_plist_path", lambda: plist_path)
        monkeypatch.setattr(launchd, "get_log_dir", lambda: tmp_path / "logs")

        launchd.install_plist()

        assert plist_path.parent.exists()


class TestUninstallPlist:
    """Tests for uninstall_plist function."""

    def test_removes_existing_plist(self, tmp_path, monkeypatch):
        """Test uninstall_plist removes existing plist file."""
        from vllmlx.daemon import launchd

        # Create a mock plist file
        plist_path = tmp_path / "com.vllmlx.daemon.plist"
        plist_path.write_text("test")
        monkeypatch.setattr(launchd, "get_plist_path", lambda: plist_path)

        launchd.uninstall_plist()

        assert not plist_path.exists()

    def test_handles_nonexistent_plist(self, tmp_path, monkeypatch):
        """Test uninstall_plist handles missing file gracefully."""
        from vllmlx.daemon import launchd

        plist_path = tmp_path / "nonexistent.plist"
        monkeypatch.setattr(launchd, "get_plist_path", lambda: plist_path)

        # Should not raise
        launchd.uninstall_plist()


class TestLoadDaemon:
    """Tests for load_daemon function."""

    def test_raises_if_plist_not_found(self, tmp_path, monkeypatch):
        """Test load_daemon raises if plist doesn't exist."""
        from vllmlx.daemon import launchd

        plist_path = tmp_path / "nonexistent.plist"
        monkeypatch.setattr(launchd, "get_plist_path", lambda: plist_path)

        with pytest.raises(FileNotFoundError):
            launchd.load_daemon()

    def test_calls_launchctl_load(self, tmp_path, monkeypatch):
        """Test load_daemon calls launchctl load."""
        from vllmlx.daemon import launchd

        # Create mock plist
        plist_path = tmp_path / "com.vllmlx.daemon.plist"
        plist_path.write_text("test")
        monkeypatch.setattr(launchd, "get_plist_path", lambda: plist_path)

        # Mock subprocess.run: load + kickstart
        mock_run = MagicMock(
            side_effect=[
                MagicMock(returncode=0, stderr=""),
                MagicMock(returncode=0, stderr=""),
            ]
        )
        monkeypatch.setattr("subprocess.run", mock_run)

        result = launchd.load_daemon()

        assert result is True
        assert mock_run.call_count == 2
        load_args = mock_run.call_args_list[0][0][0]
        kick_args = mock_run.call_args_list[1][0][0]
        assert load_args[:2] == ["launchctl", "load"]
        assert kick_args[:3] == ["launchctl", "kickstart", "-k"]

    def test_handles_already_loaded(self, tmp_path, monkeypatch):
        """Test load_daemon handles already loaded state."""
        from vllmlx.daemon import launchd

        plist_path = tmp_path / "com.vllmlx.daemon.plist"
        plist_path.write_text("test")
        monkeypatch.setattr(launchd, "get_plist_path", lambda: plist_path)

        # Mock subprocess.run returning "already loaded" then successful kickstart
        mock_run = MagicMock(
            side_effect=[
                MagicMock(returncode=1, stderr="service already loaded"),
                MagicMock(returncode=0, stderr=""),
            ]
        )
        monkeypatch.setattr("subprocess.run", mock_run)

        result = launchd.load_daemon()
        assert result is True


class TestUnloadDaemon:
    """Tests for unload_daemon function."""

    def test_handles_not_found_plist(self, tmp_path, monkeypatch):
        """Test unload_daemon handles missing plist."""
        from vllmlx.daemon import launchd

        plist_path = tmp_path / "nonexistent.plist"
        monkeypatch.setattr(launchd, "get_plist_path", lambda: plist_path)

        result = launchd.unload_daemon()
        assert result is True

    def test_calls_launchctl_unload(self, tmp_path, monkeypatch):
        """Test unload_daemon calls launchctl unload."""
        from vllmlx.daemon import launchd

        plist_path = tmp_path / "com.vllmlx.daemon.plist"
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
        from vllmlx.daemon import launchd

        monkeypatch.setattr(launchd, "get_daemon_pid", lambda: 12345)
        monkeypatch.setattr("os.kill", lambda pid, sig: None)

        assert launchd.is_daemon_running() is True

    def test_returns_false_when_not_running(self, monkeypatch):
        """Test returns False when daemon is not running."""
        from vllmlx.daemon import launchd

        monkeypatch.setattr(launchd, "get_daemon_pid", lambda: None)
        monkeypatch.setattr("os.kill", lambda pid, sig: None)

        assert launchd.is_daemon_running() is False

    def test_returns_false_when_pid_not_alive(self, monkeypatch):
        """Test returns False when launchctl reports PID but process is gone."""
        from vllmlx.daemon import launchd

        monkeypatch.setattr(launchd, "get_daemon_pid", lambda: 12345)

        def _kill(pid, sig):
            raise OSError("no such process")

        monkeypatch.setattr("os.kill", _kill)

        assert launchd.is_daemon_running() is False


class TestGetDaemonPid:
    """Tests for get_daemon_pid function."""

    def test_returns_none_when_not_running(self, monkeypatch):
        """Test returns None when daemon is not running."""
        from vllmlx.daemon import launchd

        mock_run = MagicMock(return_value=MagicMock(returncode=1, stdout=""))
        monkeypatch.setattr("subprocess.run", mock_run)

        assert launchd.get_daemon_pid() is None

    def test_returns_pid_when_running(self, monkeypatch):
        """Test returns PID when daemon is running."""
        from vllmlx.daemon import launchd

        # launchctl list output format: PID\tStatus\tLabel
        mock_run = MagicMock(
            return_value=MagicMock(returncode=0, stdout="12345\t0\tcom.vllmlx.daemon")
        )
        monkeypatch.setattr("subprocess.run", mock_run)

        assert launchd.get_daemon_pid() == 12345

    def test_returns_none_when_pid_is_dash(self, monkeypatch):
        """Test returns None when PID shows as dash (not running)."""
        from vllmlx.daemon import launchd

        # When service is loaded but not running, PID shows as "-"
        mock_run = MagicMock(return_value=MagicMock(returncode=0, stdout="-\t0\tcom.vllmlx.daemon"))
        monkeypatch.setattr("subprocess.run", mock_run)

        assert launchd.get_daemon_pid() is None

    def test_uses_overridden_label(self, monkeypatch):
        """Test launchctl list targets the overridden label when configured."""
        from vllmlx.daemon import launchd

        monkeypatch.setenv("VLLMLX_LAUNCHD_LABEL", "dev.vllmlx.e2e")
        mock_run = MagicMock(return_value=MagicMock(returncode=1, stdout=""))
        monkeypatch.setattr("subprocess.run", mock_run)

        launchd.get_daemon_pid()

        assert mock_run.call_args[0][0] == ["launchctl", "list", "dev.vllmlx.e2e"]
