"""Internal worker entrypoint that runs a configured vllm-mlx server."""

from __future__ import annotations

import argparse
import logging

import uvicorn

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse worker arguments."""
    parser = argparse.ArgumentParser(description="vllmlx internal backend worker")
    parser.add_argument("--model", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=11435)
    parser.add_argument("--max-tokens", type=int, default=32768)
    parser.add_argument("--stream-interval", type=int, default=1)
    parser.add_argument("--continuous-batching", action="store_true")
    parser.add_argument("--max-num-seqs", type=int, default=256)
    parser.add_argument("--max-num-batched-tokens", type=int, default=8192)
    parser.add_argument(
        "--scheduler-policy",
        choices=["fcfs", "priority"],
        default="fcfs",
    )
    parser.add_argument("--prefill-batch-size", type=int, default=8)
    parser.add_argument("--completion-batch-size", type=int, default=32)
    parser.add_argument("--prefill-step-size", type=int, default=2048)
    parser.add_argument("--enable-prefix-cache", action="store_true", default=True)
    parser.add_argument("--disable-prefix-cache", action="store_true")
    parser.add_argument("--prefix-cache-size", type=int, default=100)
    parser.add_argument("--cache-memory-mb", type=int, default=None)
    parser.add_argument("--cache-memory-percent", type=float, default=0.20)
    parser.add_argument("--no-memory-aware-cache", action="store_true")
    parser.add_argument("--use-paged-cache", action="store_true")
    parser.add_argument("--paged-cache-block-size", type=int, default=64)
    parser.add_argument("--max-cache-blocks", type=int, default=1000)
    parser.add_argument("--chunked-prefill-tokens", type=int, default=0)
    parser.add_argument("--mid-prefill-save-interval", type=int, default=8192)
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--rate-limit", type=int, default=0)
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--reasoning-parser", default=None)
    parser.add_argument("--default-temperature", type=float, default=None)
    parser.add_argument("--default-top-p", type=float, default=None)
    parser.add_argument("--embedding-model", default=None)
    parser.add_argument("--log-level", default="info")
    return parser.parse_args()


def run() -> None:
    """Run backend worker."""
    args = parse_args()

    from vllm_mlx import server
    from vllm_mlx.scheduler import SchedulerConfig, SchedulingPolicy
    from vllm_mlx.server import RateLimiter, app, load_model

    server._api_key = args.api_key
    server._default_timeout = args.timeout

    if args.rate_limit > 0:
        server._rate_limiter = RateLimiter(
            requests_per_minute=args.rate_limit,
            enabled=True,
        )

    if args.default_temperature is not None:
        server._default_temperature = args.default_temperature

    if args.default_top_p is not None:
        server._default_top_p = args.default_top_p

    if args.reasoning_parser:
        from vllm_mlx.reasoning import get_parser

        parser_cls = get_parser(args.reasoning_parser)
        server._reasoning_parser = parser_cls()

    if args.embedding_model:
        server.load_embedding_model(args.embedding_model, lock=True)

    scheduler_config = None
    if args.continuous_batching:
        enable_prefix_cache = args.enable_prefix_cache and not args.disable_prefix_cache
        scheduler_config = SchedulerConfig(
            max_num_seqs=args.max_num_seqs,
            max_num_batched_tokens=args.max_num_batched_tokens,
            policy=SchedulingPolicy(args.scheduler_policy),
            prefill_batch_size=args.prefill_batch_size,
            completion_batch_size=args.completion_batch_size,
            prefill_step_size=args.prefill_step_size,
            enable_prefix_cache=enable_prefix_cache,
            prefix_cache_size=args.prefix_cache_size,
            use_memory_aware_cache=not args.no_memory_aware_cache,
            cache_memory_mb=args.cache_memory_mb,
            cache_memory_percent=args.cache_memory_percent,
            use_paged_cache=args.use_paged_cache,
            paged_cache_block_size=args.paged_cache_block_size,
            max_cache_blocks=args.max_cache_blocks,
            chunked_prefill_tokens=args.chunked_prefill_tokens,
            mid_prefill_save_interval=args.mid_prefill_save_interval,
        )

    load_model(
        args.model,
        use_batching=args.continuous_batching,
        scheduler_config=scheduler_config,
        stream_interval=args.stream_interval,
        max_tokens=args.max_tokens,
    )

    uvicorn.run(app, host=args.host, port=args.port, log_level=args.log_level)


if __name__ == "__main__":
    run()
