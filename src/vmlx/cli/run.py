"""Run command for vmlx CLI - starts interactive chat session."""

import click
import httpx
from rich.console import Console

console = Console()


@click.command()
@click.argument("model", required=False)
@click.option("--daemon", is_flag=True, help="Force using daemon API instead of local model")
def run(model: str = None, daemon: bool = False):
    """Start an interactive chat session.

    MODEL is the model name or alias (e.g., qwen2-vl-7b).
    If not provided, uses the default model from config.

    By default, loads the model directly for the session.
    Use --daemon to connect to the running daemon instead.

    Examples:
        vmlx run qwen2-vl-7b
        vmlx run  # uses default model if configured
        vmlx run qwen2-vl-7b --daemon  # use daemon API
    """
    from vmlx.chat.repl import start_chat, start_local_chat
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

    if daemon:
        # Use daemon API
        api_url = f"http://{config.daemon.host}:{config.daemon.port}"
        try:
            response = httpx.get(f"{api_url}/health", timeout=2.0)
            if response.status_code != 200:
                raise httpx.ConnectError("Unhealthy")
        except (httpx.ConnectError, httpx.TimeoutException):
            console.print("[red]Error: Daemon is not running[/red]")
            console.print("[dim]Start it with: vmlx daemon start[/dim]")
            console.print("[dim]Or run without --daemon to load model directly[/dim]")
            raise SystemExit(1)

        start_chat(model_path, api_url)
    else:
        # Load model directly (default)
        start_local_chat(model_path)
