"""CLI commands for managing the vllmlx daemon."""

import os
import signal
import subprocess
import time
from pathlib import Path

import click
import httpx
from rich.console import Console
from rich.table import Table

from vllmlx.config import Config
from vllmlx.daemon.launchd import (
    get_daemon_pid,
    get_plist_path,
    install_plist,
    is_daemon_running,
    load_daemon,
    unload_daemon,
)

console = Console()


def _find_listener_pid(port: int) -> int | None:
    """Return PID listening on daemon API port, if any."""
    result = subprocess.run(
        ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None

    for line in result.stdout.splitlines():
        candidate = line.strip()
        if candidate.isdigit():
            return int(candidate)
    return None


def _terminate_pid(pid: int) -> bool:
    """Attempt graceful termination of a process by PID."""
    try:
        os.kill(pid, signal.SIGTERM)
        return True
    except OSError:
        return False


@click.group()
def daemon():
    """Manage the vllmlx daemon.

    The daemon runs as a launchd service that auto-starts on login
    and provides the OpenAI-compatible API for vision-language models.

    \b
    Examples:
        vllmlx daemon start     # Install and start the daemon
        vllmlx daemon status    # Check if daemon is running
        vllmlx daemon logs      # View daemon logs
        vllmlx daemon stop      # Stop the daemon
    """
    pass


@daemon.command()
def start():
    """Start the vllmlx daemon.

    Installs the launchd plist if not present and loads the daemon.
    The daemon will auto-start on future logins.

    \b
    Examples:
        vllmlx daemon start
    """
    if is_daemon_running():
        console.print("[yellow]Daemon is already running[/yellow]")
        return

    # Install plist if not present
    if not get_plist_path().exists():
        console.print("Installing daemon configuration...")
        install_plist()

    console.print("Starting daemon...")
    if load_daemon():
        config = Config.load()
        console.print("[green]✓ Daemon started[/green]")
        console.print(f"  API: http://{config.daemon.host}:{config.daemon.port}")
        console.print("  Logs: ~/.vllmlx/logs/daemon.log")
    else:
        console.print("[red]✗ Failed to start daemon[/red]")
        raise SystemExit(1)


@daemon.command()
def stop():
    """Stop the vllmlx daemon.

    Unloads the daemon from launchd. The daemon will still auto-start
    on next login unless you remove the plist.

    \b
    Examples:
        vllmlx daemon stop
    """
    config = Config.load()

    if not is_daemon_running():
        # Clear stale launchd state if present.
        unload_daemon()

        listener_pid = _find_listener_pid(config.daemon.port)
        if listener_pid:
            if _terminate_pid(listener_pid):
                console.print(f"[yellow]Stopped stray daemon process (pid={listener_pid})[/yellow]")
                return
            console.print("[red]✗ Failed to stop stray daemon process[/red]")
            raise SystemExit(1)

        console.print("[yellow]Daemon is not running[/yellow]")
        return

    console.print("Stopping daemon...")
    if unload_daemon():
        # If launchctl unload succeeds but a process still listens, clean it up.
        listener_pid = _find_listener_pid(config.daemon.port)
        if listener_pid and _terminate_pid(listener_pid):
            console.print(f"[green]✓ Daemon stopped[/green] (killed pid={listener_pid})")
            return
        console.print("[green]✓ Daemon stopped[/green]")
    else:
        console.print("[red]✗ Failed to stop daemon[/red]")
        raise SystemExit(1)


@daemon.command()
def restart():
    """Restart the vllmlx daemon.

    Stops the daemon if running, then starts it again.
    Useful after configuration changes.

    \b
    Examples:
        vllmlx daemon restart
    """
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
    """Show daemon status.

    Displays whether the daemon is running, its PID, and if available,
    information about loaded models and resource usage.

    \b
    Examples:
        vllmlx daemon status
    """
    config = Config.load()
    launchd_running = is_daemon_running()
    launchd_pid = get_daemon_pid()
    listener_pid = _find_listener_pid(config.daemon.port)

    running = launchd_running or listener_pid is not None
    pid = launchd_pid or listener_pid

    table = Table(title="vllmlx Daemon Status")
    table.add_column("Property", style="cyan")
    table.add_column("Value")

    table.add_row("Status", "[green]Running[/green]" if running else "[red]Stopped[/red]")
    table.add_row("PID", str(pid) if pid else "-")
    table.add_row("Port", str(config.daemon.port))
    if running and not launchd_running and listener_pid:
        table.add_row("Manager", "unmanaged (port listener)")

    if running:
        # Try to get extended status from API
        try:
            response = httpx.get(
                f"http://{config.daemon.host}:{config.daemon.port}/v1/status",
                timeout=2.0,
            )
            if response.status_code == 200:
                data = response.json()
                table.add_row("Backend Status", str(data.get("status", "-")))
                table.add_row("Loaded Model", str(data.get("model") or "-"))
                if data.get("uptime_s") is not None:
                    table.add_row("Uptime", f"{float(data['uptime_s']):.0f}s")
                metal = data.get("metal") or {}
                if metal.get("active_memory_gb") is not None:
                    table.add_row("Metal Active", f"{float(metal['active_memory_gb']):.2f} GB")
        except Exception:
            pass  # API not responding, just show basic info

    console.print(table)


@daemon.command()
@click.option("-f", "--follow", is_flag=True, help="Follow log output (tail -f)")
@click.option("-n", "--lines", default=50, type=int, help="Number of lines to show (default: 50)")
def logs(follow: bool, lines: int):
    """View daemon logs.

    Shows the daemon log file. Use --follow to continuously stream new log entries.

    \b
    Examples:
        vllmlx daemon logs            # Show last 50 lines
        vllmlx daemon logs -n 100     # Show last 100 lines
        vllmlx daemon logs -f         # Follow log output
    """
    log_path = Path.home() / ".vllmlx" / "logs" / "daemon.log"

    if not log_path.exists():
        console.print(f"[yellow]Log file not found: {log_path}[/yellow]")
        return

    if follow:
        subprocess.run(["tail", "-f", str(log_path)])
    else:
        subprocess.run(["tail", f"-n{lines}", str(log_path)])
