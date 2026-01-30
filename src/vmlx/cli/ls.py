"""List command for showing downloaded models."""

import click
from rich.console import Console
from rich.table import Table

from vmlx.models.registry import format_size, list_models

console = Console()


@click.command()
def ls():
    """List downloaded MLX models.

    Shows all MLX-VLM compatible models in the HuggingFace cache
    with their sizes.

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
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Size", style="green", justify="right")
    table.add_column("Modified", style="dim")

    for model in sorted(models, key=lambda m: m.name):
        modified = model.last_modified.strftime("%Y-%m-%d") if model.last_modified else "Unknown"
        table.add_row(model.name, format_size(model.size_bytes), modified)

    console.print(table)
    console.print(f"\n[dim]{len(models)} model(s)[/dim]")
