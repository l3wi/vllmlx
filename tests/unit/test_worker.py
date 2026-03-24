"""Tests for backend worker argument parsing and scheduler wiring."""

from __future__ import annotations

import argparse
import sys
from enum import Enum
from types import SimpleNamespace
from unittest.mock import patch


def test_parse_args_accepts_new_scheduler_flags(monkeypatch):
    from vllmlx.backend.worker import parse_args

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "worker",
            "--model",
            "mlx-community/Qwen3-4B-4bit",
            "--continuous-batching",
            "--max-num-batched-tokens",
            "4096",
            "--scheduler-policy",
            "priority",
            "--prefill-step-size",
            "1024",
            "--disable-prefix-cache",
            "--prefix-cache-size",
            "42",
            "--chunked-prefill-tokens",
            "2048",
            "--mid-prefill-save-interval",
            "4096",
        ],
    )

    args = parse_args()
    assert args.max_num_batched_tokens == 4096
    assert args.scheduler_policy == "priority"
    assert args.prefill_step_size == 1024
    assert args.disable_prefix_cache is True
    assert args.prefix_cache_size == 42
    assert args.chunked_prefill_tokens == 2048
    assert args.mid_prefill_save_interval == 4096


def test_run_passes_new_scheduler_settings_to_vllm_mlx():
    from vllmlx.backend.worker import run

    captured: dict[str, object] = {}

    class SchedulingPolicy(Enum):
        FCFS = "fcfs"
        PRIORITY = "priority"

    class SchedulerConfig:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    def load_model(
        model, use_batching=False, scheduler_config=None, stream_interval=1, max_tokens=0
    ):
        captured["model"] = model
        captured["use_batching"] = use_batching
        captured["scheduler_config"] = scheduler_config
        captured["stream_interval"] = stream_interval
        captured["max_tokens"] = max_tokens

    fake_server_module = SimpleNamespace(
        _api_key=None,
        _default_timeout=None,
        _rate_limiter=None,
        _default_temperature=None,
        _default_top_p=None,
        _reasoning_parser=None,
        RateLimiter=lambda **kwargs: kwargs,
        app=object(),
        load_model=load_model,
        load_embedding_model=lambda *args, **kwargs: None,
    )
    fake_scheduler_module = SimpleNamespace(
        SchedulerConfig=SchedulerConfig,
        SchedulingPolicy=SchedulingPolicy,
    )
    fake_pkg = SimpleNamespace(server=fake_server_module)

    args = argparse.Namespace(
        model="mlx-community/Qwen3-4B-4bit",
        host="127.0.0.1",
        port=11435,
        max_tokens=16384,
        stream_interval=2,
        continuous_batching=True,
        max_num_seqs=64,
        max_num_batched_tokens=4096,
        scheduler_policy="priority",
        prefill_batch_size=4,
        completion_batch_size=8,
        prefill_step_size=1024,
        enable_prefix_cache=True,
        disable_prefix_cache=True,
        prefix_cache_size=55,
        cache_memory_mb=1024,
        cache_memory_percent=0.15,
        no_memory_aware_cache=False,
        use_paged_cache=True,
        paged_cache_block_size=128,
        max_cache_blocks=500,
        chunked_prefill_tokens=2048,
        mid_prefill_save_interval=4096,
        api_key=None,
        rate_limit=0,
        timeout=300.0,
        reasoning_parser=None,
        default_temperature=None,
        default_top_p=None,
        embedding_model=None,
        log_level="warning",
    )

    with (
        patch("vllmlx.backend.worker.parse_args", return_value=args),
        patch("vllmlx.backend.worker.uvicorn.run"),
        patch.dict(
            sys.modules,
            {
                "vllm_mlx": fake_pkg,
                "vllm_mlx.server": fake_server_module,
                "vllm_mlx.scheduler": fake_scheduler_module,
            },
        ),
    ):
        run()

    assert captured["model"] == "mlx-community/Qwen3-4B-4bit"
    assert captured["use_batching"] is True
    assert captured["stream_interval"] == 2
    assert captured["max_tokens"] == 16384

    scheduler_config = captured["scheduler_config"]
    assert scheduler_config is not None
    kwargs = scheduler_config.kwargs
    assert kwargs["max_num_batched_tokens"] == 4096
    assert kwargs["policy"] is SchedulingPolicy.PRIORITY
    assert kwargs["prefill_step_size"] == 1024
    assert kwargs["enable_prefix_cache"] is False
    assert kwargs["prefix_cache_size"] == 55
    assert kwargs["chunked_prefill_tokens"] == 2048
    assert kwargs["mid_prefill_save_interval"] == 4096
