"""Tests for daemon state module."""

import asyncio
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from vmlx.daemon.state import DaemonState, get_state, init_state


class TestDaemonState:
    """Tests for DaemonState class."""

    def test_default_state(self):
        """Test default state initialization."""
        state = DaemonState()
        assert state.model is None
        assert state.processor is None
        assert state.config is None
        assert state.loaded_model_name is None
        assert state.loaded_at is None
        assert state.last_request_at is None
        assert state.start_time is not None
        assert state.lock is not None

    def test_is_model_loaded_false_when_no_model(self):
        """Test is_model_loaded returns False when no model."""
        state = DaemonState()
        assert state.is_model_loaded is False

    def test_is_model_loaded_true_when_model_set(self):
        """Test is_model_loaded returns True when model is set."""
        state = DaemonState()
        state.model = MagicMock()
        assert state.is_model_loaded is True

    def test_touch_updates_last_request_at(self):
        """Test touch updates last_request_at timestamp."""
        state = DaemonState()
        assert state.last_request_at is None
        before = datetime.now()
        state.touch()
        after = datetime.now()
        assert state.last_request_at is not None
        assert before <= state.last_request_at <= after

    def test_touch_updates_timestamp_multiple_calls(self):
        """Test multiple touch calls update timestamp."""
        state = DaemonState()
        state.touch()
        first_touch = state.last_request_at
        state.touch()
        second_touch = state.last_request_at
        assert second_touch >= first_touch

    def test_reset_model_state(self):
        """Test reset_model_state clears model state."""
        state = DaemonState()
        state.model = MagicMock()
        state.processor = MagicMock()
        state.config = MagicMock()
        state.loaded_model_name = "test-model"
        state.loaded_at = datetime.now()

        state.reset_model_state()

        assert state.model is None
        assert state.processor is None
        assert state.config is None
        assert state.loaded_model_name is None
        assert state.loaded_at is None

    def test_reset_preserves_other_state(self):
        """Test reset_model_state preserves non-model state."""
        state = DaemonState()
        start = state.start_time
        state.touch()
        last_request = state.last_request_at
        lock = state.lock

        state.model = MagicMock()
        state.reset_model_state()

        assert state.start_time == start
        assert state.last_request_at == last_request
        assert state.lock is lock

    def test_lock_is_asyncio_lock(self):
        """Test lock is an asyncio Lock."""
        state = DaemonState()
        assert isinstance(state.lock, asyncio.Lock)


class TestGlobalState:
    """Tests for global state management functions."""

    def test_get_state_raises_before_init(self):
        """Test get_state raises RuntimeError before init."""
        # Reset global state
        import vmlx.daemon.state as state_module

        state_module._state = None

        with pytest.raises(RuntimeError, match="Daemon state not initialized"):
            get_state()

    def test_init_state_creates_state(self):
        """Test init_state creates new state."""
        # Reset global state
        import vmlx.daemon.state as state_module

        state_module._state = None

        state = init_state()
        assert state is not None
        assert isinstance(state, DaemonState)

    def test_get_state_returns_initialized_state(self):
        """Test get_state returns the initialized state."""
        # Reset and init
        import vmlx.daemon.state as state_module

        state_module._state = None

        init_state()
        state = get_state()
        assert state is not None
        assert isinstance(state, DaemonState)

    def test_get_state_returns_same_instance(self):
        """Test get_state returns the same instance."""
        import vmlx.daemon.state as state_module

        state_module._state = None

        init_state()
        state1 = get_state()
        state2 = get_state()
        assert state1 is state2

    def test_init_state_replaces_existing(self):
        """Test init_state replaces existing state."""
        import vmlx.daemon.state as state_module

        state_module._state = None

        state1 = init_state()
        state2 = init_state()
        assert state1 is not state2
        assert get_state() is state2
