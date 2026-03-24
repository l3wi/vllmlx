"""Tests for daemon state module."""

import asyncio
from datetime import datetime, timedelta

import pytest

from vllmlx.config import Config
from vllmlx.daemon.state import DaemonState, ModelSlot, get_state, init_state


class _DummySupervisor:
    def __init__(self, port: int = 11435):
        self.active_model: str | None = None
        self.running = False
        self.healthy = True
        self.stop_calls = 0
        self.ensure_calls: list[str] = []
        self.start_calls: list[str] = []
        self.shutdown_calls = 0
        self.health_calls = 0
        self.backend_url = f"http://127.0.0.1:{port}"

    def is_running(self) -> bool:
        return self.running

    async def is_healthy(self) -> bool:
        self.health_calls += 1
        return self.running and self.healthy

    async def ensure_model(self, model: str) -> None:
        self.ensure_calls.append(model)
        self.active_model = model
        self.running = True

    async def start(self, model: str) -> None:
        self.start_calls.append(model)
        self.active_model = model
        self.running = True

    async def stop(self) -> None:
        self.running = False
        self.active_model = None
        self.stop_calls += 1

    async def shutdown(self) -> None:
        self.running = False
        self.shutdown_calls += 1


class TestDaemonState:
    """Tests for DaemonState class."""

    def test_default_state(self):
        supervisor = _DummySupervisor()
        state = DaemonState(config=Config(), primary_supervisor=supervisor)

        assert state.loaded_model_name is None
        assert state.last_request_at is None
        assert state.start_time is not None
        assert isinstance(state.lock, asyncio.Lock)
        assert state.model_slots == {}

    def test_touch_updates_last_request_at(self):
        state = DaemonState(config=Config(), primary_supervisor=_DummySupervisor())
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

        state = DaemonState(config=Config(), primary_supervisor=supervisor)
        state.model_slots["mlx-community/Test-4bit"].last_used_at = datetime.now() - timedelta(
            seconds=601
        )
        await state._unload_on_idle()

        assert supervisor.stop_calls == 1
        assert not supervisor.running
        assert state.list_loaded_models() == []

    def test_resolve_default_model(self):
        state = DaemonState(
            config=Config(models={"default": "qwen3:4b"}),
            primary_supervisor=_DummySupervisor(),
        )
        assert state.resolve_default_model() == "mlx-community/Qwen3-4B-4bit"

    @pytest.mark.asyncio
    async def test_unload_on_idle_keeps_pinned_default_model(self):
        supervisor = _DummySupervisor()
        supervisor.running = True
        supervisor.active_model = "mlx-community/Qwen3-4B-4bit"

        state = DaemonState(
            config=Config(
                daemon={"pin_default_model": True},
                models={"default": "qwen3:4b"},
            ),
            primary_supervisor=supervisor,
        )
        await state._unload_on_idle()

        assert supervisor.stop_calls == 0
        assert supervisor.running
        assert state.list_loaded_models() == ["mlx-community/Qwen3-4B-4bit"]

    @pytest.mark.asyncio
    async def test_unload_on_idle_unloads_stale_models_from_pool(self):
        primary = _DummySupervisor(port=11435)
        primary.running = True
        primary.active_model = "mlx-community/Qwen3-8B-4bit"

        stale = _DummySupervisor(port=11436)
        stale.running = True
        stale.active_model = "mlx-community/Qwen2-VL-2B-Instruct-4bit"

        state = DaemonState(
            config=Config(daemon={"idle_timeout": 1}),
            primary_supervisor=primary,
        )
        state.model_slots[stale.active_model] = ModelSlot(
            supervisor=stale,
            port=11436,
            last_used_at=datetime.now().replace(year=2000),
        )

        await state._unload_on_idle()

        assert stale.stop_calls == 1
        assert stale.active_model not in state.model_slots
        assert primary.active_model in state.model_slots

    def test_oldest_evictable_model_skips_pinned_default(self):
        state = DaemonState(
            config=Config(
                daemon={"pin_default_model": True},
                models={"default": "qwen3:8b"},
            ),
            primary_supervisor=_DummySupervisor(),
        )
        state.model_slots = {
            "mlx-community/Qwen3-8B-4bit": ModelSlot(
                supervisor=_DummySupervisor(port=11435),
                port=11435,
                last_used_at=datetime.now().replace(year=2000),
            ),
            "mlx-community/Qwen3-Embedding-4B-4bit-DWQ": ModelSlot(
                supervisor=_DummySupervisor(port=11436),
                port=11436,
                last_used_at=datetime.now().replace(year=2001),
            ),
        }

        oldest = state._oldest_evictable_model()
        assert oldest == "mlx-community/Qwen3-Embedding-4B-4bit-DWQ"

    @pytest.mark.asyncio
    async def test_loaded_models_and_supervisor_lookup_agree(self):
        supervisor = _DummySupervisor()
        supervisor.running = True
        supervisor.active_model = "mlx-community/Qwen3-4B-4bit"

        state = DaemonState(config=Config(), primary_supervisor=supervisor)

        assert state.list_loaded_models() == ["mlx-community/Qwen3-4B-4bit"]
        resolved = await state.get_supervisor_for_any_loaded_model()
        assert resolved is supervisor

    @pytest.mark.asyncio
    async def test_health_ttl_caches_probe_within_ttl(self):
        supervisor = _DummySupervisor()
        supervisor.running = True
        supervisor.active_model = "mlx-community/Qwen3-4B-4bit"

        state = DaemonState(
            config=Config(daemon={"health_ttl_seconds": 30.0}),
            primary_supervisor=supervisor,
        )

        assert await state.get_supervisor_for_model("mlx-community/Qwen3-4B-4bit") is supervisor
        assert await state.get_supervisor_for_model("mlx-community/Qwen3-4B-4bit") is supervisor
        assert supervisor.health_calls == 1

    @pytest.mark.asyncio
    async def test_health_ttl_reprobes_after_expiry(self):
        supervisor = _DummySupervisor()
        supervisor.running = True
        supervisor.active_model = "mlx-community/Qwen3-4B-4bit"

        state = DaemonState(
            config=Config(daemon={"health_ttl_seconds": 0.1}),
            primary_supervisor=supervisor,
        )

        model_name = "mlx-community/Qwen3-4B-4bit"
        assert await state.get_supervisor_for_model(model_name) is supervisor

        state.model_slots[model_name].last_health_checked_at = datetime.now() - timedelta(seconds=2)
        assert await state.get_supervisor_for_model(model_name) is supervisor
        assert supervisor.health_calls == 2

    @pytest.mark.asyncio
    async def test_unhealthy_existing_slot_is_replaced_and_metadata_stays_consistent(self):
        target_model = "mlx-community/Qwen3-8B-4bit"

        primary = _DummySupervisor(port=11435)
        stale = _DummySupervisor(port=11436)
        stale.running = True
        stale.active_model = target_model
        stale.healthy = False

        state = DaemonState(
            config=Config(daemon={"max_loaded_models": 3}),
            primary_supervisor=primary,
        )
        state.model_slots[target_model] = ModelSlot(
            supervisor=stale,
            port=11436,
            last_used_at=datetime.now() - timedelta(days=1),
        )

        supervisor = await state.ensure_model_loaded(target_model)

        assert supervisor is primary
        assert stale.stop_calls == 1
        assert primary.ensure_calls == [target_model]
        assert set(state.model_slots.keys()) == {target_model}
        assert state.model_slots[target_model].supervisor is primary
        assert state.model_slots[target_model].port == 11435


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
        state = DaemonState(config=Config(), primary_supervisor=_DummySupervisor())
        state.start_idle_tracking(1)
        try:
            assert state.idle_timer is not None
            assert state.idle_timer.timeout_seconds == 1
        finally:
            state.stop_idle_tracking()

        assert state.idle_timer is None


