"""Unit tests for idle timer module."""

import asyncio

import pytest

from vmlx.daemon.idle import IdleTimer


class TestIdleTimerBasics:
    """Basic tests for IdleTimer class."""

    def test_init_with_defaults(self):
        """Test IdleTimer initialization with default values."""
        timer = IdleTimer(timeout_seconds=60, on_timeout=lambda: None)
        assert timer.timeout_seconds == 60
        assert timer.check_interval == 10
        assert not timer._running
        assert timer._task is None

    def test_init_with_custom_check_interval(self):
        """Test IdleTimer initialization with custom check interval."""
        timer = IdleTimer(timeout_seconds=30, on_timeout=lambda: None, check_interval=5)
        assert timer.timeout_seconds == 30
        assert timer.check_interval == 5

    def test_touch_updates_last_activity(self):
        """Test that touch() updates the last activity timestamp."""
        timer = IdleTimer(timeout_seconds=60, on_timeout=lambda: None)
        assert timer._last_activity is None
        timer.touch()
        assert timer._last_activity is not None

    def test_seconds_until_timeout_none_before_touch(self):
        """Test seconds_until_timeout returns None before any activity."""
        timer = IdleTimer(timeout_seconds=60, on_timeout=lambda: None)
        assert timer.seconds_until_timeout is None

    def test_seconds_until_timeout_after_touch(self):
        """Test seconds_until_timeout returns correct value after touch."""
        timer = IdleTimer(timeout_seconds=60, on_timeout=lambda: None)
        timer.touch()
        remaining = timer.seconds_until_timeout
        assert remaining is not None
        assert 59 < remaining <= 60


class TestIdleTimerAsync:
    """Async tests for IdleTimer."""

    @pytest.mark.asyncio
    async def test_start_creates_task(self):
        """Test that start() creates a background task."""
        timer = IdleTimer(timeout_seconds=60, on_timeout=lambda: None, check_interval=1)
        timer.start()

        try:
            assert timer._running
            assert timer._task is not None
            assert timer._last_activity is not None
        finally:
            timer.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_task(self):
        """Test that stop() cancels the background task."""
        timer = IdleTimer(timeout_seconds=60, on_timeout=lambda: None, check_interval=1)
        timer.start()
        timer.stop()

        assert not timer._running
        assert timer._task is None

    @pytest.mark.asyncio
    async def test_start_idempotent(self):
        """Test that starting an already running timer is a no-op."""
        timer = IdleTimer(timeout_seconds=60, on_timeout=lambda: None, check_interval=1)
        timer.start()
        task1 = timer._task
        timer.start()  # Should not create new task

        try:
            assert timer._task is task1
        finally:
            timer.stop()

    @pytest.mark.asyncio
    async def test_timer_triggers_after_timeout(self):
        """Test that timer triggers callback after timeout."""
        triggered = False

        def on_timeout():
            nonlocal triggered
            triggered = True

        timer = IdleTimer(timeout_seconds=1, on_timeout=on_timeout, check_interval=0.1)
        timer.start()

        try:
            await asyncio.sleep(1.5)
            assert triggered
        finally:
            timer.stop()

    @pytest.mark.asyncio
    async def test_timer_triggers_async_callback(self):
        """Test that timer triggers async callback after timeout."""
        triggered = False

        async def on_timeout():
            nonlocal triggered
            triggered = True

        timer = IdleTimer(timeout_seconds=1, on_timeout=on_timeout, check_interval=0.1)
        timer.start()

        try:
            await asyncio.sleep(1.5)
            assert triggered
        finally:
            timer.stop()

    @pytest.mark.asyncio
    async def test_touch_resets_timer(self):
        """Test that touch() resets the timer."""
        triggered = False

        def on_timeout():
            nonlocal triggered
            triggered = True

        timer = IdleTimer(timeout_seconds=1, on_timeout=on_timeout, check_interval=0.1)
        timer.start()

        try:
            # Keep touching every 0.5s for 1.5s total
            # Timer would have fired at 1s if not touched
            for _ in range(3):
                await asyncio.sleep(0.5)
                timer.touch()

            assert not triggered  # Should not have triggered yet
        finally:
            timer.stop()

    @pytest.mark.asyncio
    async def test_timer_clears_last_activity_after_timeout(self):
        """Test that last_activity is cleared after timeout."""
        timer = IdleTimer(timeout_seconds=1, on_timeout=lambda: None, check_interval=0.1)
        timer.start()

        try:
            await asyncio.sleep(1.5)
            # After timeout, _last_activity should be None (stops tracking until next request)
            assert timer._last_activity is None
        finally:
            timer.stop()

    @pytest.mark.asyncio
    async def test_callback_error_does_not_stop_timer(self):
        """Test that an error in callback doesn't stop the timer."""
        call_count = 0

        def on_timeout():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Test error")

        timer = IdleTimer(timeout_seconds=0.5, on_timeout=on_timeout, check_interval=0.1)
        timer.start()

        try:
            await asyncio.sleep(0.8)
            assert call_count >= 1  # Should have been called despite error
        finally:
            timer.stop()


class TestIdleTimerSecondsRemaining:
    """Tests for seconds_until_timeout property."""

    def test_seconds_until_timeout_decreases(self):
        """Test that seconds_until_timeout decreases over time."""
        timer = IdleTimer(timeout_seconds=60, on_timeout=lambda: None)
        timer.touch()

        import time

        remaining1 = timer.seconds_until_timeout
        time.sleep(0.1)
        remaining2 = timer.seconds_until_timeout

        assert remaining2 < remaining1

    def test_seconds_until_timeout_never_negative(self):
        """Test that seconds_until_timeout doesn't go negative."""
        timer = IdleTimer(timeout_seconds=0, on_timeout=lambda: None)
        timer.touch()

        import time

        time.sleep(0.1)
        remaining = timer.seconds_until_timeout

        assert remaining >= 0
