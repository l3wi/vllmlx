"""Integration tests for vmlx API endpoints."""

import sys
from unittest.mock import MagicMock, patch


class TestHealthEndpoint:
    """Tests for /health endpoint."""

    def test_health_returns_ok(self):
        """Test health endpoint returns status ok."""
        from fastapi.testclient import TestClient

        from vmlx.daemon.server import create_app

        app = create_app()
        with TestClient(app) as client:
            response = client.get("/health")

            assert response.status_code == 200
            assert response.json() == {"status": "ok"}


class TestListModelsEndpoint:
    """Tests for /v1/models endpoint."""

    def test_list_models_returns_list(self):
        """Test list models endpoint returns model list."""
        from datetime import datetime
        from unittest.mock import MagicMock

        from fastapi.testclient import TestClient

        from vmlx.daemon.server import create_app

        # Mock the list_models function
        mock_model = MagicMock()
        mock_model.name = "test-model"
        mock_model.hf_path = "test-org/test-model"
        mock_model.last_modified = datetime(2024, 1, 1)

        with patch("vmlx.models.registry.list_models", return_value=[mock_model]):
            app = create_app()
            with TestClient(app) as client:
                response = client.get("/v1/models")

                assert response.status_code == 200
                data = response.json()
                assert data["object"] == "list"
                assert len(data["data"]) == 1
                assert data["data"][0]["id"] == "test-model"
                assert data["data"][0]["owned_by"] == "test-org"

    def test_list_models_empty(self):
        """Test list models returns empty list when no models."""
        from fastapi.testclient import TestClient

        from vmlx.daemon.server import create_app

        with patch("vmlx.daemon.routes.list_models", return_value=[]):
            app = create_app()
            with TestClient(app) as client:
                response = client.get("/v1/models")

                assert response.status_code == 200
                data = response.json()
                assert data["object"] == "list"
                assert data["data"] == []


class TestStatusEndpoint:
    """Tests for /status endpoint."""

    def test_status_returns_daemon_info(self):
        """Test status endpoint returns daemon information."""
        from fastapi.testclient import TestClient

        from vmlx.daemon.server import create_app

        app = create_app()
        with TestClient(app) as client:
            response = client.get("/status")

            assert response.status_code == 200
            data = response.json()
            assert data["running"] is True
            assert "pid" in data
            assert "uptime_seconds" in data
            assert "loaded_model" in data
            assert "idle_timeout" in data


class TestChatCompletionsEndpoint:
    """Tests for /v1/chat/completions endpoint."""

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

    def test_chat_completion_text_only(self):
        """Test chat completion with text-only message."""
        from fastapi.testclient import TestClient

        mock_modules = self._mock_mlx_modules()

        with patch.dict(sys.modules, mock_modules):
            from vmlx.daemon.server import create_app

            app = create_app()
            with TestClient(app) as client:
                response = client.post(
                    "/v1/chat/completions",
                    json={
                        "model": "test-model",
                        "messages": [{"role": "user", "content": "Hello"}],
                        "stream": False,
                    },
                )

                assert response.status_code == 200
                data = response.json()
                assert "id" in data
                assert data["object"] == "chat.completion"
                assert data["model"] == "test-model"
                assert len(data["choices"]) == 1
                assert data["choices"][0]["message"]["role"] == "assistant"
                assert data["choices"][0]["finish_reason"] == "stop"

    def test_chat_completion_with_image(self):
        """Test chat completion with image input."""
        from fastapi.testclient import TestClient

        mock_modules = self._mock_mlx_modules()

        with patch.dict(sys.modules, mock_modules):
            from vmlx.daemon.server import create_app

            app = create_app()
            with TestClient(app) as client:
                response = client.post(
                    "/v1/chat/completions",
                    json={
                        "model": "test-model",
                        "messages": [
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": "What is in this image?"},
                                    {
                                        "type": "image_url",
                                        "image_url": {"url": "data:image/jpeg;base64,/9j/4AAQ..."},
                                    },
                                ],
                            }
                        ],
                        "stream": False,
                    },
                )

                assert response.status_code == 200
                data = response.json()
                assert data["object"] == "chat.completion"

    def test_chat_completion_streaming(self):
        """Test chat completion with streaming."""
        from fastapi.testclient import TestClient

        mock_modules = self._mock_mlx_modules()

        with patch.dict(sys.modules, mock_modules):
            from vmlx.daemon.server import create_app

            app = create_app()
            with TestClient(app) as client:
                response = client.post(
                    "/v1/chat/completions",
                    json={
                        "model": "test-model",
                        "messages": [{"role": "user", "content": "Hello"}],
                        "stream": True,
                    },
                )

                assert response.status_code == 200
                assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

                # Read streamed content
                content = response.text
                assert "data:" in content
                assert "[DONE]" in content


class TestInternalUnloadEndpoint:
    """Tests for /_internal/unload endpoint."""

    def test_unload_when_no_model_loaded(self):
        """Test unload returns success when no model loaded."""
        from fastapi.testclient import TestClient

        from vmlx.daemon.server import create_app

        app = create_app()
        with TestClient(app) as client:
            response = client.post("/_internal/unload")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["unloaded_model"] is None


class TestExtractContent:
    """Tests for extract_content helper function."""

    def test_extract_simple_text(self):
        """Test extracting simple text content."""
        from vmlx.daemon.routes import Message, extract_content

        messages = [Message(role="user", content="Hello, world!")]
        prompt, images = extract_content(messages)

        assert "Hello, world!" in prompt
        assert images == []

    def test_extract_multipart_content(self):
        """Test extracting multipart content with images."""
        from vmlx.daemon.routes import Message, extract_content

        messages = [
            Message(
                role="user",
                content=[
                    {"type": "text", "text": "What is this?"},
                    {"type": "image_url", "image_url": {"url": "http://example.com/image.jpg"}},
                ],
            )
        ]
        prompt, images = extract_content(messages)

        assert "What is this?" in prompt
        assert len(images) == 1
        assert images[0] == "http://example.com/image.jpg"

    def test_extract_base64_image(self):
        """Test extracting base64 encoded image."""
        from vmlx.daemon.routes import Message, extract_content

        base64_url = "data:image/jpeg;base64,/9j/4AAQSkZJRg..."
        messages = [
            Message(
                role="user",
                content=[
                    {"type": "text", "text": "Describe this"},
                    {"type": "image_url", "image_url": {"url": base64_url}},
                ],
            )
        ]
        prompt, images = extract_content(messages)

        assert "Describe this" in prompt
        assert len(images) == 1
        assert images[0] == base64_url

    def test_extract_multiple_messages(self):
        """Test extracting from multiple messages."""
        from vmlx.daemon.routes import Message, extract_content

        messages = [
            Message(role="system", content="You are helpful."),
            Message(role="user", content="Hello"),
            Message(role="assistant", content="Hi there!"),
            Message(role="user", content="How are you?"),
        ]
        prompt, images = extract_content(messages)

        assert "You are helpful" in prompt
        assert "Hello" in prompt
        assert "Hi there!" in prompt
        assert "How are you?" in prompt
        assert images == []
