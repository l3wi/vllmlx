"""Daemon state management for vmlx."""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from vmlx.daemon.idle import IdleTimer

logger = logging.getLogger(__name__)

# Global daemon state instance
_state: Optional["DaemonState"] = None


@dataclass
class DaemonState:
    """Mutable state for the running daemon."""

    model: Optional[Any] = None
    processor: Optional[Any] = None
    config: Optional[Any] = None
    loaded_model_name: Optional[str] = None
    loaded_at: Optional[datetime] = None
    last_request_at: Optional[datetime] = None
    start_time: datetime = field(default_factory=datetime.now)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    idle_timer: Optional["IdleTimer"] = None

    @property
    def is_model_loaded(self) -> bool:
        """Check if a model is currently loaded."""
        return self.model is not None

    def touch(self) -> None:
        """Update last request timestamp and reset idle timer."""
        self.last_request_at = datetime.now()
        if self.idle_timer:
            self.idle_timer.touch()

    def reset_model_state(self) -> None:
        """Clear model-related state after unloading."""
        self.model = None
        self.processor = None
        self.config = None
        self.loaded_model_name = None
        self.loaded_at = None

    def start_idle_tracking(self, timeout: int) -> None:
        """Start tracking idle time for loaded model.

        Args:
            timeout: Number of seconds of inactivity before unloading
        """
        from vmlx.daemon.idle import IdleTimer

        # Stop existing timer if any
        if self.idle_timer:
            self.idle_timer.stop()

        self.idle_timer = IdleTimer(
            timeout_seconds=timeout,
            on_timeout=self._unload_on_idle,
        )
        self.idle_timer.start()

    def stop_idle_tracking(self) -> None:
        """Stop idle tracking (model unloaded)."""
        if self.idle_timer:
            self.idle_timer.stop()
            self.idle_timer = None

    async def _unload_on_idle(self) -> None:
        """Callback when idle timeout triggers."""
        from vmlx.models.manager import ModelManager

        async with self.lock:
            if self.model:
                model_name = self.loaded_model_name
                idle_duration = (
                    datetime.now() - self.last_request_at
                ).total_seconds() if self.last_request_at else 0

                ModelManager.unload_model(self.model, self.processor)
                self.reset_model_state()
                self.stop_idle_tracking()

                logger.info(
                    f"Unloaded model '{model_name}' due to idle timeout "
                    f"(idle for {idle_duration:.1f}s)"
                )


def init_state() -> DaemonState:
    """Initialize global daemon state.

    Returns:
        The newly initialized DaemonState instance
    """
    global _state
    _state = DaemonState()
    return _state


def get_state() -> DaemonState:
    """Get the global daemon state.

    Returns:
        The current DaemonState instance

    Raises:
        RuntimeError: If state hasn't been initialized
    """
    global _state
    if _state is None:
        raise RuntimeError("Daemon state not initialized. Call init_state() first.")
    return _state
