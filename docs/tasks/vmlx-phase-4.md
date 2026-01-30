# Task: launchd Integration

**Phase**: 4  
**Branch**: `feat/vmlx-phase-4`  
**Plan**: [docs/plans/vmlx.md](../plans/vmlx.md)  
**Spec**: [docs/specs/vmlx-spec.md](../specs/vmlx-spec.md)  
**Status**: pending  
**Parallel With**: Phase 3, Phase 5

---

## Objective

Implement launchd integration for persistent daemon that auto-starts on login, with CLI commands for daemon lifecycle management.

---

## Acceptance Criteria

- [ ] `vmlx daemon start` installs plist and starts daemon
- [ ] `vmlx daemon stop` stops daemon and unloads plist
- [ ] `vmlx daemon restart` stops then starts
- [ ] `vmlx daemon status` shows running/stopped, PID, uptime
- [ ] `vmlx daemon logs` tails daemon log file
- [ ] Daemon auto-starts on user login (RunAtLoad)
- [ ] Daemon auto-restarts on crash (KeepAlive)
- [ ] Plist installed to `~/Library/LaunchAgents/com.vmlx.daemon.plist`
- [ ] Logs written to `~/.vmlx/logs/daemon.log`
- [ ] Graceful handling when daemon already running/stopped
- [ ] All tests pass
- [ ] Lint clean

---

## Files to Create

| File | Action | Description |
|------|--------|-------------|
| `src/vmlx/daemon/launchd.py` | create | Plist generation, launchctl commands |
| `src/vmlx/cli/daemon_cmd.py` | create | `vmlx daemon` command group |
| `tests/unit/test_launchd.py` | create | Plist generation tests |
| `tests/integration/test_daemon_lifecycle.py` | create | Full lifecycle tests |

---

## Implementation Notes

### launchd Module (launchd.py)

```python
import os
import subprocess
import plistlib
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)

LABEL = "com.vmlx.daemon"
PLIST_NAME = f"{LABEL}.plist"

def get_plist_path() -> Path:
    """Get path to LaunchAgent plist."""
    return Path.home() / "Library" / "LaunchAgents" / PLIST_NAME

def get_log_dir() -> Path:
    """Get path to log directory."""
    return Path.home() / ".vmlx" / "logs"

def get_python_path() -> str:
    """Get path to current Python interpreter."""
    import sys
    return sys.executable

def generate_plist() -> dict:
    """Generate launchd plist configuration."""
    log_dir = get_log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    
    return {
        "Label": LABEL,
        "ProgramArguments": [
            get_python_path(),
            "-m",
            "vmlx.daemon",
        ],
        "RunAtLoad": True,
        "KeepAlive": {
            "SuccessfulExit": False,  # Restart on crash, not clean exit
        },
        "StandardOutPath": str(log_dir / "daemon.log"),
        "StandardErrorPath": str(log_dir / "daemon.error.log"),
        "EnvironmentVariables": {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(Path.home()),
        },
        "WorkingDirectory": str(Path.home()),
    }

def install_plist() -> None:
    """Write plist file to LaunchAgents directory."""
    plist_path = get_plist_path()
    plist_path.parent.mkdir(parents=True, exist_ok=True)
    
    plist_data = generate_plist()
    
    with open(plist_path, "wb") as f:
        plistlib.dump(plist_data, f)
    
    logger.info(f"Installed plist to {plist_path}")

def uninstall_plist() -> None:
    """Remove plist file."""
    plist_path = get_plist_path()
    if plist_path.exists():
        plist_path.unlink()
        logger.info(f"Removed plist from {plist_path}")

def load_daemon() -> bool:
    """Load daemon with launchctl."""
    plist_path = get_plist_path()
    if not plist_path.exists():
        raise FileNotFoundError(f"Plist not found at {plist_path}")
    
    result = subprocess.run(
        ["launchctl", "load", str(plist_path)],
        capture_output=True,
        text=True,
    )
    
    if result.returncode != 0:
        if "already loaded" in result.stderr.lower():
            logger.info("Daemon already loaded")
            return True
        logger.error(f"Failed to load daemon: {result.stderr}")
        return False
    
    logger.info("Daemon loaded")
    return True

def unload_daemon() -> bool:
    """Unload daemon with launchctl."""
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
    """Check if daemon is currently running."""
    result = subprocess.run(
        ["launchctl", "list", LABEL],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0

def get_daemon_pid() -> Optional[int]:
    """Get PID of running daemon, or None if not running."""
    result = subprocess.run(
        ["launchctl", "list", LABEL],
        capture_output=True,
        text=True,
    )
    
    if result.returncode != 0:
        return None
    
    # Parse output: PID Status Label
    lines = result.stdout.strip().split("\n")
    for line in lines:
        parts = line.split()
        if len(parts) >= 1 and parts[0] != "-":
            try:
                return int(parts[0])
            except ValueError:
                pass
    
    return None
```

### Daemon CLI Commands (daemon_cmd.py)

