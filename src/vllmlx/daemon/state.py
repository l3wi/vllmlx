"""Daemon state management for vllmlx."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from vllmlx.backend import BackendSupervisor
from vllmlx.config import Config

try:
    import psutil as _psutil
except ImportError:
    _psutil = None

if TYPE_CHECKING:
    from vllmlx.daemon.idle import IdleTimer

logger = logging.getLogger(__name__)

_state: "DaemonState | None" = None


@runtime_checkable
class SupervisorProtocol(Protocol):
    """Runtime contract for backend supervisor implementations."""

    active_model: str | None
    backend_url: str

    def is_running(self) -> bool:
        """Return True when backend worker process is alive."""

    async def is_healthy(self) -> bool:
        """Return True when backend worker API is healthy."""

    async def ensure_model(self, model: str) -> None:
        """Ensure backend worker is running with the requested model."""

    async def start(self, model: str) -> None:
        """Start backend worker for model."""

    async def stop(self) -> None:
        """Stop backend worker process."""

    async def shutdown(self) -> None:
        """Shutdown helper for daemon app lifespan."""


@dataclass
class ModelSlot:
    """Single model slot containing runtime metadata for one worker."""

    supervisor: SupervisorProtocol
    port: int
    last_used_at: datetime
    last_health_checked_at: datetime | None = None
    last_health_ok: bool | None = None


@dataclass
class DaemonState:
    """Mutable state for the running daemon process."""

    config: Config
    primary_supervisor: SupervisorProtocol
    start_time: datetime = field(default_factory=datetime.now)
    last_request_at: datetime | None = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    idle_timer: "IdleTimer | None" = None
    model_slots: dict[str, ModelSlot] = field(default_factory=dict)
    _next_backend_port: int | None = None

    def __post_init__(self) -> None:
        if self.primary_supervisor.is_running() and self.primary_supervisor.active_model:
            self._upsert_slot(
                self.primary_supervisor.active_model,
                self.primary_supervisor,
                used_at=datetime.now(),
            )

    @property
    def loaded_model_name(self) -> str | None:
        """Current active backend model."""
        models = self.list_loaded_models()
        return models[0] if models else None

    def resolve_default_model(self) -> str | None:
        """Resolve configured default model to canonical backend model id."""
        default_model = self.config.models.default.strip()
        if not default_model:
            return None

        from vllmlx.models.aliases import resolve_alias

        return resolve_alias(default_model, self.config.aliases)

    def list_loaded_models(self) -> list[str]:
        """Return loaded models ordered by recency."""
        running_models = [
            model
            for model, slot in self.model_slots.items()
            if slot.supervisor.is_running()
        ]
        return sorted(
            running_models,
            key=lambda model: self.model_slots[model].last_used_at,
            reverse=True,
        )

    def is_running(self) -> bool:
        """Return True when at least one backend worker is active."""
        return any(slot.supervisor.is_running() for slot in self.model_slots.values())

    async def ensure_model_loaded(self, model: str) -> SupervisorProtocol:
        """Ensure a model worker is loaded and return its supervisor."""
        max_models = max(1, self.config.daemon.max_loaded_models)

        if max_models == 1:
            await self.primary_supervisor.ensure_model(model)
            self.model_slots.clear()
            self._upsert_slot(model, self.primary_supervisor, used_at=datetime.now())
            return self.primary_supervisor

        existing = self.model_slots.get(model)
        if existing and await self._slot_is_healthy(existing):
            self.touch_model(model)
            return existing.supervisor

        if existing:
            await self._evict_model(model)

        await self._evict_for_capacity(max_models)
        await self._evict_for_memory_pressure()

        if not self.model_slots:
            supervisor = self.primary_supervisor
            await supervisor.ensure_model(model)
        else:
            port = self._allocate_backend_port()
            supervisor = self._build_supervisor_for_port(port)
            await supervisor.start(model)

        self._upsert_slot(model, supervisor, used_at=datetime.now())
        return supervisor

    async def get_supervisor_for_model(self, model: str) -> SupervisorProtocol | None:
        """Return a healthy supervisor for a loaded model."""
        slot = self.model_slots.get(model)
        if slot and await self._slot_is_healthy(slot):
            return slot.supervisor
        return None

    async def get_supervisor_for_any_loaded_model(self) -> SupervisorProtocol | None:
        """Return a healthy supervisor from current loaded pool."""
        for model in self.list_loaded_models():
            supervisor = await self.get_supervisor_for_model(model)
            if supervisor:
                return supervisor
        return None

    def touch_model(self, model: str) -> None:
        """Record activity for a specific model worker."""
        slot = self.model_slots.get(model)
        if slot:
            slot.last_used_at = datetime.now()
        self.touch()

    async def shutdown(self) -> None:
        """Stop every managed worker and clear runtime state."""
        seen: set[int] = set()
        for slot in list(self.model_slots.values()):
            supervisor = slot.supervisor
            if id(supervisor) in seen:
                continue
            seen.add(id(supervisor))
            await supervisor.shutdown()

        if id(self.primary_supervisor) not in seen:
            await self.primary_supervisor.shutdown()

        self.model_slots.clear()

    def touch(self) -> None:
        """Mark daemon as active and reset idle timer countdown."""
        self.last_request_at = datetime.now()
        if self.idle_timer:
            self.idle_timer.touch()

    def start_idle_tracking(self, timeout: int) -> None:
        """Start idle timeout tracking for backend unload."""
        from vllmlx.daemon.idle import IdleTimer

        if self.idle_timer:
            self.idle_timer.stop()

        self.idle_timer = IdleTimer(
            timeout_seconds=timeout,
            on_timeout=self._unload_on_idle,
            check_interval=max(0.2, min(10.0, timeout / 5)),
        )
        self.idle_timer.start()

    def stop_idle_tracking(self) -> None:
        """Stop idle timeout tracking."""
        if self.idle_timer:
            self.idle_timer.stop()
            self.idle_timer = None

    async def _unload_on_idle(self) -> None:
        """Unload backend workers when idle timeout is reached."""
        async with self.lock:
            if not self.is_running():
                return

            pinned_model = self._pinned_model()
            timeout_seconds = (
                self.idle_timer.timeout_seconds
                if self.idle_timer is not None
                else self.config.daemon.idle_timeout
            )
            now = datetime.now()
            unloaded: list[str] = []

            for model, slot in list(self.model_slots.items()):
                if model == pinned_model:
                    continue
                if not slot.supervisor.is_running():
                    self._remove_slot(model)
                    continue
                if (now - slot.last_used_at).total_seconds() < timeout_seconds:
                    continue
                await self._evict_model(model)
                unloaded.append(model)

            if unloaded:
                logger.info("Unloaded idle backend models: %s", ", ".join(unloaded))
            elif pinned_model and pinned_model in self.model_slots:
                logger.info(
                    "Idle timeout reached but keeping pinned default model loaded: '%s'",
                    pinned_model,
                )
                self.touch_model(pinned_model)

    def _pinned_model(self) -> str | None:
        if self.config.daemon.pin_default_model:
            return self.resolve_default_model()
        return None

    async def _evict_for_capacity(self, max_models: int) -> None:
        while len(self.model_slots) >= max_models:
            model = self._oldest_evictable_model()
            if model is None:
                break
            await self._evict_model(model)

    async def _evict_for_memory_pressure(self) -> None:
        while self.model_slots and not self._has_memory_headroom():
            model = self._oldest_evictable_model()
            if model is None:
                break
            await self._evict_model(model)
            logger.info(
                "Evicted stale model '%s' due to low memory headroom",
                model,
            )

    def _oldest_evictable_model(self) -> str | None:
        pinned_model = self._pinned_model()
        candidates = [
            model for model in self.model_slots.keys() if model != pinned_model
        ]
        if not candidates:
            return None
        return min(
            candidates,
            key=lambda model: self.model_slots[model].last_used_at,
        )

    async def _evict_model(self, model: str) -> None:
        slot = self._remove_slot(model)
        if slot:
            await slot.supervisor.stop()

    def _build_supervisor_for_port(self, port: int) -> SupervisorProtocol:
        config = self.config.model_copy(deep=True)
        config.backend.port = port
        return BackendSupervisor(config)

    def _allocate_backend_port(self) -> int:
        used_ports = {slot.port for slot in self.model_slots.values()}
        if self._next_backend_port is None:
            self._next_backend_port = self.config.backend.port + 1

        port = self._next_backend_port
        while port in used_ports:
            port += 1
        self._next_backend_port = port + 1
        return port

    @staticmethod
    def _backend_port(supervisor: SupervisorProtocol) -> int:
        try:
            return int(supervisor.backend_url.rsplit(":", 1)[1])
        except Exception:
            return 11435

    def _upsert_slot(
        self,
        model: str,
        supervisor: SupervisorProtocol,
        *,
        used_at: datetime,
    ) -> ModelSlot:
        slot = ModelSlot(
            supervisor=supervisor,
            port=self._backend_port(supervisor),
            last_used_at=used_at,
        )
        self.model_slots[model] = slot
        return slot

    def _remove_slot(self, model: str) -> ModelSlot | None:
        return self.model_slots.pop(model, None)

    async def _slot_is_healthy(self, slot: ModelSlot) -> bool:
        if not slot.supervisor.is_running():
            slot.last_health_checked_at = datetime.now()
            slot.last_health_ok = False
            return False

        ttl_seconds = self.config.daemon.health_ttl_seconds
        now = datetime.now()

        if (
            ttl_seconds > 0
            and slot.last_health_checked_at is not None
            and slot.last_health_ok is not None
            and (now - slot.last_health_checked_at).total_seconds() <= ttl_seconds
        ):
            return slot.last_health_ok

        try:
            healthy = await slot.supervisor.is_healthy()
        except Exception:
            healthy = False

        slot.last_health_checked_at = now
        slot.last_health_ok = healthy
        return healthy

    def _has_memory_headroom(self) -> bool:
        reserve_gb = max(0.0, self.config.daemon.min_available_memory_gb)
        if reserve_gb <= 0 or _psutil is None:
            return True

        try:
            available_gb = _psutil.virtual_memory().available / (1024**3)
            return available_gb >= reserve_gb
        except Exception:
            return True



def init_state() -> DaemonState:
    """Initialize global daemon state."""
    global _state
    config = Config.load()
    state = DaemonState(config=config, primary_supervisor=BackendSupervisor(config))
    try:
        asyncio.get_running_loop()
        state.start_idle_tracking(config.daemon.idle_timeout)
    except RuntimeError:
        # Unit tests may initialize state outside an active event loop.
        pass
    _state = state
    return state



def get_state() -> DaemonState:
    """Get global daemon state."""
    if _state is None:
        raise RuntimeError("Daemon state not initialized. Call init_state() first.")
    return _state
