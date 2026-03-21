"""API routes for vllmlx daemon.

The daemon exposes a stable public endpoint and proxies OpenAI/Anthropic-style
`/v1/*` requests to a managed internal vllm-mlx worker.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

from vllmlx.config import Config
from vllmlx.daemon.state import get_state
from vllmlx.models.aliases import resolve_alias

router = APIRouter()
logger = logging.getLogger(__name__)

_REQUEST_MODEL_PATHS = {
    "chat/completions",
    "completions",
    "messages",
    "embeddings",
}

_HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "host",
    "content-length",
}



def _filter_request_headers(headers: httpx.Headers) -> dict[str, str]:
    """Filter hop-by-hop headers before forwarding to backend."""
    return {
        key: value
        for key, value in headers.items()
        if key.lower() not in _HOP_BY_HOP_HEADERS
    }



def _filter_response_headers(headers: httpx.Headers) -> dict[str, str]:
    """Filter hop-by-hop headers when returning proxied responses."""
    return {
        key: value
        for key, value in headers.items()
        if key.lower() not in _HOP_BY_HOP_HEADERS
    }



def _extract_target_model(path: str, payload: Any) -> str | None:
    """Extract model name from request payload for model-routed endpoints."""
    if path not in _REQUEST_MODEL_PATHS:
        return None
    if not isinstance(payload, dict):
        return None
    model = payload.get("model")
    if not isinstance(model, str) or not model.strip():
        return None
    return model



def _is_stream_request(payload: Any, request: Request) -> bool:
    """Determine whether this request expects streaming response handling."""
    accept_header = request.headers.get("accept", "")
    if "text/event-stream" in accept_header:
        return True

    if isinstance(payload, dict):
        stream = payload.get("stream")
        if isinstance(stream, bool):
            return stream

    return False


async def _proxy(
    request: Request,
    backend_path: str,
    raw_body: bytes,
    payload: Any,
) -> Response:
    """Proxy an HTTP request to the active backend worker."""
    state = get_state()
    base_url = state.supervisor.backend_url

    headers = _filter_request_headers(request.headers)
    params = dict(request.query_params)
    method = request.method.upper()

    if _is_stream_request(payload, request):
        # Keep the upstream client alive for the full streaming lifetime.
        client = httpx.AsyncClient(base_url=base_url, timeout=None)
        outgoing = client.build_request(
            method,
            backend_path,
            headers=headers,
            params=params,
            content=raw_body,
        )
        try:
            incoming = await client.send(outgoing, stream=True)
        except httpx.HTTPError as exc:
            await client.aclose()
            raise HTTPException(
                status_code=503,
                detail=f"Backend proxy request failed: {exc}",
            ) from exc

        async def iterator():
            try:
                async for chunk in incoming.aiter_bytes():
                    yield chunk
            finally:
                await incoming.aclose()
                await client.aclose()

        return StreamingResponse(
            iterator(),
            status_code=incoming.status_code,
            media_type=incoming.headers.get("content-type"),
            headers=_filter_response_headers(incoming.headers),
        )

    async with httpx.AsyncClient(base_url=base_url, timeout=None) as client:
        try:
            incoming = await client.request(
                method,
                backend_path,
                headers=headers,
                params=params,
                content=raw_body,
            )
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=503,
                detail=f"Backend proxy request failed: {exc}",
            ) from exc

    return Response(
        content=incoming.content,
        status_code=incoming.status_code,
        media_type=incoming.headers.get("content-type"),
        headers=_filter_response_headers(incoming.headers),
    )


@router.get("/health")
async def health() -> dict[str, str]:
    """Daemon health check endpoint."""
    return {"status": "ok"}


@router.get("/v1/status")
async def status(request: Request) -> Response:
    """Return upstream status payload, or not-loaded when worker is inactive."""
    state = get_state()

    if not state.supervisor.is_running() or not await state.supervisor.is_healthy():
        return JSONResponse(
            {
                "status": "not_loaded",
                "model": None,
                "requests": [],
            }
        )

    return await _proxy(request, "/v1/status", b"", None)


@router.get("/v1/models")
async def list_models(request: Request) -> Response:
    """List currently active model from backend; empty list when unloaded."""
    state = get_state()

    if not state.supervisor.is_running() or not await state.supervisor.is_healthy():
        return JSONResponse({"object": "list", "data": []})

    return await _proxy(request, "/v1/models", b"", None)


@router.api_route(
    "/v1/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
)
async def proxy_v1(path: str, request: Request) -> Response:
    """Proxy arbitrary `/v1/*` API requests to the managed backend."""
    state = get_state()
    raw_body = await request.body()
    payload: Any = None

    if raw_body:
        try:
            payload = json.loads(raw_body)
        except json.JSONDecodeError:
            payload = None

    if request.method.upper() in {"POST", "PUT", "PATCH"}:
        config = Config.load()
        requested = _extract_target_model(path, payload)

        # Allow embedding requests without explicit model in payload by using
        # configured backend embedding_model as the default.
        if (
            not requested
            and path == "embeddings"
            and isinstance(payload, dict)
            and config.backend.embedding_model
        ):
            requested = config.backend.embedding_model
            payload["model"] = requested
            raw_body = json.dumps(payload).encode("utf-8")

        if requested:
            resolved_model = resolve_alias(requested, config.aliases)
            if isinstance(payload, dict):
                payload["model"] = resolved_model
                raw_body = json.dumps(payload).encode("utf-8")

            async with state.lock:
                try:
                    await state.supervisor.ensure_model(resolved_model)
                except Exception as exc:
                    raise HTTPException(
                        status_code=503,
                        detail=f"Failed to load backend model '{resolved_model}': {exc}",
                    ) from exc

    if not state.supervisor.is_running():
        raise HTTPException(status_code=503, detail="No model loaded. Send a request with a model.")

    if state.idle_timer is None:
        state.start_idle_tracking(state.config.daemon.idle_timeout)

    state.touch()
    return await _proxy(request, f"/v1/{path}", raw_body, payload)
