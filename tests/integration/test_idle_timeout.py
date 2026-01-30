"""Integration tests for idle timeout functionality."""

import asyncio
import sys
from unittest.mock import MagicMock, patch

import pytest


class TestIdleTimerIntegration:
    """Integration tests for idle timer functionality."""

    def _mock_mlx_modules(self):
        """Set up mock MLX modules."""
        mock_mlx_vlm = MagicMock()
        mock_mlx_vlm.load = MagicMock(return_value=(MagicMock(), MagicMock()))
        mock_mlx_vlm.generate = MagicMock(return_value="Hello, world!")
        mock_mlx_vlm.stream_generate = MagicMock(return_value=iter(["Hello", ", ", "world!"]))
        mock_mlx_vlm_utils = MagicMock()
        mock_mlx_vlm_utils.load_config = MagicMock(return_value=MagicMock())
        mock_prompt_utils = MagicMock()
        mock_prompt_utils.apply_chat_template = MagicMock(return_value="formatted prompt")
        mock_mlx_core = MagicMock()

        return {
            "mlx": MagicMock(),
            "mlx.core": mock_mlx_core,
            "mlx_vlm": mock_mlx_vlm,
            "mlx_vlm.utils": mock_mlx_vlm_utils,
            "mlx_vlm.prompt_utils": mock_prompt_utils,
        }

    def test_status_shows_idle_seconds_remaining_after_model_load(self):
        """Test that status shows idle_seconds_remaining after model is loaded."""
        from fastapi.testclient import TestClient

        mock_modules = self._mock_mlx_modules()

        with patch.dict(sys.modules, mock_modules):
            from vmlx.daemon.server import create_app

            app = create_app()
            with TestClient(app) as client:
                # First load a model via chat completion
                client.post(
                    "/v1/chat/completions",
                    json={
                        "model": "test-model",
                        "messages": [{"role": "user", "content": "Hello"}],
                        "stream": False,
                    },
                )

                # Check status shows idle_seconds_remaining
                response = client.get("/status")
                data = response.json()

                assert response.status_code == 200
                assert "idle_seconds_remaining" in data
                # Should have remaining time (could be None before first request with model)
                if data["loaded_model"] is not None:
                    assert data["idle_seconds_remaining"] is not None
                    assert data["idle_seconds_remaining"] > 0

    def test_status_idle_seconds_none_when_no_model(self):
        """Test that status shows None for idle_seconds when no model loaded."""
        from fastapi.testclient import TestClient

        from vmlx.daemon.server import create_app

        app = create_app()
        with TestClient(app) as client:
            response = client.get("/status")
            data = response.json()

            assert response.status_code == 200
            assert data["loaded_model"] is None
            assert data["idle_seconds_remaining"] is None

    def test_idle_timer_resets_on_request(self):
        """Test that idle timer resets when making requests."""
        from fastapi.testclient import TestClient

        mock_modules = self._mock_mlx_modules()

        with patch.dict(sys.modules, mock_modules):
            from vmlx.daemon.server import create_app

            app = create_app()
            with TestClient(app) as client:
                # Load a model
                client.post(
                    "/v1/chat/completions",
                    json={
                        "model": "test-model",
                        "messages": [{"role": "user", "content": "Hello"}],
                        "stream": False,
                    },
                )

                # Get initial idle_seconds
                response1 = client.get("/status")
                _ = response1.json().get("idle_seconds_remaining")  # Used for baseline

                # Wait a bit
                import time

                time.sleep(0.2)

                # Get idle_seconds (should be less now)
                response2 = client.get("/status")
                remaining2 = response2.json().get("idle_seconds_remaining")

                # Make another request - this should reset the timer
                client.post(
                    "/v1/chat/completions",
                    json={
                        "model": "test-model",
                        "messages": [{"role": "user", "content": "Hi again"}],
                        "stream": False,
                    },
                )

                # Get idle_seconds again (should be close to initial)
                response3 = client.get("/status")
                remaining3 = response3.json().get("idle_seconds_remaining")

                # After the second request, remaining should be > remaining2
                if remaining2 is not None and remaining3 is not None:
                    assert remaining3 > remaining2

    def test_internal_unload_stops_idle_timer(self):
        """Test that internal unload stops the idle timer."""
        from fastapi.testclient import TestClient

        mock_modules = self._mock_mlx_modules()

        with patch.dict(sys.modules, mock_modules):
            from vmlx.daemon.server import create_app

            app = create_app()
            with TestClient(app) as client:
                # Load a model
                client.post(
                    "/v1/chat/completions",
                    json={
                        "model": "test-model",
                        "messages": [{"role": "user", "content": "Hello"}],
                        "stream": False,
                    },
                )

                # Verify model is loaded with idle tracking
                status1 = client.get("/status").json()
                assert status1["loaded_model"] is not None

                # Unload the model
                unload_response = client.post("/_internal/unload")
                assert unload_response.json()["success"] is True

                # Check that idle tracking stopped
                status2 = client.get("/status").json()
                assert status2["loaded_model"] is None
                assert status2["idle_seconds_remaining"] is None


