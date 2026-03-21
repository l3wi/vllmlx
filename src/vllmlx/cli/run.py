"""Run command for vllmlx CLI - daemon-backed interactive chat."""

import click
import httpx
from rich.console import Console

console = Console()


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
    try:
        response = httpx.get(f"{api_url}/health", timeout=2.0)
        if response.status_code != 200:
            raise httpx.ConnectError("Unhealthy")
    except (httpx.ConnectError, httpx.TimeoutException):
        console.print("[red]Error: Daemon is not running[/red]")
        console.print("[dim]Start it with: vllmlx daemon start[/dim]")
        raise SystemExit(1)

    start_chat(model_path, api_url)
