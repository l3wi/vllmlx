"""Model loading utilities with progress indicators."""

import os
import threading
import time
from typing import Any, Tuple

from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    DownloadColumn,
    TransferSpeedColumn,
    TimeRemainingColumn,
    MofNCompleteColumn,
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


def _get_partial_download_size(model_path: str, cache_dir: str) -> int:
    """Check for partial downloads and return total size downloaded so far."""
    from pathlib import Path

    total = 0
    try:
        # HuggingFace cache structure: models--{org}--{repo}/blobs/
        safe_name = model_path.replace("/", "--")
        model_cache = Path(cache_dir) / f"models--{safe_name}"

        if model_cache.exists():
            # Check blobs directory for downloaded files
            blobs_dir = model_cache / "blobs"
            if blobs_dir.exists():
                for f in blobs_dir.iterdir():
                    if f.is_file():
                        total += f.stat().st_size

            # Also check for incomplete downloads (.incomplete files)
            for f in model_cache.rglob("*.incomplete"):
                total += f.stat().st_size
    except Exception:
        pass

    return total


class RichDownloadProgress:
    """Custom tqdm-compatible progress bar using Rich for HuggingFace downloads."""
    _lock = threading.RLock()

    def __init__(self, *args, **kwargs):
        self.total = kwargs.get("total", 0)
        self.desc = kwargs.get("desc", "")
        self.unit = kwargs.get("unit", "it")
        self.n = 0
        self._progress = None
        self._task = None

    def __enter__(self):
        if self.unit == "B":
            # File download progress
            self._progress = Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.description}"),
                BarColumn(),
                DownloadColumn(),
                TransferSpeedColumn(),
                TimeRemainingColumn(),
                console=console,
            )
        else:
            # File count progress
            self._progress = Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.description}"),
                BarColumn(),
                MofNCompleteColumn(),
                TimeRemainingColumn(),
                console=console,
            )
        self._progress.start()
        self._task = self._progress.add_task(self.desc, total=self.total)
        return self

    def __exit__(self, *args):
        if self._progress:
            self._progress.stop()

    def update(self, n=1):
        self.n += n
        if self._progress and self._task is not None:
            self._progress.update(self._task, advance=n)

    def set_description(self, desc):
        self.desc = desc
        if self._progress and self._task is not None:
            self._progress.update(self._task, description=desc)

    def close(self):
        pass

    @classmethod
    def get_lock(cls):
        """Provide tqdm-compatible class lock API for huggingface_hub."""
        return cls._lock

    @classmethod
    def set_lock(cls, lock):
        """Provide tqdm-compatible class lock API for huggingface_hub."""
        cls._lock = lock


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


