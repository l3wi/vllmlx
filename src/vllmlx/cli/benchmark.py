"""Benchmark command for vllmlx CLI - measures model performance metrics."""

import json
import signal
import statistics
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from typing import Any, List, Tuple

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

console = Console()

# Default benchmark prompts of varying complexity
DEFAULT_PROMPTS = [
    "What is the capital of France?",
    "Explain quantum computing in simple terms.",
    "Write a haiku about the ocean.",
    "List 5 benefits of regular exercise.",
    "Describe the process of photosynthesis step by step.",
]


class TimeoutError(Exception):
    """Raised when an operation times out."""

    pass


@contextmanager
def timeout(seconds: int, message: str = "Operation timed out"):
    """Context manager for timing out operations."""

    def handler(signum, frame):
        raise TimeoutError(message)

    old_handler = signal.signal(signal.SIGALRM, handler)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


@dataclass
class MemoryStats:
    """Memory usage statistics."""

    system_used_gb: float = 0.0
    system_available_gb: float = 0.0
    system_percent: float = 0.0
    metal_active_gb: float = 0.0
    metal_peak_gb: float = 0.0
    metal_cache_gb: float = 0.0


@dataclass
class BenchmarkResult:
    """Results from a single generation."""

    prompt: str
    iteration: int
    tokens: int
    total_time_s: float
    time_to_first_token_s: float
    generation_time_s: float
    tokens_per_second: float  # excludes TTFT, pure generation speed
    is_warm: bool = True


@dataclass
class BenchmarkSummary:
    """Aggregated benchmark statistics."""

    model: str
    cold_start_time_s: float
    warm_start_time_s: float

    # Memory
    memory_before: MemoryStats = field(default_factory=MemoryStats)
    memory_after_load: MemoryStats = field(default_factory=MemoryStats)
    memory_peak: MemoryStats = field(default_factory=MemoryStats)
    model_memory_gb: float = 0.0  # Estimated model memory footprint

    # Time to first token
    avg_ttft_s: float = 0.0
    min_ttft_s: float = 0.0
    max_ttft_s: float = 0.0

    # Token generation rate (excluding TTFT)
    avg_tokens_per_sec: float = 0.0
    min_tokens_per_sec: float = 0.0
    max_tokens_per_sec: float = 0.0
    std_tokens_per_sec: float = 0.0

    # Totals
    total_tokens: int = 0
    total_time_s: float = 0.0
    total_iterations: int = 0


def _get_memory_stats() -> MemoryStats:
    """Get current memory usage."""
    stats = MemoryStats()

    # System memory via psutil
    try:
        import psutil

        mem = psutil.virtual_memory()
        stats.system_used_gb = mem.used / (1024**3)
        stats.system_available_gb = mem.available / (1024**3)
        stats.system_percent = mem.percent
    except ImportError:
        pass

    # Metal/GPU memory via MLX (use new API, fallback to old)
    try:
        import mlx.core as mx

        # New API (mlx >= 0.22)
        if hasattr(mx, "get_active_memory"):
            stats.metal_active_gb = mx.get_active_memory() / (1024**3)
            stats.metal_peak_gb = mx.get_peak_memory() / (1024**3)
            stats.metal_cache_gb = mx.get_cache_memory() / (1024**3)
        # Old API (fallback)
        elif hasattr(mx.metal, "get_active_memory"):
            stats.metal_active_gb = mx.metal.get_active_memory() / (1024**3)
            stats.metal_peak_gb = mx.metal.get_peak_memory() / (1024**3)
            stats.metal_cache_gb = mx.metal.get_cache_memory() / (1024**3)
    except Exception:
        pass

    return stats


def _reset_peak_memory():
    """Reset MLX peak memory tracking."""
    try:
        import mlx.core as mx

        # New API (mlx >= 0.22)
        if hasattr(mx, "reset_peak_memory"):
            mx.reset_peak_memory()
        # Old API (fallback)
        elif hasattr(mx.metal, "reset_peak_memory"):
            mx.metal.reset_peak_memory()
    except Exception:
        pass