class TestHttpClientPool:
    def test_get_http_client_reuses_per_base_url(self, monkeypatch):
        created: list[object] = []

        class FakeAsyncClient:
            def __init__(self, *args, **kwargs):
                self.closed = False
                self.is_closed = False
                created.append(self)

            async def aclose(self):
                self.closed = True
                self.is_closed = True

        monkeypatch.setattr("vllmlx.daemon.state.httpx.AsyncClient", FakeAsyncClient)

        state = DaemonState(config=Config(), primary_supervisor=_DummySupervisor())
        first = state.get_http_client("http://127.0.0.1:11435")
        second = state.get_http_client("http://127.0.0.1:11435")

        assert first is second
        assert len(created) == 1

    @pytest.mark.asyncio
    async def test_shutdown_closes_http_clients(self, monkeypatch):
        created: list[object] = []

        class FakeAsyncClient:
            def __init__(self, *args, **kwargs):
                self.closed = False
                self.is_closed = False
                created.append(self)

            async def aclose(self):
                self.closed = True
                self.is_closed = True

        monkeypatch.setattr("vllmlx.daemon.state.httpx.AsyncClient", FakeAsyncClient)

        state = DaemonState(config=Config(), primary_supervisor=_DummySupervisor())
        state.get_http_client("http://127.0.0.1:11435")
        state.get_http_client("http://127.0.0.1:11436")

        await state.shutdown()

        assert len(created) == 2
        assert all(client.closed for client in created)
        assert state._http_clients == {}