```python
import click
from rich.console import Console
from rich.table import Table
import httpx
from pathlib import Path

console = Console()

@click.group()
def daemon():
    """Manage the vmlx daemon."""
    pass

@daemon.command()
def start():
    """Start the vmlx daemon."""
    from vmlx.daemon.launchd import (
        install_plist, load_daemon, is_daemon_running, get_plist_path
    )
    
    if is_daemon_running():
        console.print("[yellow]Daemon is already running[/yellow]")
        return
    
    # Install plist if not present
    if not get_plist_path().exists():
        console.print("Installing daemon configuration...")
        install_plist()
    
    console.print("Starting daemon...")
    if load_daemon():
        console.print("[green]✓ Daemon started[/green]")
        console.print(f"  API: http://127.0.0.1:11434")
        console.print(f"  Logs: ~/.vmlx/logs/daemon.log")
    else:
        console.print("[red]✗ Failed to start daemon[/red]")
        raise SystemExit(1)

@daemon.command()
def stop():
    """Stop the vmlx daemon."""
    from vmlx.daemon.launchd import unload_daemon, is_daemon_running
    
    if not is_daemon_running():
        console.print("[yellow]Daemon is not running[/yellow]")
        return
    
    console.print("Stopping daemon...")
    if unload_daemon():
        console.print("[green]✓ Daemon stopped[/green]")
    else:
        console.print("[red]✗ Failed to stop daemon[/red]")
        raise SystemExit(1)

@daemon.command()
def restart():
    """Restart the vmlx daemon."""
    from vmlx.daemon.launchd import unload_daemon, load_daemon, install_plist, get_plist_path
    import time
    
    console.print("Restarting daemon...")
    
    # Stop if running
    unload_daemon()
    time.sleep(1)  # Give it time to fully stop
    
    # Ensure plist exists
    if not get_plist_path().exists():
        install_plist()
    
    # Start
    if load_daemon():
        console.print("[green]✓ Daemon restarted[/green]")
    else:
        console.print("[red]✗ Failed to restart daemon[/red]")
        raise SystemExit(1)

@daemon.command()
def status():
    """Show daemon status."""
    from vmlx.daemon.launchd import is_daemon_running, get_daemon_pid
    from vmlx.config import Config
    
    config = Config.load()
    running = is_daemon_running()
    pid = get_daemon_pid()
    
    table = Table(title="vmlx Daemon Status")
    table.add_column("Property", style="cyan")
    table.add_column("Value")
    
    table.add_row("Status", "[green]Running[/green]" if running else "[red]Stopped[/red]")
    table.add_row("PID", str(pid) if pid else "-")
    table.add_row("Port", str(config.daemon.port))
    
    if running:
        # Try to get extended status from API
        try:
            response = httpx.get(
                f"http://127.0.0.1:{config.daemon.port}/status",
                timeout=2.0,
            )
            if response.status_code == 200:
                data = response.json()
                table.add_row("Uptime", f"{data.get('uptime_seconds', 0):.0f}s")
                table.add_row("Loaded Model", data.get("loaded_model") or "-")
                table.add_row("Memory", f"{data.get('memory_usage_mb', 0):.1f} MB")
                if data.get("idle_seconds_remaining"):
                    table.add_row("Idle Timeout In", f"{data['idle_seconds_remaining']:.0f}s")
        except Exception:
            pass  # API not responding, just show basic info
    
    console.print(table)

@daemon.command()
@click.option("-f", "--follow", is_flag=True, help="Follow log output")
@click.option("-n", "--lines", default=50, help="Number of lines to show")
def logs(follow, lines):
    """View daemon logs."""
    import subprocess
    
    log_path = Path.home() / ".vmlx" / "logs" / "daemon.log"
    
    if not log_path.exists():
        console.print(f"[yellow]Log file not found: {log_path}[/yellow]")
        return
    
    if follow:
        subprocess.run(["tail", "-f", str(log_path)])
    else:
        subprocess.run(["tail", f"-n{lines}", str(log_path)])
```

### Register Commands (main.py)

Add to CLI main:

```python
from vmlx.cli.daemon_cmd import daemon

cli.add_command(daemon)
```

### Daemon Entry Point (__main__.py in daemon/)

Create `src/vmlx/daemon/__main__.py`:

```python
"""Entry point for running daemon directly: python -m vmlx.daemon"""
from vmlx.daemon.server import run_server
from vmlx.config import Config

if __name__ == "__main__":
    config = Config.load()
    run_server(
        host=config.daemon.host,
        port=config.daemon.port,
    )
```

---

## Testing Requirements

### Unit Tests (test_launchd.py)

```python
import pytest
from pathlib import Path
from vmlx.daemon.launchd import generate_plist, LABEL

def test_generate_plist_has_required_keys():
    plist = generate_plist()
    
    assert plist["Label"] == LABEL
    assert "ProgramArguments" in plist
    assert plist["RunAtLoad"] == True
    assert "KeepAlive" in plist
    assert "StandardOutPath" in plist
    assert "StandardErrorPath" in plist

def test_generate_plist_uses_current_python():
    import sys
    plist = generate_plist()
    
    assert sys.executable in plist["ProgramArguments"]

def test_plist_path_is_in_launch_agents():
    from vmlx.daemon.launchd import get_plist_path
    
    path = get_plist_path()
    assert "LaunchAgents" in str(path)
    assert path.name == f"{LABEL}.plist"
```

### Integration Tests (test_daemon_lifecycle.py)

```python
@pytest.mark.slow
def test_daemon_start_stop():
    """Test starting and stopping daemon."""
    # This test actually starts/stops the daemon
    # Should be run in isolation, not in parallel
    pass

@pytest.mark.slow  
def test_daemon_survives_signal():
    """Test daemon restarts after SIGKILL."""
    pass
```

---

## Agent Instructions

1. Create `launchd.py` with plist generation and launchctl wrappers
2. Create `daemon_cmd.py` with Click command group
3. Create daemon `__main__.py` entry point
4. Register daemon commands in main CLI
5. Test plist generation (unit tests - fast)
6. Test manually:
   ```bash
   vmlx daemon start
   vmlx daemon status
   launchctl list | grep vmlx  # Verify loaded
   curl localhost:11434/health
   vmlx daemon logs
   vmlx daemon stop
   ```
7. Test auto-restart:
   ```bash
   vmlx daemon start
   kill -9 $(pgrep -f "vmlx.daemon")
   sleep 5
   vmlx daemon status  # Should show running again
   ```
8. Run `ruff check` and `pytest`
9. Commit with `wt commit`
