"""Integration tests for daemon idle timeout behavior."""

from __future__ import annotations

import asyncio

import pytest

from vllmlx.config import Config
from vllmlx.daemon.state import DaemonState


class _FakeSupervisor:
    def __init__(self):
        self.running = False
        self.active_model: str | None = None
        self.stop_calls = 0
        self.backend_url = "http://127.0.0.1:8001"

    def is_running(self) -> bool:
        return self.running

    async def is_healthy(self) -> bool:
        return self.running

    async def ensure_model(self, model: str) -> None:
        self.active_model = model
        self.running = True

    async def start(self, model: str) -> None:
        self.active_model = model
        self.running = True

    async def stop(self) -> None:
        self.running = False
        self.active_model = None
        self.stop_calls += 1

    async def shutdown(self) -> None:
        self.running = False


@pytest.mark.asyncio
async def test_idle_timeout_stops_backend_worker():
    supervisor = _FakeSupervisor()
    supervisor.running = True
    supervisor.active_model = "mlx-community/Qwen3-VL-4B-Instruct-3bit"

    state = DaemonState(config=Config(), primary_supervisor=supervisor)
    state.start_idle_tracking(timeout=1)

    try:
        await asyncio.sleep(1.4)
    finally:
        state.stop_idle_tracking()

    assert supervisor.stop_calls == 1
    assert not supervisor.running


@pytest.mark.asyncio
async def test_idle_touch_prevents_unload_until_inactive():
    supervisor = _FakeSupervisor()
    supervisor.running = True
    supervisor.active_model = "mlx-community/Qwen3-VL-4B-Instruct-3bit"

    state = DaemonState(config=Config(), primary_supervisor=supervisor)
    state.start_idle_tracking(timeout=1)

    try:
        # Keep activity alive for longer than timeout.
        for _ in range(3):
            await asyncio.sleep(0.4)
            state.touch()

        assert supervisor.stop_calls == 0

        # Then go idle and ensure unload happens.
        await asyncio.sleep(1.3)
    finally:
        state.stop_idle_tracking()

    assert supervisor.stop_calls == 1
