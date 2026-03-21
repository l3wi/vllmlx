"""Tests for daemon state module."""

import asyncio
from datetime import datetime

import pytest

from vllmlx.config import Config
from vllmlx.daemon.state import DaemonState, get_state, init_state


class _DummySupervisor:
    def __init__(self):
        self.active_model = None
        self.running = False
        self.stop_calls = 0

    def is_running(self) -> bool:
        return self.running

    async def stop(self) -> None:
        self.running = False
        self.active_model = None
        self.stop_calls += 1


class TestDaemonState:
    """Tests for DaemonState class."""

    def test_default_state(self):
        supervisor = _DummySupervisor()
        state = DaemonState(config=Config(), supervisor=supervisor)

        assert state.loaded_model_name is None
        assert state.last_request_at is None
        assert state.start_time is not None
        assert isinstance(state.lock, asyncio.Lock)

    def test_touch_updates_last_request_at(self):
        state = DaemonState(config=Config(), supervisor=_DummySupervisor())
        assert state.last_request_at is None
        before = datetime.now()
        state.touch()
        after = datetime.now()
        assert state.last_request_at is not None
        assert before <= state.last_request_at <= after

    @pytest.mark.asyncio
    async def test_unload_on_idle_stops_supervisor(self):
        supervisor = _DummySupervisor()
        supervisor.running = True
        supervisor.active_model = "mlx-community/Test-4bit"

        state = DaemonState(config=Config(), supervisor=supervisor)
        await state._unload_on_idle()

        assert supervisor.stop_calls == 1
        assert not supervisor.running


class TestGlobalState:
    """Tests for global state management functions."""

    def test_get_state_raises_before_init(self):
        import vllmlx.daemon.state as state_module

        state_module._state = None
        with pytest.raises(RuntimeError, match="Daemon state not initialized"):
            get_state()

    def test_init_state_creates_state(self):
        import vllmlx.daemon.state as state_module

        state_module._state = None
        state = init_state()
        assert isinstance(state, DaemonState)

    def test_get_state_returns_same_instance(self):
        import vllmlx.daemon.state as state_module

        state_module._state = None
        state1 = init_state()
        state2 = get_state()
        assert state1 is state2


class TestIdleTracking:
    """Tests for idle tracking controls."""

    @pytest.mark.asyncio
    async def test_start_and_stop_idle_tracking(self):
        state = DaemonState(config=Config(), supervisor=_DummySupervisor())
        state.start_idle_tracking(1)
        try:
            assert state.idle_timer is not None
            assert state.idle_timer.timeout_seconds == 1
        finally:
            state.stop_idle_tracking()

        assert state.idle_timer is None
