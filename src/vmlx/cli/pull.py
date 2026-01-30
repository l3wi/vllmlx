"""Pull command for downloading models."""

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from vmlx.config import Config
from vmlx.models.aliases import resolve_alias
from vmlx.models.registry import download_model

console = Console()


@click.command()
@click.argument("model")
def pull(model: str):
    """Download a model from HuggingFace.

    MODEL can be an alias (e.g., qwen2-vl-2b) or a full HuggingFace path
    (e.g., mlx-community/Qwen2-VL-2B-Instruct-4bit).

    Examples:

        vmlx pull qwen2-vl-2b

        vmlx pull mlx-community/Some-Model-4bit
    """
    # Load config for custom aliases
    config = Config.load()

    # Resolve alias to full HF path
    hf_path = resolve_alias(model, custom_aliases=config.aliases)

    if hf_path != model:
        console.print(f"Resolving [cyan]{model}[/cyan] → [green]{hf_path}[/green]")
    else:
        console.print(f"Pulling [green]{hf_path}[/green]")

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task(f"Downloading {hf_path}...", total=None)
            download_model(hf_path)

        console.print(f"[green]✓[/green] Successfully downloaded [cyan]{model}[/cyan]")

    except Exception as e:
        console.print(f"[red]✗[/red] Failed to download [cyan]{model}[/cyan]: {e}")
        raise SystemExit(1)
