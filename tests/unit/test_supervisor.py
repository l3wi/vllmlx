"""Tests for backend supervisor diagnostics."""

from __future__ import annotations

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
