"""Process supervisor for the internal vllm-mlx backend server."""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import sys
import time
from collections import deque
from pathlib import Path

import httpx

from vllmlx.config import Config, get_runtime_home, get_state_dir

logger = logging.getLogger(__name__)


class BackendStartupError(RuntimeError):
    """Raised when the managed backend fails to start."""


class BackendSupervisor:
    """Manages the lifecycle of an internal vllm-mlx worker process."""

    def __init__(self, config: Config):
        self._config = config
        self._process: subprocess.Popen[str] | None = None
        self._active_model: str | None = None
        self._stdout_file = None
        self._stderr_file = None

    @property
    def backend_url(self) -> str:
        return f"http://{self._config.backend.host}:{self._config.backend.port}"

    @property
    def active_model(self) -> str | None:
        return self._active_model

    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    async def ensure_model(self, model: str) -> None:
        """Ensure backend is running for the requested model."""
        if self.is_running() and self._active_model == model and await self.is_healthy():
            return

        await self.stop()
        await self.start(model)

    async def start(self, model: str) -> None:
        """Start worker process for a model and wait for readiness."""
        log_dir = get_state_dir() / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        stdout_file = open(log_dir / "backend.log", "a", encoding="utf-8")
        stderr_file = open(log_dir / "backend.error.log", "a", encoding="utf-8")
        self._stdout_file = stdout_file
        self._stderr_file = stderr_file

        cmd = [
            sys.executable,
            "-m",
            "vllmlx.backend.worker",
            "--model",
            model,
            "--host",
            self._config.backend.host,
            "--port",
            str(self._config.backend.port),
            "--max-tokens",
            str(self._config.backend.max_tokens),
            "--stream-interval",
            str(self._config.backend.stream_interval),
        ]

        if self._config.backend.continuous_batching:
            cmd.append("--continuous-batching")
            cmd.extend(["--max-num-seqs", str(self._config.backend.max_num_seqs)])
            cmd.extend(
                ["--max-num-batched-tokens", str(self._config.backend.max_num_batched_tokens)]
            )
            cmd.extend(["--scheduler-policy", self._config.backend.scheduler_policy])
            cmd.extend(["--prefill-batch-size", str(self._config.backend.prefill_batch_size)])
            cmd.extend(["--completion-batch-size", str(self._config.backend.completion_batch_size)])
            cmd.extend(["--prefill-step-size", str(self._config.backend.prefill_step_size)])
            if not self._config.backend.enable_prefix_cache:
                cmd.append("--disable-prefix-cache")
            cmd.extend(["--prefix-cache-size", str(self._config.backend.prefix_cache_size)])
            cmd.extend(
                ["--chunked-prefill-tokens", str(self._config.backend.chunked_prefill_tokens)]
            )
            cmd.extend(
                [
                    "--mid-prefill-save-interval",
                    str(self._config.backend.mid_prefill_save_interval),
                ]
            )

        if self._config.backend.cache_memory_mb is not None:
            cmd.extend(["--cache-memory-mb", str(self._config.backend.cache_memory_mb)])
        else:
            cmd.extend(
                [
                    "--cache-memory-percent",
                    str(self._config.backend.cache_memory_percent),
                ]
            )

        if self._config.backend.no_memory_aware_cache:
            cmd.append("--no-memory-aware-cache")

        if self._config.backend.use_paged_cache:
            cmd.append("--use-paged-cache")
            cmd.extend(
                ["--paged-cache-block-size", str(self._config.backend.paged_cache_block_size)]
            )
            cmd.extend(["--max-cache-blocks", str(self._config.backend.max_cache_blocks)])

        if self._config.backend.api_key:
            cmd.extend(["--api-key", self._config.backend.api_key])

        if self._config.backend.rate_limit > 0:
            cmd.extend(["--rate-limit", str(self._config.backend.rate_limit)])

        cmd.extend(["--timeout", str(self._config.backend.timeout)])

        if self._config.backend.reasoning_parser:
            cmd.extend(["--reasoning-parser", self._config.backend.reasoning_parser])

        if self._config.backend.default_temperature is not None:
            cmd.extend(["--default-temperature", str(self._config.backend.default_temperature)])

        if self._config.backend.default_top_p is not None:
            cmd.extend(["--default-top-p", str(self._config.backend.default_top_p)])

        if self._config.backend.embedding_model:
            cmd.extend(["--embedding-model", self._config.backend.embedding_model])

        env = os.environ.copy()
        if self._config.backend.mcp_config:
            env["VLLM_MLX_MCP_CONFIG"] = self._config.backend.mcp_config

        logger.info("Starting backend worker for model '%s'", model)
        self._process = subprocess.Popen(  # noqa: S603
            cmd,
            stdout=stdout_file,
            stderr=stderr_file,
            text=True,
            cwd=str(get_runtime_home()),
            env=env,
        )

        try:
            await self._wait_until_ready(timeout_seconds=self._config.backend.startup_timeout)
        except Exception as exc:
            await self.stop()
            raise BackendStartupError(
                f"Backend failed to start for model '{model}': {exc}"
            ) from exc

        self._active_model = model

    async def stop(self) -> None:
        """Stop worker process if running."""
        process = self._process
        self._process = None
        self._active_model = None

        def _close_logs() -> None:
            if self._stdout_file:
                self._stdout_file.close()
                self._stdout_file = None
            if self._stderr_file:
                self._stderr_file.close()
                self._stderr_file = None

        if process is None:
            _close_logs()
            return

        if process.poll() is not None:
            _close_logs()
            return

        logger.info("Stopping backend worker (pid=%s)", process.pid)

        process.terminate()
        deadline = time.monotonic() + self._config.backend.stop_timeout
        while process.poll() is None and time.monotonic() < deadline:
            await asyncio.sleep(0.1)

        if process.poll() is None:
            logger.warning("Backend worker did not stop gracefully; killing it")
            process.kill()

        _close_logs()

    async def is_healthy(self) -> bool:
        """Check backend health endpoint."""
        if not self.is_running():
            return False

        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(f"{self.backend_url}/health")
                return response.status_code == 200
        except Exception:
            return False

    async def _wait_until_ready(self, timeout_seconds: int) -> None:
        """Wait for backend to return healthy state."""
        deadline = time.monotonic() + timeout_seconds

        while time.monotonic() < deadline:
            if self._process is None:
                raise BackendStartupError("backend process missing during startup")

            if self._process.poll() is not None:
                recent_error = self._read_recent_backend_error()
                if recent_error:
                    raise BackendStartupError(
                        f"backend process exited during startup: {recent_error}"
                    )
                raise BackendStartupError("backend process exited during startup")

            if await self.is_healthy():
                return

            await asyncio.sleep(0.2)

        raise BackendStartupError("backend readiness timeout")

    def _read_recent_backend_error(self, max_lines: int = 60) -> str | None:
        """Read recent stderr lines from backend log for startup diagnostics."""
        if self._stderr_file is None:
            return None

        log_path = Path(getattr(self._stderr_file, "name", ""))
        if not log_path.exists():
            return None

        try:
            with log_path.open("r", encoding="utf-8", errors="ignore") as handle:
                lines = [line.rstrip() for line in deque(handle, maxlen=max_lines)]
        except OSError:
            return None

        non_empty = [line for line in lines if line.strip()]
        if not non_empty:
            return None

        markers = (
            "Traceback",
            "Error",
            "Exception",
            "ValueError",
            "ModuleNotFoundError",
            "RuntimeError",
        )
        marker_indices = [
            idx for idx, line in enumerate(non_empty) if any(token in line for token in markers)
        ]
        start = marker_indices[-1] if marker_indices else max(0, len(non_empty) - 8)
        excerpt = non_empty[start : start + 8]

        summary = " | ".join(excerpt)
        if len(summary) > 1000:
            summary = summary[-1000:]
        return summary

    async def shutdown(self) -> None:
        """Public shutdown helper for app lifespan."""
        await self.stop()
