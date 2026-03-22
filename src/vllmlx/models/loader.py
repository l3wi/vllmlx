"""Model loading utilities with progress indicators."""

import os
import threading
import time
from contextlib import contextmanager
from typing import Any, Tuple

from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
)

console = Console()


def _format_size(bytes: int) -> str:
    """Format byte size nicely."""
    if bytes < 1024:
        return f"{bytes}B"
    elif bytes < 1024**2:
        return f"{bytes/1024:.1f}KB"
    elif bytes < 1024**3:
        return f"{bytes/1024**2:.1f}MB"
    else:
        return f"{bytes/1024**3:.2f}GB"


@contextmanager
def _hf_progress_scope(*, quiet: bool):
    """Scope HF progress bars to a single download call when quiet is enabled."""
    if not quiet:
        yield
        return

    from huggingface_hub.utils import (
        are_progress_bars_disabled,
        disable_progress_bars,
        enable_progress_bars,
    )

    bars_previously_disabled = are_progress_bars_disabled()
    if not bars_previously_disabled:
        disable_progress_bars()
    try:
        yield
    finally:
        if not bars_previously_disabled:
            enable_progress_bars()


def _snapshot_download(
    model_path: str,
    *,
    local_files_only: bool = False,
    quiet: bool = False,
) -> str:
    """Download model snapshot using Hugging Face native downloader."""
    from huggingface_hub import snapshot_download

    if local_files_only:
        return snapshot_download(model_path, local_files_only=True)

    with _hf_progress_scope(quiet=quiet):
        return snapshot_download(model_path)


def _offline_mode_enabled() -> bool:
    """Return True when the standard Hugging Face offline env vars are enabled."""
    for name in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"):
        value = os.environ.get(name, "").strip().lower()
        if value in {"1", "true", "yes", "on"}:
            return True
    return False


def _fetch_remote_total_size(model_path: str) -> int | None:
    """Fetch total repository size from HuggingFace metadata."""
    from huggingface_hub import HfApi

    api = HfApi()
    try:
        info = api.repo_info(model_path, repo_type="model", files_metadata=True)
    except TypeError:
        info = api.repo_info(model_path, repo_type="model")

    siblings = info.siblings or []
    sizes = [s.size for s in siblings if isinstance(s.size, int)]
    if not sizes:
        return None
    return sum(sizes)


def _get_local_snapshot_size(snapshot_path: str) -> int:
    """Return total bytes in a resolved local snapshot path."""
    total = 0
    for root, _, files in os.walk(snapshot_path):
        for filename in files:
            file_path = os.path.join(root, filename)
            try:
                total += os.path.getsize(file_path)
            except OSError:
                continue
    return total


def ensure_model_downloaded(
    model_path: str,
    quiet: bool = False,
    verify_complete: bool = False,
) -> Tuple[str, bool]:
    """Ensure model is downloaded, showing progress if needed.

    Args:
        model_path: HuggingFace model path or local path
        quiet: Suppress progress output
        verify_complete: Validate cached size against live Hub metadata before
            reporting model as already downloaded.

    Returns:
        (local_path, was_already_cached)
    """
    import warnings

    warnings.filterwarnings("ignore")

    # Check if it's a local path
    if os.path.exists(model_path):
        return model_path, True

    remote_total_size: int | None = None
    if verify_complete:
        try:
            remote_total_size = _fetch_remote_total_size(model_path)
        except Exception:
            remote_total_size = None

    # Check if already cached
    try:
        local_path = _snapshot_download(model_path, local_files_only=True)
        if not verify_complete:
            return local_path, True

        # If live metadata cannot be fetched, trust existing cache to avoid
        # unnecessary redownloads in offline or rate-limited environments.
        if remote_total_size is None:
            return local_path, True

        local_size = _get_local_snapshot_size(local_path)
        if remote_total_size and local_size >= int(remote_total_size * 0.98):
            return local_path, True

        if not quiet:
            if remote_total_size:
                pct = (local_size / remote_total_size * 100) if remote_total_size > 0 else 0
                console.print(
                    f"[yellow]Cached model is incomplete[/yellow]: "
                    f"{_format_size(local_size)} / {_format_size(remote_total_size)} ({pct:.1f}%)"
                )
                console.print("[dim]Continuing download to complete missing files...[/dim]\n")
            else:
                console.print(
                    "[yellow]Unable to validate cached size from Hub metadata.[/yellow]"
                )
                console.print("[dim]Verifying by continuing download...[/dim]\n")
    except Exception:
        pass  # Not cached, need to download

    if _offline_mode_enabled():
        raise RuntimeError(
            f"Offline mode is enabled and {model_path} is not fully cached."
        )

    # Get repo info for size estimation and render pre-download context.
    total_size: int | None = remote_total_size
    if not quiet:
        try:
            if total_size is None:
                total_size = _fetch_remote_total_size(model_path)

            console.print(f"[bold blue]Downloading[/bold blue] [cyan]{model_path}[/cyan]")
            if isinstance(total_size, int) and total_size > 0:
                console.print(f"Total size: [yellow]{_format_size(total_size)}[/yellow]")
            else:
                console.print("Total size: [yellow]unknown[/yellow]")
            console.print("[dim]Using Hugging Face native downloader (resumable)[/dim]")
            console.print()
        except Exception:
            console.print(f"[bold blue]Downloading[/bold blue] [cyan]{model_path}[/cyan]...")

    # Download with Hugging Face native progress bars.
    try:
        local_path = _snapshot_download(model_path, quiet=quiet)
        if not quiet:
            console.print()
        return local_path, False
    except KeyboardInterrupt:
        raise
    except Exception as e:
        console.print(f"[red]Download failed: {e}[/red]")
        raise


