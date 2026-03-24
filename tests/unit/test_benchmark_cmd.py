"""Tests for benchmark CLI JSON output."""

from __future__ import annotations

import json

from click.testing import CliRunner

from vllmlx.cli.benchmark import BenchmarkSummary, MemoryStats
from vllmlx.cli.main import cli


def test_benchmark_json_outputs_machine_readable_summary(monkeypatch):
    runner = CliRunner()
    summary = BenchmarkSummary(
        model="mlx-community/Llama-3.2-1B-Instruct-4bit",
        cold_start_time_s=1.25,
        warm_start_time_s=0.75,
        memory_before=MemoryStats(system_percent=40.0),
        memory_after_load=MemoryStats(system_percent=45.0, metal_active_gb=1.5),
        memory_peak=MemoryStats(system_percent=48.0, metal_peak_gb=2.0),
        model_memory_gb=1.1,
        avg_ttft_s=0.08,
        min_ttft_s=0.07,
        max_ttft_s=0.09,
        avg_tokens_per_sec=12.5,
        min_tokens_per_sec=11.0,
        max_tokens_per_sec=14.0,
        std_tokens_per_sec=1.1,
        total_tokens=42,
        total_time_s=3.5,
        total_iterations=1,
    )

    monkeypatch.setattr("vllmlx.cli.benchmark._reset_peak_memory", lambda: None)
    monkeypatch.setattr("vllmlx.cli.benchmark._get_memory_stats", lambda: MemoryStats())
    monkeypatch.setattr("vllmlx.cli.benchmark._measure_cold_start", lambda model, quiet=False: 1.25)
    monkeypatch.setattr(
        "vllmlx.cli.benchmark._measure_warm_start",
        lambda model, quiet=False: (0.75, object(), object(), object()),
    )
    monkeypatch.setattr("vllmlx.cli.benchmark._run_benchmark", lambda *args, **kwargs: [])
    monkeypatch.setattr("vllmlx.cli.benchmark._build_summary", lambda *args, **kwargs: summary)
    monkeypatch.setattr(
        "vllmlx.cli.benchmark._display_results",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("table output should be skipped")
        ),
    )
    monkeypatch.setattr("vllmlx.cli.benchmark._unload_model", lambda *args, **kwargs: None)
    monkeypatch.setattr("vllmlx.config.Config.load", classmethod(lambda cls: cls()))
    monkeypatch.setattr(
        "vllmlx.models.aliases.resolve_alias",
        lambda model, aliases=None: "mlx-community/Llama-3.2-1B-Instruct-4bit",
    )

    result = runner.invoke(
        cli,
        [
            "benchmark",
            "llama-3.2-1b-instruct-4bit",
            "--json",
            "-n",
            "1",
            "-t",
            "16",
            "--warmup",
            "0",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["model"] == "mlx-community/Llama-3.2-1B-Instruct-4bit"
    assert payload["cold_start_time_s"] == 1.25
    assert payload["warm_start_time_s"] == 0.75
    assert payload["total_tokens"] == 42
    assert payload["memory_peak"]["metal_peak_gb"] == 2.0
