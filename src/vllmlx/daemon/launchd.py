"""launchd integration for vllmlx daemon.

Provides plist generation and launchctl commands for managing the daemon
as a macOS LaunchAgent that auto-starts on login and restarts on crash.
"""

import logging
import os
import plistlib
import subprocess
import sys
from pathlib import Path
from typing import Optional

from vllmlx.config import get_runtime_home, get_state_dir

logger = logging.getLogger(__name__)

LABEL = "com.vllmlx.daemon"
PLIST_NAME = f"{LABEL}.plist"


def get_label() -> str:
    """Return the effective launchd label."""
    return os.environ.get("VLLMLX_LAUNCHD_LABEL", "").strip() or LABEL


def get_plist_name() -> str:
    """Return the effective plist filename."""
    return f"{get_label()}.plist"


def get_launchd_dir() -> Path:
    """Return the effective LaunchAgents directory."""
    override = os.environ.get("VLLMLX_LAUNCHD_DIR", "").strip()
    if override:
        return Path(override).expanduser()
    return get_runtime_home() / "Library" / "LaunchAgents"


def get_plist_path() -> Path:
    """Get path to LaunchAgent plist.

    Returns:
        Path to ~/Library/LaunchAgents/com.vllmlx.daemon.plist
    """
    return get_launchd_dir() / get_plist_name()


def get_log_dir() -> Path:
    """Get path to log directory.

    Returns:
        Path to ~/.vllmlx/logs/
    """
    return get_state_dir() / "logs"


def get_python_path() -> str:
    """Get path to current Python interpreter.

    Returns:
        Path to the Python executable
    """
    return sys.executable


def generate_plist() -> dict:
    """Generate launchd plist configuration.

    Creates the plist dictionary with:
    - RunAtLoad: Auto-start on login
    - KeepAlive: Auto-restart on crash (but not clean exit)
    - Log paths for stdout/stderr
    - Environment variables for proper operation

    Returns:
        Dictionary suitable for plistlib.dump()
    """
    log_dir = get_log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    runtime_home = get_runtime_home()
    env_vars = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(runtime_home),
    }
    for name in (
        "VLLMLX_HOME",
        "VLLMLX_STATE_DIR",
        "VLLMLX_LAUNCHD_LABEL",
        "VLLMLX_LAUNCHD_DIR",
    ):
        value = os.environ.get(name, "").strip()
        if value:
            env_vars[name] = value

    return {
        "Label": get_label(),
        "ProgramArguments": [
            get_python_path(),
            "-m",
            "vllmlx.daemon",
        ],
        "RunAtLoad": True,
        "KeepAlive": {
            "SuccessfulExit": False,  # Restart on crash, not clean exit
        },
        "StandardOutPath": str(log_dir / "daemon.log"),
        "StandardErrorPath": str(log_dir / "daemon.error.log"),
        "EnvironmentVariables": env_vars,
        "WorkingDirectory": str(runtime_home),
    }


def install_plist() -> None:
    """Write plist file to LaunchAgents directory.

    Creates parent directories if needed and writes the plist
    configuration file.
    """
    plist_path = get_plist_path()
    plist_path.parent.mkdir(parents=True, exist_ok=True)

    plist_data = generate_plist()

    with open(plist_path, "wb") as f:
        plistlib.dump(plist_data, f)

    logger.info(f"Installed plist to {plist_path}")


def uninstall_plist() -> None:
    """Remove plist file.

    Silently succeeds if file doesn't exist.
    """
    plist_path = get_plist_path()
    if plist_path.exists():
        plist_path.unlink()
        logger.info(f"Removed plist from {plist_path}")


def load_daemon() -> bool:
    """Load daemon with launchctl.

    Returns:
        True if successful or already loaded, False on error

    Raises:
        FileNotFoundError: If plist file doesn't exist
    """
    plist_path = get_plist_path()
    if not plist_path.exists():
        raise FileNotFoundError(f"Plist not found at {plist_path}")

    result = subprocess.run(
        ["launchctl", "load", str(plist_path)],
        capture_output=True,
        text=True,
    )

    def _kickstart() -> bool:
        target = f"gui/{os.getuid()}/{get_label()}"
        kick = subprocess.run(
            ["launchctl", "kickstart", "-k", target],
            capture_output=True,
            text=True,
        )
        if kick.returncode != 0:
            logger.error(f"Failed to kickstart daemon: {kick.stderr}")
            return False
        return True

    if result.returncode != 0:
        if "already loaded" in result.stderr.lower():
            logger.info("Daemon already loaded; kickstarting service")
            return _kickstart()
        logger.error(f"Failed to load daemon: {result.stderr}")
        return False

    logger.info("Daemon loaded; kickstarting service")
    return _kickstart()


def unload_daemon() -> bool:
    """Unload daemon with launchctl.

    Returns:
        True if successful or not loaded, False on error
    """
    plist_path = get_plist_path()
    if not plist_path.exists():
        logger.info("Plist not found, nothing to unload")
        return True

    result = subprocess.run(
        ["launchctl", "unload", str(plist_path)],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        if "could not find" in result.stderr.lower():
            logger.info("Daemon not loaded")
            return True
        logger.error(f"Failed to unload daemon: {result.stderr}")
        return False

    logger.info("Daemon unloaded")
    return True


def is_daemon_running() -> bool:
    """Check if daemon is currently running.

    Returns:
        True if daemon is loaded with launchctl
    """
    pid = get_daemon_pid()
    if pid is None:
        return False

    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def get_daemon_pid() -> Optional[int]:
    """Get PID of running daemon, or None if not running.

    Returns:
        Process ID if running, None otherwise
    """
    result = subprocess.run(
        ["launchctl", "list", get_label()],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return None

    # Parse output: PID\tStatus\tLabel
    lines = result.stdout.strip().split("\n")
    for line in lines:
        parts = line.split()
        if len(parts) >= 1 and parts[0] != "-":
            try:
                return int(parts[0])
            except ValueError:
                pass

    return None
