"""Run command for vmlx CLI - starts interactive chat session."""

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

    Examples:
        vmlx run qwen2-vl-7b
        vmlx run  # uses default model if configured
    """
    from vmlx.chat.repl import start_chat
    from vmlx.config import Config
    from vmlx.models.aliases import resolve_alias

    config = Config.load()

    # Determine model to use
    if not model:
        if config.models.default:
            model = config.models.default
        else:
            console.print("[red]Error: No model specified and no default set[/red]")
            console.print("[dim]Usage: vmlx run <model>[/dim]")
            console.print("[dim]Or set default: vmlx config set models.default qwen2-vl-7b[/dim]")
            raise SystemExit(1)

    # Resolve alias
    model_path = resolve_alias(model, config.aliases)

    # Check daemon is running
    api_url = f"http://{config.daemon.host}:{config.daemon.port}"
    try:
        response = httpx.get(f"{api_url}/health", timeout=2.0)
        if response.status_code != 200:
            raise httpx.ConnectError("Unhealthy")
    except (httpx.ConnectError, httpx.TimeoutException):
        console.print("[red]Error: Daemon is not running[/red]")
        console.print("[dim]Start it with: vmlx daemon start[/dim]")
        raise SystemExit(1)

    # Start chat
    start_chat(model_path, api_url)