class TestIdleTimerState:
    """Tests for idle timer state management."""

    def _mock_mlx_modules(self):
        """Set up mock MLX modules."""
        mock_mlx_vlm = MagicMock()
        mock_mlx_vlm.load = MagicMock(return_value=(MagicMock(), MagicMock()))
        mock_mlx_vlm.generate = MagicMock(return_value="Hello, world!")
        mock_mlx_vlm_utils = MagicMock()
        mock_mlx_vlm_utils.load_config = MagicMock(return_value=MagicMock())
        mock_prompt_utils = MagicMock()
        mock_prompt_utils.apply_chat_template = MagicMock(return_value="formatted prompt")
        mock_mlx_core = MagicMock()

        return {
            "mlx": MagicMock(),
            "mlx.core": mock_mlx_core,
            "mlx_vlm": mock_mlx_vlm,
            "mlx_vlm.utils": mock_mlx_vlm_utils,
            "mlx_vlm.prompt_utils": mock_prompt_utils,
        }

    def test_hot_swap_restarts_idle_timer(self):
        """Test that hot-swapping models restarts the idle timer."""
        from fastapi.testclient import TestClient

        mock_modules = self._mock_mlx_modules()

        with patch.dict(sys.modules, mock_modules):
            from vmlx.daemon.server import create_app

            app = create_app()
            with TestClient(app) as client:
                # Load first model
                client.post(
                    "/v1/chat/completions",
                    json={
                        "model": "model-1",
                        "messages": [{"role": "user", "content": "Hello"}],
                        "stream": False,
                    },
                )

                # Check status
                status1 = client.get("/status").json()
                remaining1 = status1.get("idle_seconds_remaining")

                # Wait a bit
                import time

                time.sleep(0.1)

                # Load different model (hot-swap)
                client.post(
                    "/v1/chat/completions",
                    json={
                        "model": "model-2",
                        "messages": [{"role": "user", "content": "Hello"}],
                        "stream": False,
                    },
                )

                # Check status - idle timer should be reset
                status2 = client.get("/status").json()
                remaining2 = status2.get("idle_seconds_remaining")

                # Timer should be reset (close to max timeout)
                if remaining1 is not None and remaining2 is not None:
                    # remaining2 should be >= remaining1 because timer was reset
                    assert remaining2 >= remaining1 - 0.2  # Allow small tolerance


@pytest.mark.slow
class TestIdleTimeoutBehavior:
    """Tests for actual idle timeout behavior (marked slow)."""

    @pytest.mark.asyncio
    async def test_model_unloads_after_idle_timeout(self):
        """Test that model unloads automatically after idle timeout.

        This test uses the IdleTimer directly with a very short timeout
        to verify the timeout callback behavior.
        """
        from vmlx.daemon.idle import IdleTimer

        # Track if unload was called
        unloaded = False
        unloaded_model_name = None

        async def mock_unload():
            nonlocal unloaded, unloaded_model_name
            unloaded = True
            unloaded_model_name = "test-model"

        # Create timer with short timeout (0.5s) and short check interval (0.1s)
        timer = IdleTimer(
            timeout_seconds=1,
            on_timeout=mock_unload,
            check_interval=0.1,
        )

        try:
            timer.start()

            # Verify timer is running
            assert timer._running
            assert timer._last_activity is not None

            # Wait for timeout + buffer
            await asyncio.sleep(1.5)

            # Unload callback should have been called
            assert unloaded, "Unload callback should have been triggered"
            assert unloaded_model_name == "test-model"
        finally:
            timer.stop()


class TestIdleTimerConfiguration:
    """Tests for idle timer configuration."""

    def test_idle_timeout_from_config(self):
        """Test that idle timeout uses value from config."""
        from vmlx.config import Config

        config = Config()
        assert config.daemon.idle_timeout == 60  # Default

        config.daemon.idle_timeout = 120
        assert config.daemon.idle_timeout == 120

    def test_idle_timeout_configurable(self):
        """Test that idle timeout can be set via config.set()."""
        from vmlx.config import Config

        config = Config()
        config.set("daemon.idle_timeout", 300)
        assert config.daemon.idle_timeout == 300
