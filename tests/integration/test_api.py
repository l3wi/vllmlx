"""Integration tests for vllmlx daemon API surface."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.testclient import TestClient

from vllmlx.config import Config
from vllmlx.daemon.server import create_app
from vllmlx.daemon.state import get_state


class _FakeSupervisor:
    def __init__(self):
        self.running = False
        self.active_model: str | None = None
        self.ensure_calls: list[str] = []
        self.start_calls: list[str] = []
        self.stop_calls = 0
        self.shutdown_calls = 0
        self.health_calls = 0
        self.backend_url = "http://127.0.0.1:12345"

    def is_running(self) -> bool:
        return self.running

    async def is_healthy(self) -> bool:
        self.health_calls += 1
        return self.running

    async def ensure_model(self, model: str) -> None:
        self.ensure_calls.append(model)
        self.active_model = model
        self.running = True

    async def start(self, model: str) -> None:
        self.start_calls.append(model)
        self.active_model = model
        self.running = True

    async def stop(self) -> None:
        self.running = False
        self.active_model = None
        self.stop_calls += 1

    async def shutdown(self) -> None:
        self.running = False
        self.shutdown_calls += 1


class TestDaemonSurface:
    def test_health_returns_ok(self):
        app = create_app()
        with TestClient(app) as client:
            response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_legacy_status_endpoint_is_removed(self):
        app = create_app()
        with TestClient(app) as client:
            response = client.get("/status")
        assert response.status_code == 404

    def test_v1_status_returns_not_loaded_when_backend_not_running(self):
        app = create_app()
        with TestClient(app) as client:
            response = client.get("/v1/status")
        assert response.status_code == 200
        assert response.json() == {
            "status": "not_loaded",
            "model": None,
            "models": [],
            "requests": [],
        }

    def test_v1_models_returns_empty_when_backend_not_running(self):
        app = create_app()
        with TestClient(app) as client:
            response = client.get("/v1/models")
        assert response.status_code == 200
        assert response.json() == {"object": "list", "data": []}

    def test_v1_models_returns_empty_when_backend_unhealthy(self):
        app = create_app()
        with TestClient(app) as client:
            state = get_state()
            supervisor = _FakeSupervisor()
            supervisor.running = True

            async def unhealthy() -> bool:
                return False

            supervisor.is_healthy = unhealthy
            state.primary_supervisor = supervisor

            response = client.get("/v1/models")

        assert response.status_code == 200
        assert response.json() == {"object": "list", "data": []}


class TestProxyRouting:
    def test_chat_request_auto_loads_model_and_proxies(self):
        app = create_app()
        with TestClient(app) as client:
            state = get_state()
            supervisor = _FakeSupervisor()
            state.primary_supervisor = supervisor

            observed: dict[str, Any] = {}

            async def fake_proxy(request, backend_path, raw_body, payload, base_url=None):
                observed["backend_path"] = backend_path
                observed["payload"] = payload
                observed["raw_body"] = raw_body
                return JSONResponse({"ok": True})

            state.config = Config(aliases={"vision": "mlx-community/Qwen3-VL-4B-Instruct-3bit"})

            with patch("vllmlx.daemon.routes._proxy", side_effect=fake_proxy):
                response = client.post(
                    "/v1/chat/completions",
                    json={
                        "model": "vision",
                        "messages": [{"role": "user", "content": "hello"}],
                        "stream": False,
                    },
                )

            assert response.status_code == 200
            assert response.json() == {"ok": True}
            assert supervisor.ensure_calls == ["mlx-community/Qwen3-VL-4B-Instruct-3bit"]
            assert observed["backend_path"] == "/v1/chat/completions"
            assert observed["payload"]["model"] == "mlx-community/Qwen3-VL-4B-Instruct-3bit"

    def test_targeted_proxy_reuses_ensured_supervisor_without_second_lookup(self):
        app = create_app()
        with TestClient(app) as client:
            state = get_state()
            supervisor = _FakeSupervisor()
            state.primary_supervisor = supervisor
            state.config = Config(aliases={})

            observed: dict[str, Any] = {}

            async def fake_proxy(request, backend_path, raw_body, payload, base_url=None):
                observed["backend_path"] = backend_path
                observed["base_url"] = base_url
                return JSONResponse({"ok": True})

            async def unexpected_lookup(model: str):
                raise AssertionError(
                    "get_supervisor_for_model should not run for model-targeted requests"
                )

            with (
                patch("vllmlx.daemon.routes._proxy", side_effect=fake_proxy),
                patch.object(state, "get_supervisor_for_model", side_effect=unexpected_lookup),
            ):
                response = client.post(
                    "/v1/chat/completions",
                    json={
                        "model": "mlx-community/Qwen3-VL-4B-Instruct-3bit",
                        "messages": [{"role": "user", "content": "hello"}],
                        "stream": False,
                    },
                )

            assert response.status_code == 200
            assert response.json() == {"ok": True}
            assert observed["backend_path"] == "/v1/chat/completions"
            assert observed["base_url"] == supervisor.backend_url

    def test_embeddings_request_loads_embedding_model_and_proxies(self):
        app = create_app()
        with TestClient(app) as client:
            state = get_state()
            supervisor = _FakeSupervisor()
            supervisor.running = True
            supervisor.active_model = "mlx-community/Qwen3-8B-4bit"
            state.primary_supervisor = supervisor

            observed: dict[str, Any] = {}

            async def fake_proxy(request, backend_path, raw_body, payload, base_url=None):
                observed["backend_path"] = backend_path
                observed["payload"] = payload
                return JSONResponse({"ok": True})

            state.config = Config(
                aliases={},
                backend={
                    "embedding_model": "mlx-community/Qwen3-Embedding-4B-4bit-DWQ",
                },
            )

            with patch("vllmlx.daemon.routes._proxy", side_effect=fake_proxy):
                response = client.post(
                    "/v1/embeddings",
                    json={
                        "model": "qwen3-embedding:4b",
                        "input": "hello",
                    },
                )

            assert response.status_code == 200
            assert response.json() == {"ok": True}
            assert supervisor.ensure_calls == ["mlx-community/Qwen3-Embedding-4B-4bit-DWQ"]
            assert observed["backend_path"] == "/v1/embeddings"
            assert observed["payload"]["model"] == "mlx-community/Qwen3-Embedding-4B-4bit-DWQ"

    def test_embeddings_request_uses_configured_embedding_model_when_model_omitted(self):
        app = create_app()
        with TestClient(app) as client:
            state = get_state()
            supervisor = _FakeSupervisor()
            state.primary_supervisor = supervisor

            observed: dict[str, Any] = {}

            async def fake_proxy(request, backend_path, raw_body, payload, base_url=None):
                observed["backend_path"] = backend_path
                observed["payload"] = payload
                return JSONResponse({"ok": True})

            state.config = Config(
                aliases={},
                backend={
                    "embedding_model": "mlx-community/Qwen3-Embedding-4B-4bit-DWQ",
                },
            )

            with patch("vllmlx.daemon.routes._proxy", side_effect=fake_proxy):
                response = client.post(
                    "/v1/embeddings",
                    json={
                        "input": "hello",
                    },
                )

            assert response.status_code == 200
            assert response.json() == {"ok": True}
            assert supervisor.ensure_calls == ["mlx-community/Qwen3-Embedding-4B-4bit-DWQ"]
            assert observed["backend_path"] == "/v1/embeddings"
            assert observed["payload"]["model"] == "mlx-community/Qwen3-Embedding-4B-4bit-DWQ"

    def test_request_without_model_returns_503_when_unloaded(self):
        app = create_app()
        with TestClient(app) as client:
            state = get_state()
            state.primary_supervisor = _FakeSupervisor()

            response = client.post(
                "/v1/chat/completions",
                json={"messages": [{"role": "user", "content": "hello"}]},
            )

            assert response.status_code == 503

    def test_streaming_proxy_response_passthrough(self):
        app = create_app()
        with TestClient(app) as client:
            state = get_state()
            supervisor = _FakeSupervisor()
            state.primary_supervisor = supervisor

            async def fake_proxy(request, backend_path, raw_body, payload, base_url=None):
                async def event_stream():
                    yield b"data: {\"choices\":[{\"delta\":{\"content\":\"Hi\"}}]}\\n\\n"
                    yield b"data: [DONE]\\n\\n"

                return StreamingResponse(event_stream(), media_type="text/event-stream")

            with patch("vllmlx.daemon.routes._proxy", side_effect=fake_proxy):
                response = client.post(
                    "/v1/chat/completions",
                    json={
                        "model": "mlx-community/Qwen3-VL-4B-Instruct-3bit",
                        "messages": [{"role": "user", "content": "hello"}],
                        "stream": True,
                    },
                )

            assert response.status_code == 200
            assert "data:" in response.text
            assert "[DONE]" in response.text

    def test_streaming_proxy_keeps_upstream_open_until_stream_end(self):
        app = create_app()
        with TestClient(app) as client:
            state = get_state()
            supervisor = _FakeSupervisor()
            state.primary_supervisor = supervisor
            created_clients: list[FakeAsyncClient] = []

            class FakeIncomingResponse:
                def __init__(self, owner: FakeAsyncClient):
                    self.owner = owner
                    self.status_code = 200
                    self.headers = {"content-type": "text/event-stream"}
                    self.closed = False

                async def aiter_bytes(self):
                    if self.owner.closed:
                        raise RuntimeError("client closed before stream consumption")
                    yield b"data: {\"choices\":[{\"delta\":{\"content\":\"Hi\"}}]}\\n\\n"
                    if self.owner.closed:
                        raise RuntimeError("client closed during stream consumption")
                    yield b"data: [DONE]\\n\\n"

                async def aclose(self):
                    self.closed = True

            class FakeAsyncClient:
                def __init__(self, *args, **kwargs):
                    self.closed = False
                    self.incoming = FakeIncomingResponse(self)
                    created_clients.append(self)

                def build_request(self, *args, **kwargs):
                    return object()

                async def send(self, request, stream: bool = False):
                    assert stream is True
                    return self.incoming

                async def aclose(self):
                    self.closed = True

            with patch("vllmlx.daemon.routes.httpx.AsyncClient", FakeAsyncClient):
                response = client.post(
                    "/v1/chat/completions",
                    json={
                        "model": "mlx-community/Qwen3-4B-4bit",
                        "messages": [{"role": "user", "content": "hello"}],
                        "stream": True,
                    },
                )

            assert response.status_code == 200
            assert "data:" in response.text
            assert "[DONE]" in response.text
            assert len(created_clients) == 1
            assert created_clients[0].incoming.closed is True
            assert created_clients[0].closed is True


class TestHardCutCompatibility:
    def test_no_legacy_script_entry_in_pyproject(self):
        pyproject = open("pyproject.toml", "r", encoding="utf-8").read()
        assert "vllmlx = \"vllmlx.cli.main:cli\"" in pyproject
        assert "\nvmlx = \"" not in pyproject

    def test_old_module_import_fails(self):
        with pytest.raises(ModuleNotFoundError):
            __import__("vmlx")