def _format_memory(gb: float) -> str:
    """Format memory size nicely."""
    if gb < 1:
        return f"{gb * 1024:.0f}MB"
    return f"{gb:.2f}GB"


@click.command()
@click.argument("model", required=True)
@click.option("--iterations", "-n", default=5, help="Number of iterations per prompt (default: 5)")
@click.option(
    "--max-tokens", "-t", default=100, help="Maximum tokens to generate per response (default: 100)"
)
@click.option(
    "--prompt", "-p", multiple=True, help="Custom prompt(s) to use (can specify multiple)"
)
@click.option("--warmup", "-w", default=1, help="Number of warmup iterations (default: 1)")
@click.option("--temp", default=0.7, help="Temperature for sampling (default: 0.7)")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output for each iteration")
@click.option(
    "--skip-cold-start",
    is_flag=True,
    help="Skip cold start measurement (model already loaded elsewhere)",
)
@click.option(
    "--timeout-load", default=300, help="Timeout for model loading in seconds (default: 300)"
)
@click.option("--timeout-gen", default=120, help="Timeout for generation in seconds (default: 120)")
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    help="Emit machine-readable JSON summary to stdout.",
)
def benchmark(
    model: str,
    iterations: int,
    max_tokens: int,
    prompt: tuple,
    warmup: int,
    temp: float,
    verbose: bool,
    skip_cold_start: bool,
    timeout_load: int,
    timeout_gen: int,
    as_json: bool,
):
    """Benchmark model performance metrics.

    MODEL is the model name or alias (e.g., qwen2-vl-7b).

    Measures:
    - Cold start time (model loading)
    - Warm start time (subsequent loads from cache)
    - Memory usage (system RAM + Metal GPU memory)
    - Time to first token (TTFT)
    - Average token generation rate

    Examples:
        vllmlx benchmark qwen2-vl-7b
        vllmlx benchmark qwen2-vl-7b -n 10 -t 200
        vllmlx benchmark qwen2-vl-7b -p "Explain AI" -p "Write a poem"
        vllmlx benchmark qwen2-vl-7b -v  # verbose output
    """
    from vllmlx.config import Config
    from vllmlx.models.aliases import resolve_alias

    config = Config.load()
    model_path = resolve_alias(model, config.aliases)
    quiet = as_json

    # Use custom prompts or defaults
    prompts = list(prompt) if prompt else DEFAULT_PROMPTS

    if not quiet:
        console.print("\n[bold blue]vllmlx benchmark[/bold blue]")
        console.print(f"Model: [cyan]{model_path}[/cyan]")
        console.print(f"Iterations: {iterations} per prompt")
        console.print(f"Max tokens: {max_tokens}")
        console.print(f"Prompts: {len(prompts)}")
        console.print()

    # Get baseline memory
    _reset_peak_memory()
    memory_before = _get_memory_stats()
    if not quiet:
        console.print("[bold]0. Baseline memory...[/bold]")
        console.print(
            f"   System: {_format_memory(memory_before.system_used_gb)} used "
            f"({memory_before.system_percent:.1f}%)"
        )
        console.print(f"   Metal:  {_format_memory(memory_before.metal_active_gb)} active")
        console.print()

    # Measure cold start
    cold_start_time = 0.0
    if not skip_cold_start:
        if not quiet:
            console.print("[bold]1. Measuring cold start time...[/bold]")
        try:
            with timeout(timeout_load, f"Cold start timed out after {timeout_load}s"):
                cold_start_time = _measure_cold_start(model_path, quiet=quiet)
        except TimeoutError as e:
            console.print(f"[red]Error: {e}[/red]")
            raise SystemExit(1)
        if cold_start_time < 0:
            raise SystemExit(1)
        if not quiet:
            console.print(f"[green]✓ Cold start: {cold_start_time:.2f}s[/green]\n")

    # Measure warm start with memory tracking
    _reset_peak_memory()
    if not quiet:
        console.print("[bold]2. Measuring warm start time + memory...[/bold]")
    try:
        with timeout(timeout_load, f"Warm start timed out after {timeout_load}s"):
            warm_start_time, model_obj, processor, model_config = _measure_warm_start(
                model_path,
                quiet=quiet,
            )
    except TimeoutError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)
    if warm_start_time < 0:
        raise SystemExit(1)

    memory_after_load = _get_memory_stats()
    model_memory = memory_after_load.metal_active_gb - memory_before.metal_active_gb

    if not quiet:
        console.print(f"[green]✓ Warm start: {warm_start_time:.2f}s[/green]")
        console.print(f"   Model memory: [yellow]{_format_memory(model_memory)}[/yellow]")
        console.print(f"   Metal active: {_format_memory(memory_after_load.metal_active_gb)}")
        console.print(
            f"   System: {_format_memory(memory_after_load.system_used_gb)} "
            f"({memory_after_load.system_percent:.1f}%)"
        )
        console.print()

    try:
        # Run benchmark with TTFT measurement
        if not quiet:
            console.print("[bold]3. Running generation benchmark...[/bold]")
        results = _run_benchmark(
            model_obj,
            processor,
            model_config,
            prompts,
            iterations,
            max_tokens,
            temp,
            warmup,
            verbose,
            timeout_gen,
            quiet=quiet,
        )

        # Get peak memory after generation
        memory_peak = _get_memory_stats()

        # Build and display summary
        summary = _build_summary(
            model_path,
            cold_start_time,
            warm_start_time,
            results,
            memory_before,
            memory_after_load,
            memory_peak,
            model_memory,
        )
        if quiet:
            click.echo(json.dumps(_summary_to_dict(summary), sort_keys=True))
        else:
            _display_results(summary, verbose)

    finally:
        # Cleanup
        _unload_model(model_obj, processor, model_config)


