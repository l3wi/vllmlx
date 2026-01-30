"""CLI commands for managing the vmlx daemon."""

import subprocess
import time
from pathlib import Path

import click
import httpx
from rich.console import Console
from rich.table import Table

from vmlx.config import Config
from vmlx.daemon.launchd import (
    get_daemon_pid,
    get_plist_path,
    install_plist,
    is_daemon_running,
    load_daemon,
    unload_daemon,
)

console = Console()


@click.group()
def daemon():
    """Manage the vmlx daemon.

    The daemon runs as a launchd service that auto-starts on login
    and provides the OpenAI-compatible API for vision-language models.

    \b
    Examples:
        vmlx daemon start     # Install and start the daemon
        vmlx daemon status    # Check if daemon is running
        vmlx daemon logs      # View daemon logs
        vmlx daemon stop      # Stop the daemon
    """
    pass


@daemon.command()
def start():
    """Start the vmlx daemon.

    Installs the launchd plist if not present and loads the daemon.
    The daemon will auto-start on future logins.

    \b
    Examples:
        vmlx daemon start
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
        console.print("  Logs: ~/.vmlx/logs/daemon.log")
    else:
        console.print("[red]✗ Failed to start daemon[/red]")
        raise SystemExit(1)


@daemon.command()
def stop():
    """Stop the vmlx daemon.

    Unloads the daemon from launchd. The daemon will still auto-start
    on next login unless you remove the plist.

    \b
    Examples:
        vmlx daemon stop
    """
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
    """Restart the vmlx daemon.

    Stops the daemon if running, then starts it again.
    Useful after configuration changes.

    \b
    Examples:
        vmlx daemon restart
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
        vmlx daemon status
    """
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
                f"http://{config.daemon.host}:{config.daemon.port}/status",
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
@click.option("-f", "--follow", is_flag=True, help="Follow log output (tail -f)")
@click.option("-n", "--lines", default=50, type=int, help="Number of lines to show (default: 50)")
def logs(follow: bool, lines: int):
    """View daemon logs.

    Shows the daemon log file. Use --follow to continuously stream new log entries.

    \b
    Examples:
        vmlx daemon logs            # Show last 50 lines
        vmlx daemon logs -n 100     # Show last 100 lines
        vmlx daemon logs -f         # Follow log output
    """
    log_path = Path.home() / ".vmlx" / "logs" / "daemon.log"

    if not log_path.exists():
        console.print(f"[yellow]Log file not found: {log_path}[/yellow]")
        return

    if follow:
        subprocess.run(["tail", "-f", str(log_path)])
    else:
        subprocess.run(["tail", f"-n{lines}", str(log_path)])
