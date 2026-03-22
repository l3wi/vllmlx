"""Daemon state management for vllmlx."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

from vllmlx.backend import BackendSupervisor
from vllmlx.config import Config

if TYPE_CHECKING:
    from vllmlx.daemon.idle import IdleTimer

logger = logging.getLogger(__name__)

_state: "DaemonState | None" = None


@dataclass
class DaemonState:
    """Mutable state for the running daemon process."""

    config: Config
    supervisor: BackendSupervisor
    start_time: datetime = field(default_factory=datetime.now)
    last_request_at: datetime | None = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    idle_timer: "IdleTimer | None" = None
    model_supervisors: dict[str, BackendSupervisor] = field(default_factory=dict)
    model_last_used: dict[str, datetime] = field(default_factory=dict)
    model_ports: dict[str, int] = field(default_factory=dict)
    _next_backend_port: int | None = None

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
        if self.model_supervisors:
            return sorted(
                self.model_supervisors.keys(),
                key=lambda model: self.model_last_used.get(model, datetime.min),
                reverse=True,
            )

        if self.supervisor.is_running() and self.supervisor.active_model:
            return [self.supervisor.active_model]

        return []

    def is_running(self) -> bool:
        """Return True when at least one backend worker is active."""
        if any(supervisor.is_running() for supervisor in self.model_supervisors.values()):
            return True
        return self.supervisor.is_running()

    async def ensure_model_loaded(self, model: str) -> BackendSupervisor:
        """Ensure a model worker is loaded and return its supervisor."""
        max_models = max(1, self.config.daemon.max_loaded_models)

        # Test doubles may replace supervisor with a lightweight fake object.
        if not isinstance(self.supervisor, BackendSupervisor):
            await self.supervisor.ensure_model(model)
            self.model_supervisors = {model: self.supervisor}
            self.model_last_used = {model: datetime.now()}
            self.model_ports = {model: self._backend_port(self.supervisor)}
            return self.supervisor

        if (
            not self.model_supervisors
            and self.supervisor.is_running()
            and self.supervisor.active_model
        ):
            active_model = self.supervisor.active_model
            assert active_model is not None
            self.model_supervisors[active_model] = self.supervisor
            self.model_last_used.setdefault(active_model, datetime.now())
            self.model_ports.setdefault(active_model, self._backend_port(self.supervisor))

        if max_models == 1:
            await self.supervisor.ensure_model(model)
            self.model_supervisors = {model: self.supervisor}
            self.model_last_used = {model: datetime.now()}
            self.model_ports = {model: self._backend_port(self.supervisor)}
            return self.supervisor

        existing = self.model_supervisors.get(model)
        if existing and existing.is_running() and await existing.is_healthy():
            self.touch_model(model)
            return existing

        if existing:
            await self._evict_model(model)

        await self._evict_for_capacity(max_models)
        await self._evict_for_memory_pressure()

        if not self.model_supervisors:
            supervisor = self.supervisor
            await supervisor.ensure_model(model)
        else:
            port = self._allocate_backend_port()
            supervisor = self._build_supervisor_for_port(port)
            await supervisor.start(model)

        self.model_supervisors[model] = supervisor
        self.model_last_used[model] = datetime.now()
        self.model_ports[model] = self._backend_port(supervisor)
        return supervisor

    async def get_supervisor_for_model(self, model: str) -> BackendSupervisor | None:
        """Return a healthy supervisor for a loaded model."""
        supervisor = self.model_supervisors.get(model)
        if supervisor and supervisor.is_running() and await supervisor.is_healthy():
            return supervisor
        return None

    async def get_supervisor_for_any_loaded_model(self) -> BackendSupervisor | None:
        """Return a healthy supervisor from current loaded pool."""
        for model in self.list_loaded_models():
            supervisor = await self.get_supervisor_for_model(model)
            if supervisor:
                return supervisor
        return None

    def touch_model(self, model: str) -> None:
        """Record activity for a specific model worker."""
        now = datetime.now()
        self.model_last_used[model] = now
        self.last_request_at = now
        if self.idle_timer:
            self.idle_timer.touch()

    async def shutdown(self) -> None:
        """Stop every managed worker and clear runtime state."""
        seen: set[int] = set()
        for supervisor in list(self.model_supervisors.values()):
            if id(supervisor) in seen:
                continue
            seen.add(id(supervisor))
            await supervisor.shutdown()

        if id(self.supervisor) not in seen:
            await self.supervisor.shutdown()

        self.model_supervisors.clear()
        self.model_last_used.clear()
        self.model_ports.clear()

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
        """Unload the backend worker when idle timeout is reached."""
        async with self.lock:
            if not self.is_running():
                return

            pinned_model = self._pinned_model()
            if not self.model_supervisors:
                model_name = self.supervisor.active_model
                if model_name and model_name != pinned_model:
                    await self.supervisor.stop()
                    logger.info("Unloaded backend model '%s' due to idle timeout", model_name)
                elif model_name:
                    logger.info(
                        "Idle timeout reached but keeping pinned default model loaded: '%s'",
                        model_name,
                    )
                    self.touch()
                return

            timeout_seconds = self.config.daemon.idle_timeout
            now = datetime.now()
            unloaded: list[str] = []

            for model, last_used in list(self.model_last_used.items()):
                if model == pinned_model:
                    continue
                if (now - last_used).total_seconds() < timeout_seconds:
                    continue
                await self._evict_model(model)
                unloaded.append(model)

            if unloaded:
                logger.info("Unloaded idle backend models: %s", ", ".join(unloaded))
            elif pinned_model and pinned_model in self.model_supervisors:
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
        while len(self.model_supervisors) >= max_models:
            model = self._oldest_evictable_model()
            if model is None:
                break
            await self._evict_model(model)

    async def _evict_for_memory_pressure(self) -> None:
        while self.model_supervisors and not self._has_memory_headroom():
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
            model for model in self.model_supervisors.keys() if model != pinned_model
        ]
        if not candidates:
            return None
        return min(
            candidates,
            key=lambda model: self.model_last_used.get(model, datetime.min),
        )

    async def _evict_model(self, model: str) -> None:
        supervisor = self.model_supervisors.pop(model, None)
        self.model_last_used.pop(model, None)
        self.model_ports.pop(model, None)
        if supervisor:
            await supervisor.stop()

    def _build_supervisor_for_port(self, port: int) -> BackendSupervisor:
        config = self.config.model_copy(deep=True)
        config.backend.port = port
        return BackendSupervisor(config)

    def _allocate_backend_port(self) -> int:
        used_ports = set(self.model_ports.values())
        if self._next_backend_port is None:
            self._next_backend_port = self.config.backend.port + 1

        port = self._next_backend_port
        while port in used_ports:
            port += 1
        self._next_backend_port = port + 1
        return port

    @staticmethod
    def _backend_port(supervisor: BackendSupervisor) -> int:
        try:
            return int(supervisor.backend_url.rsplit(":", 1)[1])
        except Exception:
            return 11435

    def _has_memory_headroom(self) -> bool:
        reserve_gb = max(0.0, self.config.daemon.min_available_memory_gb)
        if reserve_gb <= 0:
            return True

        try:
            import psutil

            available_gb = psutil.virtual_memory().available / (1024**3)
            return available_gb >= reserve_gb
        except Exception:
            return True



def init_state() -> DaemonState:
    """Initialize global daemon state."""
    global _state
    config = Config.load()
    state = DaemonState(config=config, supervisor=BackendSupervisor(config))
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