def _measure_cold_start(model_path: str, *, quiet: bool = False) -> float:
    """Measure cold start time (loading model from scratch).

    Returns time in seconds, or -1 on error.
    """
    import gc
    import warnings

    from vllmlx.models.loader import load_model_with_progress, unload_model

    warnings.filterwarnings("ignore")

    # Clear any cached models first
    gc.collect()
    _clear_mlx_cache()

    try:
        model, processor, config, elapsed = load_model_with_progress(model_path, quiet=quiet)

        # Unload immediately
        unload_model(model, processor, config)

        return elapsed

    except Exception as e:
        if not quiet:
            console.print(f"[red]Error during cold start: {e}[/red]")
        return -1


def _measure_warm_start(model_path: str, *, quiet: bool = False) -> Tuple[float, Any, Any, Any]:
    """Measure warm start time (loading with caches warm).

    Returns (time_seconds, model, processor, config) or (-1, None, None, None) on error.
    """
    import warnings

    from vllmlx.models.loader import load_model_with_progress

    warnings.filterwarnings("ignore")

    try:
        model, processor, config, elapsed = load_model_with_progress(model_path, quiet=quiet)
        return elapsed, model, processor, config

    except Exception as e:
        if not quiet:
            console.print(f"[red]Error during warm start: {e}[/red]")
        return -1, None, None, None


def _clear_mlx_cache():
    """Clear MLX memory cache."""
    try:
        import mlx.core as mx

        # New API (mlx >= 0.22)
        if hasattr(mx, "clear_memory_cache"):
            mx.clear_memory_cache()
        # Old API variants
        elif hasattr(mx, "clear_cache"):
            mx.clear_cache()
        elif hasattr(mx.metal, "clear_cache"):
            mx.metal.clear_cache()
    except Exception:
        pass


def _unload_model(model, processor, config):
    """Unload model and free memory."""
    from vllmlx.models.loader import unload_model

    unload_model(model, processor, config)


