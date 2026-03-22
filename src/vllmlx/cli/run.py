import time

import click
import httpx
from rich.console import Console

from vllmlx.daemon.launchd import (
    get_plist_path,
    install_plist,
    is_daemon_running,
    load_daemon,
)

console = Console()


def _daemon_is_healthy(api_url: str, *, timeout: float = 2.0) -> bool:
    """Return True when the daemon health endpoint responds successfully."""
    try:
        response = httpx.get(f"{api_url}/health", timeout=timeout)
    except httpx.HTTPError:
        return False
    return response.status_code == 200


def _start_daemon_if_needed() -> bool:
    """Install and load the daemon service when it is not already running."""
    if is_daemon_running():
        return True

    if not get_plist_path().exists():
        console.print("Installing daemon configuration...")
        install_plist()

    console.print("Starting daemon...")
    return load_daemon()


def _ensure_daemon_ready(config) -> bool:
    """Ensure the daemon API is healthy, auto-starting it if needed."""
    api_url = f"http://{config.daemon.host}:{config.daemon.port}"
    if _daemon_is_healthy(api_url):
        return True

    console.print("[yellow]Daemon is not running. Starting it...[/yellow]")
    if not _start_daemon_if_needed():
        return False

    deadline = time.monotonic() + 15.0
    while time.monotonic() < deadline:
        if _daemon_is_healthy(api_url, timeout=1.0):
            return True
        time.sleep(0.5)

    return _daemon_is_healthy(api_url, timeout=1.0)


@click.command()
@click.argument("model", required=False)
def run(model: str = None):
    """Start an interactive chat session.

    MODEL is the model name or alias (e.g., qwen2-vl-7b).
    If not provided, uses the default model from config.

    This command always uses the running daemon.

    Examples:
        vllmlx run qwen2-vl-7b
        vllmlx run  # uses default model if configured
    """
    from vllmlx.chat.repl import start_chat
    from vllmlx.config import Config
    from vllmlx.models.aliases import resolve_alias

    config = Config.load()

    # Determine model to use
    if not model:
        if config.models.default:
            model = config.models.default
        else:
            console.print("[red]Error: No model specified and no default set[/red]")
            console.print("[dim]Usage: vllmlx run <model>[/dim]")
            console.print("[dim]Or set default: vllmlx config set models.default qwen2-vl-7b[/dim]")
            raise SystemExit(1)

    # Resolve alias
    model_path = resolve_alias(model, config.aliases)

    api_url = f"http://{config.daemon.host}:{config.daemon.port}"
    if not _ensure_daemon_ready(config):
        console.print("[red]Error: Failed to start daemon[/red]")
        console.print("[dim]Check logs with: vllmlx daemon logs[/dim]")
        raise SystemExit(1)

    start_chat(model_path, api_url)
