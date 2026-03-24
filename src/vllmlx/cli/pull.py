"""Pull command for downloading models."""

import os

import click
from rich.console import Console

from vllmlx.config import Config
from vllmlx.models.aliases import resolve_alias
from vllmlx.models.loader import ensure_model_downloaded

console = Console()


def _requires_non_mlx_confirmation(model_path: str) -> bool:
    """Return True when model path is a non-mlx-community HF repo id."""
    if os.path.exists(model_path):
        return False
    if "/" not in model_path:
        return False
    namespace, _ = model_path.split("/", 1)
    return namespace.lower() != "mlx-community"


@click.command()
@click.argument("model")
@click.option(
    "-y",
    "--yes",
    is_flag=True,
    help="Skip confirmation prompt for non-mlx-community models.",
)
def pull(model: str, yes: bool):
    """Download a model from HuggingFace.

    MODEL can be:
    - a packaged catalog alias (e.g., qwen2-vl-2b-instruct-4bit, qwen3-8b-4bit)
    - a full HuggingFace repo ID (e.g., mlx-community/Qwen3-8B-4bit)
    - a HuggingFace URL (e.g., https://huggingface.co/Qwen/Qwen3-Embedding-4B)

    Examples:

        vllmlx pull qwen3-8b-4bit

        vllmlx pull mlx-community/Some-Model-4bit

        vllmlx pull https://huggingface.co/Qwen/Qwen3-Embedding-4B
    """
    # Load config for custom aliases
    config = Config.load()

    # Resolve alias to full HF path
    hf_path = resolve_alias(model, custom_aliases=config.aliases)

    if _requires_non_mlx_confirmation(hf_path) and not yes:
        click.confirm(
            (
                f"'{hf_path}' is outside mlx-community. "
                "Continue downloading from a third-party namespace?"
            ),
            default=False,
            abort=True,
        )

    try:
        local_path, was_cached = ensure_model_downloaded(
            hf_path,
            verify_complete=True,
        )

        if was_cached:
            console.print(f"[green]✓[/green] Model [cyan]{model}[/cyan] already downloaded")
        else:
            console.print(f"[green]✓[/green] Successfully downloaded [cyan]{model}[/cyan]")

    except Exception as e:
        console.print(f"[red]✗[/red] Failed to download [cyan]{model}[/cyan]: {e}")
        raise SystemExit(1)
