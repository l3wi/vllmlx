"""Idle timer for automatic model unloading."""

import asyncio
import logging
from datetime import datetime
from typing import Callable, Optional, Union

logger = logging.getLogger(__name__)


class IdleTimer:
    """Background timer that triggers model unload after inactivity.

    The timer runs a background asyncio task that periodically checks
    if the last activity timestamp exceeds the configured timeout.
    When timeout is reached, the on_timeout callback is invoked.
    """

    def __init__(
        self,
        timeout_seconds: int,
        on_timeout: Callable[[], Union[None, "asyncio.coroutine"]],
        check_interval: int = 10,
    ):
        """Initialize the idle timer.

        Args:
            timeout_seconds: Number of seconds of inactivity before timeout
            on_timeout: Callback function to invoke on timeout (can be sync or async)
            check_interval: How often to check for timeout (seconds)
        """
        self.timeout_seconds = timeout_seconds
        self.on_timeout = on_timeout
        self.check_interval = check_interval
        self._task: Optional[asyncio.Task] = None
        self._last_activity: Optional[datetime] = None
        self._running = False

    def touch(self) -> None:
        """Reset the idle timer (called on each request)."""
        self._last_activity = datetime.now()

    def start(self) -> None:
        """Start the background timer task."""
        if self._running:
            return
        self._running = True
        self._last_activity = datetime.now()
        self._task = asyncio.create_task(self._run())
        logger.info(f"Idle timer started (timeout: {self.timeout_seconds}s)")

    def stop(self) -> None:
        """Stop the background timer task."""
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("Idle timer stopped")

    @property
    def seconds_until_timeout(self) -> Optional[float]:
        """Get seconds remaining until timeout, or None if not tracking.

        Returns:
            Number of seconds until timeout, or None if no activity tracked
        """
        if not self._last_activity:
            return None
        elapsed = (datetime.now() - self._last_activity).total_seconds()
        remaining = self.timeout_seconds - elapsed
        return max(0, remaining)

    async def _run(self) -> None:
        """Background task that checks for idle timeout."""
        while self._running:
            try:
                await asyncio.sleep(self.check_interval)

                if not self._last_activity:
                    continue

                elapsed = (datetime.now() - self._last_activity).total_seconds()

                if elapsed >= self.timeout_seconds:
                    logger.info(f"Idle timeout reached ({elapsed:.1f}s)")
                    await self._trigger_timeout()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in idle timer: {e}")

    async def _trigger_timeout(self) -> None:
        """Trigger the timeout callback."""
        try:
            # Run callback (may be sync or async)
            result = self.on_timeout()
            if asyncio.iscoroutine(result):
                await result
            self._last_activity = None  # Stop tracking until next request
        except Exception as e:
            logger.error(f"Error in timeout callback: {e}")