def _run_benchmark(
    model,
    processor,
    config,
    prompts: List[str],
    iterations: int,
    max_tokens: int,
    temp: float,
    warmup: int,
    verbose: bool,
    timeout_gen: int,
    quiet: bool = False,
) -> List[BenchmarkResult]:
    """Run the benchmark with TTFT measurement."""
    import warnings

    from mlx_vlm.prompt_utils import apply_chat_template

    warnings.filterwarnings("ignore")

    results: List[BenchmarkResult] = []
    show_verbose = verbose and not quiet

    # Warmup runs (not measured)
    if warmup > 0:
        if not quiet:
            console.print(f"[dim]Running {warmup} warmup iteration(s)...[/dim]")
        for i in range(warmup):
            try:
                formatted = apply_chat_template(processor, config, prompts[0], num_images=0)
                with timeout(timeout_gen, f"Warmup {i + 1} timed out"):
                    _generate_with_ttft(model, processor, formatted, max_tokens=50, temp=temp)
            except TimeoutError as e:
                if not quiet:
                    console.print(f"[yellow]Warning: {e}[/yellow]")
        if not quiet:
            console.print("[dim]Warmup complete[/dim]\n")

    def _run_iteration(prompt_text: str, iter_num: int) -> bool:
        formatted = apply_chat_template(processor, config, prompt_text, num_images=0)

        try:
            with timeout(timeout_gen, f"Generation timed out after {timeout_gen}s"):
                response, ttft, gen_time, total_time = _generate_with_ttft(
                    model, processor, formatted, max_tokens=max_tokens, temp=temp
                )
        except TimeoutError as e:
            if not quiet:
                console.print(f"\n[yellow]Warning: {e} - skipping[/yellow]")
            return False

        tokens = _count_tokens(processor, response)
        tps = tokens / gen_time if gen_time > 0 else 0

        results.append(
            BenchmarkResult(
                prompt=prompt_text[:50] + "..." if len(prompt_text) > 50 else prompt_text,
                iteration=iter_num + 1,
                tokens=tokens,
                total_time_s=total_time,
                time_to_first_token_s=ttft,
                generation_time_s=gen_time,
                tokens_per_second=tps,
                is_warm=True,
            )
        )

        if show_verbose:
            mem = _get_memory_stats()
            console.print(
                f"  [dim]Iter {iter_num + 1}: {tokens} tokens, "
                f"TTFT={ttft * 1000:.0f}ms, "
                f"gen={gen_time:.2f}s, "
                f"{tps:.1f} tok/s, "
                f"mem={_format_memory(mem.metal_active_gb)}[/dim]"
            )
        return True

    if quiet:
        for prompt_text in prompts:
            for iter_num in range(iterations):
                _run_iteration(prompt_text, iter_num)
        return results

    # Main benchmark
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=not verbose,
    ) as progress:
        task = progress.add_task("Running benchmark...", total=len(prompts) * iterations)

        for prompt_idx, prompt_text in enumerate(prompts):
            for iter_num in range(iterations):
                progress.update(
                    task,
                    description=(
                        f"Prompt {prompt_idx + 1}/{len(prompts)}, iter {iter_num + 1}/{iterations}"
                    ),
                )
                _run_iteration(prompt_text, iter_num)
                progress.advance(task)

            if verbose and iterations > 1:
                prompt_results = [r for r in results if r.prompt == results[-1].prompt]
                if prompt_results:
                    avg_tps = statistics.mean([r.tokens_per_second for r in prompt_results])
                    avg_ttft = (
                        statistics.mean([r.time_to_first_token_s for r in prompt_results]) * 1000
                    )
                    console.print(
                        f"  [cyan]Prompt avg: {avg_tps:.1f} tok/s, TTFT={avg_ttft:.0f}ms[/cyan]\n"
                    )

    return results


