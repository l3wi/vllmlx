"""Search command for discovering packaged mlx-community models."""

from __future__ import annotations

import json

import click
from rich.console import Console
from rich.table import Table

from vllmlx.models.catalog import CatalogEntry, search_catalog
from vllmlx.models.registry import format_size

console = Console()


def _to_payload(entry: CatalogEntry, *, size_bytes: int | None) -> dict[str, str | int | None]:
    return {
        "alias": entry.alias,
        "repo_id": entry.repo_id,
        "description": entry.description,
        "model_type": entry.model_type,
        "release_date": entry.release_date,
        "size_bytes": size_bytes,
        "updated_at": entry.updated_at,
    }


@click.command()
@click.argument("query", required=False, default="")
@click.option("--limit", type=int, default=20, show_default=True, help="Maximum results.")
@click.option(
    "--type",
    "model_type",
    type=click.Choice(["text", "vision", "embedding", "audio"], case_sensitive=False),
    help="Filter by model type.",
)
@click.option("--json", "as_json", is_flag=True, help="Output JSON.")
def search(query: str, limit: int, model_type: str | None, as_json: bool):
    """Search packaged mlx-community model catalog."""
    if limit <= 0:
        raise click.BadParameter("limit must be greater than 0", param_hint="--limit")

    results = search_catalog(query, limit=limit, model_type=model_type)

    if as_json:
        payload = [_to_payload(entry, size_bytes=entry.size_bytes) for entry in results]
        click.echo(json.dumps(payload, ensure_ascii=True, indent=2))
        return

    if not results:
        console.print("[yellow]No models found.[/yellow]")
        return

    table = Table(title="mlx-community Model Search")
    table.add_column("Alias", style="green", no_wrap=True)
    table.add_column("Type", style="magenta", no_wrap=True)
    table.add_column("Release", style="cyan", no_wrap=True)
    table.add_column("Size", style="yellow", justify="right", no_wrap=True)
    table.add_column("Updated", style="dim", no_wrap=True)
    table.add_column("Repo", style="blue")
    table.add_column("Description", style="white")

    for entry in results:
        size = format_size(entry.size_bytes) if isinstance(entry.size_bytes, int) else "-"
        updated = entry.updated_at[:10] if entry.updated_at else "-"
        table.add_row(
            entry.alias,
            entry.model_type,
            entry.release_date or "-",
            size,
            updated,
            entry.repo_id,
            entry.description,
        )

    console.print(table)
    console.print(
        f"\n[dim]{len(results)} result(s). Pull with: vllmlx pull <alias-or-repo-id>[/dim]"
    )
