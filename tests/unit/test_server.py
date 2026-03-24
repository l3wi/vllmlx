"""Tests for daemon server lifespan behaviors."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest
from fastapi import FastAPI

from vllmlx.config import Config
from vllmlx.daemon.server import lifespan


class _FakeSupervisor:
    def __init__(self):
        self.ensure_calls: list[str] = []
        self.shutdown_calls = 0

    async def ensure_model(self, model: str) -> None:
        self.ensure_calls.append(model)

    async def shutdown(self) -> None:
        self.shutdown_calls += 1


class _FakeState:
    def __init__(self, config: Config):
        self.config = config
        self.primary_supervisor = _FakeSupervisor()
        self.lock = asyncio.Lock()
        self.touch_calls = 0
        self.stop_idle_tracking_calls = 0
        self.shutdown_calls = 0

    def resolve_default_model(self) -> str | None:
        return "mlx-community/Qwen3-4B-4bit"

    async def ensure_model_loaded(self, model: str) -> None:
        await self.primary_supervisor.ensure_model(model)

    def touch_model(self, model: str) -> None:
        self.touch_calls += 1

    def touch(self) -> None:
        self.touch_calls += 1

    def stop_idle_tracking(self) -> None:
        self.stop_idle_tracking_calls += 1

    async def shutdown(self) -> None:
        self.shutdown_calls += 1


@pytest.mark.asyncio
async def test_lifespan_preloads_default_model_when_enabled():
    config = Config(
        daemon={"preload_default_model": True},
        models={"default": "qwen3-4b-4bit"},
    )
    state = _FakeState(config)

    with (
        patch("vllmlx.daemon.server.init_state", return_value=state),
        patch("vllmlx.daemon.server.get_state", return_value=state),
    ):
        async with lifespan(FastAPI()):
            pass

    assert state.primary_supervisor.ensure_calls == ["mlx-community/Qwen3-4B-4bit"]
    assert state.touch_calls == 1
    assert state.stop_idle_tracking_calls == 1
    assert state.shutdown_calls == 1


@pytest.mark.asyncio
async def test_lifespan_skips_preload_when_disabled():
    config = Config(
        daemon={"preload_default_model": False, "pin_default_model": False},
        models={"default": "qwen3-4b-4bit"},
    )
    state = _FakeState(config)

    with (
        patch("vllmlx.daemon.server.init_state", return_value=state),
        patch("vllmlx.daemon.server.get_state", return_value=state),
    ):
        async with lifespan(FastAPI()):
            pass

    assert state.primary_supervisor.ensure_calls == []
    assert state.stop_idle_tracking_calls == 1
    assert state.shutdown_calls == 1