def _generate_with_ttft(
    model, processor, prompt: str, max_tokens: int, temp: float
) -> Tuple[str, float, float, float]:
    """Generate text and measure time to first token.

    Returns: (response_text, ttft_seconds, generation_time_seconds, total_time_seconds)
    """
    import io
    import sys

    try:
        from mlx_vlm.utils import generate_step, prepare_inputs
    except ImportError:
        # Fallback if generate_step not available
        return _generate_simple_fallback(model, processor, prompt, max_tokens, temp)

    # Suppress output
    old_stdout, old_stderr = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = io.StringIO()

    try:
        total_start = time.perf_counter()

        # Prepare inputs
        inputs = prepare_inputs(processor, [prompt], [])
        input_ids = inputs["input_ids"]
        pixel_values = inputs.get("pixel_values")
        mask = inputs.get("attention_mask")

        # Measure time to first token
        ttft_start = time.perf_counter()

        tokens = []
        first_token_time = None

        for i, (token, _) in enumerate(
            generate_step(
                model=model,
                input_ids=input_ids,
                pixel_values=pixel_values,
                mask=mask,
                cache=None,
                temp=temp,
                max_tokens=max_tokens,
            )
        ):
            if i == 0:
                first_token_time = time.perf_counter()
            tokens.append(token.item())

            # Check for EOS
            if hasattr(processor, "tokenizer"):
                eos_token_id = getattr(processor.tokenizer, "eos_token_id", None)
            else:
                eos_token_id = getattr(processor, "eos_token_id", None)

            if eos_token_id is not None and token.item() == eos_token_id:
                break

        total_end = time.perf_counter()

        # Calculate times
        ttft = (first_token_time - ttft_start) if first_token_time else 0
        total_time = total_end - total_start
        gen_time = (total_end - first_token_time) if first_token_time else total_time

        # Decode response
        if hasattr(processor, "tokenizer"):
            response = processor.tokenizer.decode(tokens, skip_special_tokens=True)
        else:
            response = processor.decode(tokens, skip_special_tokens=True)

        return response, ttft, gen_time, total_time

    except Exception:
        # Fallback to simple generate if streaming not available
        sys.stdout, sys.stderr = old_stdout, old_stderr
        return _generate_simple_fallback(model, processor, prompt, max_tokens, temp)
    finally:
        sys.stdout, sys.stderr = old_stdout, old_stderr


def _generate_simple_fallback(
    model, processor, prompt: str, max_tokens: int, temp: float
) -> Tuple[str, float, float, float]:
    """Fallback generation without TTFT measurement."""
    import io
    import sys

    from mlx_vlm import generate

    old_stdout, old_stderr = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = io.StringIO()

    try:
        start = time.perf_counter()
        response = generate(
            model, processor, prompt, [], max_tokens=max_tokens, temp=temp, verbose=False
        )
        elapsed = time.perf_counter() - start

        # Estimate TTFT as 10% of total time (rough approximation)
        ttft = elapsed * 0.1
        gen_time = elapsed * 0.9

        return response, ttft, gen_time, elapsed
    finally:
        sys.stdout, sys.stderr = old_stdout, old_stderr


def _count_tokens(processor, text: str) -> int:
    """Count tokens in text using the processor's tokenizer."""
    try:
        if hasattr(processor, "tokenizer"):
            tokens = processor.tokenizer.encode(text)
        else:
            tokens = processor.encode(text)
        return len(tokens)
    except Exception:
        # Fallback: rough estimate
        return int(len(text.split()) * 1.3)


def _build_summary(
    model_path: str,
    cold_start: float,
    warm_start: float,
    results: List[BenchmarkResult],
    memory_before: MemoryStats,
    memory_after_load: MemoryStats,
    memory_peak: MemoryStats,
    model_memory: float,
) -> BenchmarkSummary:
    """Build summary statistics from results."""

    summary = BenchmarkSummary(
        model=model_path,
        cold_start_time_s=cold_start,
        warm_start_time_s=warm_start,
        memory_before=memory_before,
        memory_after_load=memory_after_load,
        memory_peak=memory_peak,
        model_memory_gb=model_memory,
    )

    if results:
        ttft_values = [r.time_to_first_token_s for r in results]
        tps_values = [r.tokens_per_second for r in results]

        summary.avg_ttft_s = statistics.mean(ttft_values)
        summary.min_ttft_s = min(ttft_values)
        summary.max_ttft_s = max(ttft_values)
        summary.avg_tokens_per_sec = statistics.mean(tps_values)
        summary.min_tokens_per_sec = min(tps_values)
        summary.max_tokens_per_sec = max(tps_values)
        summary.std_tokens_per_sec = statistics.stdev(tps_values) if len(tps_values) > 1 else 0
        summary.total_tokens = sum(r.tokens for r in results)
        summary.total_time_s = sum(r.total_time_s for r in results)
        summary.total_iterations = len(results)

    return summary


