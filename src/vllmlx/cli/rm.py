"""Remove command for deleting models."""

import click
from rich.console import Console

from vllmlx.config import Config
from vllmlx.models.aliases import resolve_alias
from vllmlx.models.registry import delete_model

console = Console()


@click.command()
@click.argument("model")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation prompt")
def rm(model: str, force: bool):
    """Remove a model from the HuggingFace cache.

    MODEL can be an alias (e.g., qwen2-vl-2b) or a full HuggingFace path.

    Examples:

        vllmlx rm qwen2-vl-2b

        vllmlx rm mlx-community/Some-Model-4bit --force
    """
    # Load config for custom aliases
    config = Config.load()

    # Resolve alias to full HF path
    hf_path = resolve_alias(model, custom_aliases=config.aliases)

    if hf_path != model:
        console.print(f"Resolving [cyan]{model}[/cyan] → [green]{hf_path}[/green]")

    # Confirm deletion unless --force
    if not force:
        if not click.confirm(f"Remove {hf_path}?"):
            console.print("[yellow]Cancelled.[/yellow]")
            return

    # Delete the model
    if delete_model(hf_path):
        console.print(f"[green]✓[/green] Removed [cyan]{model}[/cyan]")
    else:
        console.print(f"[red]✗[/red] Model [cyan]{model}[/cyan] not found in cache")
        raise SystemExit(1)
