"""Daemon state management for vmlx."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

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

    @property
    def is_model_loaded(self) -> bool:
        """Check if a model is currently loaded."""
        return self.model is not None

    def touch(self) -> None:
        """Update last request timestamp."""
        self.last_request_at = datetime.now()

    def reset_model_state(self) -> None:
        """Clear model-related state after unloading."""
        self.model = None
        self.processor = None
        self.config = None
        self.loaded_model_name = None
        self.loaded_at = None


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