def _summary_to_dict(summary: BenchmarkSummary) -> dict[str, Any]:
    """Convert benchmark summary dataclasses to a JSON-safe dictionary."""
    return asdict(summary)


def _display_results(summary: BenchmarkSummary, verbose: bool):
    """Display benchmark results in formatted tables."""

    console.print()

    # Main results table
    table = Table(title="Benchmark Results", show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan", width=25)
    table.add_column("Value", justify="right", width=20)

    table.add_row("Model", summary.model.split("/")[-1])
    table.add_row("", "")

    # Startup times
    table.add_row("[bold]Startup Times[/bold]", "")
    if summary.cold_start_time_s > 0:
        table.add_row("  Cold Start", f"{summary.cold_start_time_s:.2f}s")
    table.add_row("  Warm Start", f"{summary.warm_start_time_s:.2f}s")
    table.add_row("", "")

    # Memory
    table.add_row("[bold]Memory Usage[/bold]", "")
    table.add_row("  Model Size", f"[yellow]{_format_memory(summary.model_memory_gb)}[/yellow]")
    table.add_row(
        "  Metal Active (loaded)", _format_memory(summary.memory_after_load.metal_active_gb)
    )
    table.add_row("  Metal Peak", f"[red]{_format_memory(summary.memory_peak.metal_peak_gb)}[/red]")
    table.add_row("  System RAM (before)", f"{summary.memory_before.system_percent:.1f}%")
    table.add_row("  System RAM (peak)", f"{summary.memory_peak.system_percent:.1f}%")
    table.add_row("", "")

    # Time to first token
    if summary.total_iterations > 0:
        table.add_row("[bold]Time to First Token[/bold]", "")
        table.add_row("  Average TTFT", f"[yellow]{summary.avg_ttft_s * 1000:.0f}ms[/yellow]")
        table.add_row("  Min TTFT", f"{summary.min_ttft_s * 1000:.0f}ms")
        table.add_row("  Max TTFT", f"{summary.max_ttft_s * 1000:.0f}ms")
        table.add_row("", "")

        # Token generation
        table.add_row("[bold]Token Generation[/bold]", "")
        table.add_row(
            "  Average Rate", f"[bold green]{summary.avg_tokens_per_sec:.2f} tok/s[/bold green]"
        )
        table.add_row("  Min Rate", f"{summary.min_tokens_per_sec:.2f} tok/s")
        table.add_row("  Max Rate", f"{summary.max_tokens_per_sec:.2f} tok/s")
        table.add_row("  Std Dev", f"±{summary.std_tokens_per_sec:.2f}")
        table.add_row("", "")

        # Totals
        table.add_row("[bold]Totals[/bold]", "")
        table.add_row("  Iterations", str(summary.total_iterations))
        table.add_row("  Total Tokens", str(summary.total_tokens))
        table.add_row("  Total Time", f"{summary.total_time_s:.2f}s")

    console.print(table)
    console.print()

    # Quick summary
    console.print("[bold]Summary:[/bold]")
    if summary.cold_start_time_s > 0:
        console.print(f"  🥶 Cold start: [cyan]{summary.cold_start_time_s:.2f}s[/cyan]")
    console.print(f"  🔥 Warm start: [cyan]{summary.warm_start_time_s:.2f}s[/cyan]")
    console.print(f"  💾 Model memory: [yellow]{_format_memory(summary.model_memory_gb)}[/yellow]")
    console.print(
        f"  📈 Peak Metal memory: [red]{_format_memory(summary.memory_peak.metal_peak_gb)}[/red]"
    )
    if summary.total_iterations > 0:
        console.print(
            f"  ⏱️  Time to first token: [yellow]{summary.avg_ttft_s * 1000:.0f}ms[/yellow] avg"
        )
        console.print(
            f"  🚀 Generation rate: [green]{summary.avg_tokens_per_sec:.2f} tokens/sec[/green] avg"
        )
    else:
        console.print("  [yellow]⚠️  No successful generations completed[/yellow]")
    console.print()