def _download_snapshot_with_live_progress(
    model_path: str,
    total_size: int | None,
    quiet: bool,
) -> str:
    """Download snapshot and render a live byte-level progress view."""
    from huggingface_hub import snapshot_download

    if quiet:
        return snapshot_download(model_path, resume_download=True)

    cache_dir = os.path.join(os.path.expanduser("~"), ".cache", "huggingface", "hub")
    result: dict[str, str | BaseException | None] = {"local_path": None, "error": None}
    done = threading.Event()

    def _worker() -> None:
        try:
            result["local_path"] = snapshot_download(
                model_path,
                resume_download=True,
            )
        except BaseException as exc:
            result["error"] = exc
        finally:
            done.set()

    worker = threading.Thread(target=_worker, daemon=True)
    worker.start()

    initial_downloaded = _get_partial_download_size(model_path, cache_dir)
    known_total = total_size if isinstance(total_size, int) and total_size > 0 else None

    if known_total:
        progress_columns = [
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TextColumn("[bold]{task.percentage:>5.1f}%[/bold]"),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
        ]
    else:
        progress_columns = [
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            DownloadColumn(),
            TransferSpeedColumn(),
            TextColumn("[dim]total unknown[/dim]"),
        ]

    try:
        if not console.is_terminal:
            last_report = 0.0
            while not done.is_set():
                now = time.monotonic()
                if now - last_report >= 1.0:
                    downloaded = _get_partial_download_size(model_path, cache_dir)
                    if known_total:
                        pct = (downloaded / known_total * 100) if known_total else 0.0
                        console.print(
                            f"[dim]Downloading... {_format_size(downloaded)} / "
                            f"{_format_size(known_total)} ({pct:.1f}%)[/dim]"
                        )
                    else:
                        console.print(f"[dim]Downloading... {_format_size(downloaded)}[/dim]")
                    last_report = now
                done.wait(0.2)
        else:
            with Progress(
                *progress_columns,
                console=console,
                refresh_per_second=20,
                auto_refresh=True,
            ) as progress:
                initial_completed = (
                    min(initial_downloaded, known_total)
                    if known_total
                    else initial_downloaded
                )
                task = progress.add_task(
                    "Downloading files...",
                    total=known_total,
                    completed=initial_completed,
                )

                while not done.is_set():
                    downloaded = _get_partial_download_size(model_path, cache_dir)
                    if known_total:
                        progress.update(task, completed=min(downloaded, known_total))
                    else:
                        progress.update(task, completed=downloaded)
                    progress.refresh()
                    done.wait(0.2)

                final_downloaded = _get_partial_download_size(model_path, cache_dir)
                if known_total:
                    progress.update(task, completed=min(final_downloaded, known_total))
                else:
                    progress.update(task, completed=final_downloaded)
                progress.refresh()
    except KeyboardInterrupt:
        console.print("\n[yellow]Download paused. Run the same command to resume.[/yellow]")
        raise

    worker.join()

    if isinstance(result["error"], BaseException):
        raise result["error"]

    local_path = result["local_path"]
    if not isinstance(local_path, str):
        raise RuntimeError("Download failed without returning a local path")
    return local_path


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
    from huggingface_hub import snapshot_download
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
        local_path = snapshot_download(
            model_path,
            local_files_only=True,
        )
        if not verify_complete:
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
                console.print("[dim]Resuming download to complete missing files...[/dim]\n")
            else:
                console.print(
                    "[yellow]Unable to validate cached size from Hub metadata.[/yellow]"
                )
                console.print("[dim]Verifying by resuming download...[/dim]\n")
    except Exception:
        pass  # Not cached, need to download

    # Get repo info for size estimation and check for partial downloads
    if not quiet:
        try:
            total_size = remote_total_size
            if total_size is None:
                total_size = _fetch_remote_total_size(model_path)

            # Check for existing partial downloads
            cache_dir = os.path.join(os.path.expanduser("~"), ".cache", "huggingface", "hub")
            partial_size = _get_partial_download_size(model_path, cache_dir)

            console.print(f"[bold blue]Downloading[/bold blue] [cyan]{model_path}[/cyan]")
            if total_size > 0:
                console.print(f"Total size: [yellow]{_format_size(total_size)}[/yellow]")
            else:
                console.print("Total size: [yellow]unknown[/yellow]")

            if partial_size > 0:
                pct = (partial_size / total_size * 100) if total_size > 0 else 0
                console.print(f"Resuming: [green]{_format_size(partial_size)}[/green] already downloaded ({pct:.1f}%)")
            else:
                console.print("[dim]Download is resumable - Ctrl+C to pause, run again to resume[/dim]")
            console.print()
        except Exception:
            console.print(f"[bold blue]Downloading[/bold blue] [cyan]{model_path}[/cyan]...")

    # Download with resumable live progress monitoring.
    try:
        local_path = _download_snapshot_with_live_progress(
            model_path=model_path,
            total_size=total_size if "total_size" in locals() else remote_total_size,
            quiet=quiet,
        )
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
    import sys
    import io
    import warnings
    import threading
    
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
