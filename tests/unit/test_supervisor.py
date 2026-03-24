"""Tests for backend supervisor diagnostics."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from vllmlx.backend.supervisor import BackendStartupError, BackendSupervisor
from vllmlx.config import Config


class _FakeExitedProcess:
    def poll(self) -> int:
        return 1


class _FakeFile:
    def __init__(self, name: str):
        self.name = name


class _FakeStartedProcess:
    pid = 4242

    def poll(self) -> int | None:
        return 0


def test_read_recent_backend_error_extracts_relevant_tail(tmp_path: Path):
    log_file = tmp_path / "backend.error.log"
    log_file.write_text(
        "\n".join(
            [
                "INFO start",
                "INFO loading",
                "Traceback (most recent call last):",
                "ModuleNotFoundError: No module named 'mlx_vlm.models.qwen3_vl'",
                "ValueError: Model type qwen3_vl not supported.",
            ]
        ),
        encoding="utf-8",
    )

    supervisor = BackendSupervisor(Config())
    supervisor._stderr_file = _FakeFile(str(log_file))

    message = supervisor._read_recent_backend_error()

    assert message is not None
    assert "qwen3_vl" in message
    assert "Model type qwen3_vl not supported" in message


@pytest.mark.asyncio
async def test_wait_until_ready_includes_recent_stderr_on_early_exit(tmp_path: Path):
    log_file = tmp_path / "backend.error.log"
    log_file.write_text(
        "ValueError: Model type qwen3_vl not supported.\n",
        encoding="utf-8",
    )

    supervisor = BackendSupervisor(Config())
    supervisor._process = _FakeExitedProcess()
    supervisor._stderr_file = _FakeFile(str(log_file))

    with pytest.raises(BackendStartupError, match="qwen3_vl"):
        await supervisor._wait_until_ready(timeout_seconds=1)


@pytest.mark.asyncio
async def test_start_forwards_new_scheduler_settings(monkeypatch, tmp_path: Path):
    config = Config(
        backend={
            "continuous_batching": True,
            "max_num_seqs": 32,
            "max_num_batched_tokens": 4096,
            "scheduler_policy": "priority",
            "prefill_batch_size": 4,
            "completion_batch_size": 8,
            "prefill_step_size": 1024,
            "enable_prefix_cache": False,
            "prefix_cache_size": 77,
            "chunked_prefill_tokens": 2048,
            "mid_prefill_save_interval": 4096,
        }
    )
    supervisor = BackendSupervisor(config)
    captured: dict[str, list[str]] = {}

    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    def fake_popen(cmd, **kwargs):  # noqa: ANN001
        captured["cmd"] = cmd
        return _FakeStartedProcess()

    async def fake_wait(self, timeout_seconds: int) -> None:  # noqa: ARG001
        return None

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    monkeypatch.setattr(BackendSupervisor, "_wait_until_ready", fake_wait)

    await supervisor.start("mlx-community/Qwen3-4B-4bit")

    cmd = captured["cmd"]
    assert "--max-num-batched-tokens" in cmd
    assert "--scheduler-policy" in cmd
    assert "--prefill-step-size" in cmd
    assert "--disable-prefix-cache" in cmd
    assert "--prefix-cache-size" in cmd
    assert "--chunked-prefill-tokens" in cmd
    assert "--mid-prefill-save-interval" in cmd
    assert cmd[cmd.index("--max-num-batched-tokens") + 1] == "4096"
    assert cmd[cmd.index("--scheduler-policy") + 1] == "priority"
    assert cmd[cmd.index("--prefill-step-size") + 1] == "1024"
    assert cmd[cmd.index("--chunked-prefill-tokens") + 1] == "2048"
    assert cmd[cmd.index("--mid-prefill-save-interval") + 1] == "4096"

    await supervisor.stop()


@pytest.mark.asyncio
async def test_start_rejects_backend_port_collision(tmp_path: Path):
    config = Config(
        daemon={"port": 8000},
        backend={"port": 8000},
    )
    supervisor = BackendSupervisor(config)

    with pytest.raises(BackendStartupError, match="backend.port must differ from daemon.port"):
        await supervisor.start("mlx-community/Qwen3-4B-4bit")
