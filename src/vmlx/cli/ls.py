"""List command for showing downloaded models."""

import click
from rich.console import Console
from rich.table import Table

from vmlx.models.aliases import BUILTIN_ALIASES
from vmlx.models.registry import format_size, list_models
from vmlx.config import Config

console = Console()


def get_alias_for_path(hf_path: str) -> str | None:
    """Find alias for a HuggingFace path."""
    # Check custom aliases first
    config = Config.load()
    for alias, path in config.aliases.items():
        if path == hf_path:
            return alias
    
    # Check builtin aliases
    for alias, path in BUILTIN_ALIASES.items():
        if path == hf_path:
            return alias
    
    return None


@click.command()
def ls():
    """List downloaded MLX models.

    Shows all MLX-VLM compatible models in the HuggingFace cache
    with their sizes and aliases.

    Examples:

        vmlx ls
    """
    models = list_models()

    if not models:
        console.print("[yellow]No MLX models found in cache.[/yellow]")
        console.print("Use [cyan]vmlx pull <model>[/cyan] to download a model.")
        return

    # Create table
    table = Table(title="Downloaded MLX Models")
    table.add_column("Alias", style="green", no_wrap=True)
    table.add_column("Model", style="cyan", no_wrap=True)
    table.add_column("Size", style="yellow", justify="right")
    table.add_column("Modified", style="dim")

    for model in sorted(models, key=lambda m: m.name):
        alias = get_alias_for_path(model.hf_path) or "-"
        modified = model.last_modified.strftime("%Y-%m-%d") if model.last_modified else "Unknown"
        table.add_row(alias, model.name, format_size(model.size_bytes), modified)

    console.print(table)
    console.print(f"\n[dim]{len(models)} model(s)[/dim]")