def get_model_size(model_path: str) -> int:
    """Get total size of model files in bytes."""
    from pathlib import Path

    total_size = 0
    try:
        # First ensure we have the local path
        if os.path.exists(model_path):
            path = Path(model_path)
        else:
            # Get from cache
            from huggingface_hub import snapshot_download
            local_path = snapshot_download(model_path, local_files_only=True)
            path = Path(local_path)

        for pattern in ["*.safetensors", "*.bin", "*.gguf"]:
            for f in path.glob(pattern):
                total_size += f.stat().st_size
    except Exception:
        pass

    return total_size


def load_model_with_progress(
    model_path: str,
    quiet: bool = False,
    show_download: bool = True,
) -> Tuple[Any, Any, Any, float]:
    """Load model with progress indication.

    Args:
        model_path: HuggingFace model path or local path
        quiet: Suppress all output
        show_download: Show download progress for new models

    Returns:
        (model, processor, config, load_time_seconds)
    """
    import io
    import sys
    import warnings

    warnings.filterwarnings("ignore")

    # Ensure model is downloaded first
    if show_download:
        local_path, was_cached = ensure_model_downloaded(
            model_path,
            quiet=quiet,
            verify_complete=True,
        )
        if not quiet and not was_cached:
            console.print("[green]✓ Download complete[/green]\n")

    # Get model size for display
    total_size = get_model_size(model_path)

    from mlx_vlm import load
    from mlx_vlm.utils import load_config

    old_stderr = sys.stderr
    sys.stderr = io.StringIO()

    try:
        if quiet:
            start = time.perf_counter()
            model, processor = load(model_path)
            config = load_config(model_path)
            elapsed = time.perf_counter() - start
        else:
            size_str = f" ({_format_size(total_size)})" if total_size else ""

            # Use a spinner with elapsed time instead of fake progress
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.description}"),
                TextColumn("[dim]{task.fields[elapsed]}[/dim]"),
                console=console,
                transient=True,
            ) as progress:
                task = progress.add_task(f"Loading model{size_str}...", total=None, elapsed="")

                start = time.perf_counter()

                # Update elapsed time in background
                stop_event = threading.Event()
                def update_elapsed():
                    while not stop_event.is_set():
                        elapsed = time.perf_counter() - start
                        progress.update(task, elapsed=f"{elapsed:.1f}s")
                        stop_event.wait(0.1)

                timer_thread = threading.Thread(target=update_elapsed, daemon=True)
                timer_thread.start()

                try:
                    model, processor = load(model_path)
                    config = load_config(model_path)
                finally:
                    stop_event.set()
                    timer_thread.join(timeout=0.2)

                elapsed = time.perf_counter() - start

        return model, processor, config, elapsed

    finally:
        sys.stderr = old_stderr


def unload_model(model: Any = None, processor: Any = None, config: Any = None):
    """Unload model and free memory."""
    import gc

    try:
        if model:
            del model
        if processor:
            del processor
        if config:
            del config
        gc.collect()

        # Clear MLX cache
        try:
            import mlx.core as mx
            if hasattr(mx, 'clear_memory_cache'):
                mx.clear_memory_cache()
            elif hasattr(mx, 'clear_cache'):
                mx.clear_cache()
            elif hasattr(mx.metal, 'clear_cache'):
                mx.metal.clear_cache()
        except Exception:
            pass
    except Exception:
        pass
