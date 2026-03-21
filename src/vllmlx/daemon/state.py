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

    @property
    def loaded_model_name(self) -> str | None:
        """Current active backend model."""
        return self.supervisor.active_model

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
            if not self.supervisor.is_running():
                return

            model_name = self.supervisor.active_model
            await self.supervisor.stop()
            logger.info("Unloaded backend model '%s' due to idle timeout", model_name)



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
