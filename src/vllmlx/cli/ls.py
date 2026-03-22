"""List command for showing downloaded models."""

from functools import lru_cache

import click
from rich.console import Console
from rich.table import Table

from vllmlx.config import Config
from vllmlx.models.aliases import BUILTIN_ALIASES
from vllmlx.models.catalog import load_catalog_cached
from vllmlx.models.registry import format_size, list_models

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


@lru_cache(maxsize=1)
def _model_type_lookup() -> dict[str, str]:
    return {entry.repo_id: entry.model_type for entry in load_catalog_cached()}


@lru_cache(maxsize=1)
def _catalog_size_lookup() -> dict[str, int]:
    return {
        entry.repo_id: entry.size_bytes
        for entry in load_catalog_cached()
        if isinstance(entry.size_bytes, int)
    }


def get_model_type_for_path(hf_path: str) -> str | None:
    """Return known model type for a HuggingFace repo path."""
    return _model_type_lookup().get(hf_path)


def get_catalog_size_for_path(hf_path: str) -> int | None:
    """Return packaged catalog size for a HuggingFace repo path."""
    return _catalog_size_lookup().get(hf_path)


def _format_size_display(local_size: int, catalog_size: int | None) -> str:
    if not isinstance(catalog_size, int) or catalog_size <= 0:
        return format_size(local_size)

    if local_size < int(catalog_size * 0.98):
        pct = (local_size / catalog_size) * 100 if catalog_size > 0 else 0
        return f"{format_size(local_size)} / {format_size(catalog_size)} ({pct:.0f}%)"

    return format_size(catalog_size)


@click.command()
@click.option(
    "--type",
    "model_type",
    type=click.Choice(["text", "vision", "embedding", "audio"], case_sensitive=False),
    help="Filter downloaded models by type.",
)
def ls(model_type: str | None):
    """List downloaded MLX models.

    Shows all MLX-VLM compatible models in the HuggingFace cache
    with their sizes and aliases.

    Examples:

        vllmlx ls
    """
    models = list_models()

    if not models:
        console.print("[yellow]No MLX models found in cache.[/yellow]")
        console.print("Use [cyan]vllmlx pull <model>[/cyan] to download a model.")
        return

    filtered_models = models
    if model_type:
        type_filter = model_type.lower()
        filtered_models = [
            model
            for model in models
            if (get_model_type_for_path(model.hf_path) or "").lower() == type_filter
        ]

        if not filtered_models:
            console.print(f"[yellow]No downloaded models found for type '{type_filter}'.[/yellow]")
            return

    incomplete_models: list[str] = []

    # Create table
    table = Table(title="Downloaded MLX Models")
    table.add_column("Alias", style="green", no_wrap=True)
    table.add_column("Type", style="magenta", no_wrap=True)
    table.add_column("Model", style="cyan", no_wrap=True)
    table.add_column("Size", style="yellow", justify="right")
    table.add_column("Modified", style="dim")

    for model in sorted(filtered_models, key=lambda m: m.name):
        alias = get_alias_for_path(model.hf_path) or "-"
        type_name = get_model_type_for_path(model.hf_path) or "-"
        catalog_size = get_catalog_size_for_path(model.hf_path)
        size_text = _format_size_display(model.size_bytes, catalog_size)
        if isinstance(catalog_size, int) and model.size_bytes < int(catalog_size * 0.98):
            incomplete_models.append(alias if alias != "-" else model.hf_path)
        modified = model.last_modified.strftime("%Y-%m-%d") if model.last_modified else "Unknown"
        table.add_row(alias, type_name, model.name, size_text, modified)

    console.print(table)
    console.print(f"\n[dim]{len(filtered_models)} model(s)[/dim]")
    if incomplete_models:
        console.print(
            "[yellow]Detected incomplete downloads:[/yellow] "
            + ", ".join(sorted(set(incomplete_models)))
        )
