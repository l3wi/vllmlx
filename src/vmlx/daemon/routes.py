"""API routes for vmlx daemon."""

import json
import os
import time
import uuid
from datetime import datetime
from typing import AsyncGenerator, List, Optional, Union

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter()


# =============================================================================
# Request/Response Models
# =============================================================================


class ImageUrl(BaseModel):
    """Image URL specification."""

    url: str


class ImageUrlContent(BaseModel):
    """Content with image URL."""

    type: str = "image_url"
    image_url: ImageUrl


class TextContent(BaseModel):
    """Content with text."""

    type: str = "text"
    text: str


class Message(BaseModel):
    """Chat message."""

    role: str
    content: Union[str, List[Union[TextContent, ImageUrlContent, dict]]]


class ChatCompletionRequest(BaseModel):
    """Request for chat completion."""

    model: str
    messages: List[Message]
    max_tokens: Optional[int] = 512
    temperature: Optional[float] = 0.7
    stream: Optional[bool] = False


class ModelData(BaseModel):
    """Model information."""

    id: str
    object: str = "model"
    created: int
    owned_by: str


class ModelListResponse(BaseModel):
    """Response for list models endpoint."""

    object: str = "list"
    data: List[ModelData]


class ChatCompletionChoice(BaseModel):
    """Choice in chat completion response."""

    index: int
    message: dict
    finish_reason: Optional[str] = "stop"


class ChatCompletionUsage(BaseModel):
    """Usage statistics for chat completion."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionResponse(BaseModel):
    """Response for chat completion."""

    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatCompletionChoice]
    usage: ChatCompletionUsage = ChatCompletionUsage()


class DaemonStatusResponse(BaseModel):
    """Response for daemon status endpoint."""

    running: bool
    pid: int
    uptime_seconds: float
    loaded_model: Optional[str]
    model_loaded_at: Optional[str]
    last_request_at: Optional[str]
    idle_seconds_remaining: Optional[float]
    memory_usage_mb: float
    idle_timeout: int


# =============================================================================
# Helper Functions
# =============================================================================


def extract_content(messages: List[Message]) -> tuple[str, list[str]]:
    """Extract text prompt and images from messages.

    Args:
        messages: List of chat messages

    Returns:
        Tuple of (text_prompt, list_of_image_urls)
    """
    prompt_parts = []
    images = []

    for msg in messages:
        if isinstance(msg.content, str):
            prompt_parts.append(f"{msg.role}: {msg.content}")
        elif isinstance(msg.content, list):
            for part in msg.content:
                if isinstance(part, dict):
                    if part.get("type") == "text":
                        prompt_parts.append(f"{msg.role}: {part['text']}")
                    elif part.get("type") == "image_url":
                        url = part.get("image_url", {}).get("url", "")
                        if url:
                            images.append(url)
                elif hasattr(part, "type"):
                    if part.type == "text":
                        prompt_parts.append(f"{msg.role}: {part.text}")
                    elif part.type == "image_url":
                        images.append(part.image_url.url)

    return "\n".join(prompt_parts), images


def format_completion_response(model: str, content: str, request_id: str) -> ChatCompletionResponse:
    """Format response as OpenAI-compatible chat completion.

    Args:
        model: Model name
        content: Generated content
        request_id: Unique request ID

    Returns:
        Formatted ChatCompletionResponse
    """
    return ChatCompletionResponse(
        id=request_id,
        created=int(time.time()),
        model=model,
        choices=[
            ChatCompletionChoice(
                index=0,
                message={"role": "assistant", "content": content},
                finish_reason="stop",
            )
        ],
    )


async def stream_response(
    model: str,
    request_id: str,
    generator,
) -> AsyncGenerator[str, None]:
    """Stream response in OpenAI SSE format.

    Args:
        model: Model name
        request_id: Unique request ID
        generator: Token generator

    Yields:
        SSE formatted chunks
    """
    for token in generator:
        chunk = {
            "id": request_id,
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": token},
                    "finish_reason": None,
                }
            ],
        }
        yield f"data: {json.dumps(chunk)}\n\n"

    # Send final chunk with finish_reason
    final_chunk = {
        "id": request_id,
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": {},
                "finish_reason": "stop",
            }
        ],
    }
    yield f"data: {json.dumps(final_chunk)}\n\n"
    yield "data: [DONE]\n\n"


def get_memory_usage_mb() -> float:
    """Get current process memory usage in MB."""
    try:
        import psutil

        process = psutil.Process(os.getpid())
        return process.memory_info().rss / (1024 * 1024)
    except ImportError:
        # psutil not available, return 0
        return 0.0


# =============================================================================
# API Endpoints
# =============================================================================


@router.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}


@router.get("/v1/models", response_model=ModelListResponse)
async def list_models():
    """List available models."""
    from vmlx.models.registry import list_models

    models = list_models()
    return ModelListResponse(
        data=[
            ModelData(
                id=m.name,
                created=int(m.last_modified.timestamp()) if m.last_modified else 0,
                owned_by=m.hf_path.split("/")[0] if "/" in m.hf_path else "unknown",
            )
            for m in models
        ]
    )


@router.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    """Create chat completion (OpenAI-compatible)."""
    from vmlx.config import Config
    from vmlx.daemon.state import get_state
    from vmlx.models.aliases import resolve_alias
    from vmlx.models.manager import ModelManager

    state = get_state()
    config = Config.load()

    # Resolve model alias to full path
    model_path = resolve_alias(request.model, config.aliases)
    request_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"

    # Acquire lock for model loading/swapping
    async with state.lock:
        # Hot-swap if different model requested
        if state.loaded_model_name != model_path:
            if state.model is not None:
                # Stop old idle tracking before unloading
                state.stop_idle_tracking()
                ModelManager.unload_model(state.model, state.processor)
                state.reset_model_state()

            try:
                model, processor, model_config = ModelManager.load_model(model_path)
                state.model = model
                state.processor = processor
                state.config = model_config
                state.loaded_model_name = model_path
                state.loaded_at = datetime.now()

                # Start idle tracking after successful load
                state.start_idle_tracking(config.daemon.idle_timeout)
            except Exception as e:
                raise HTTPException(
                    status_code=503,
                    detail=f"Failed to load model '{model_path}': {str(e)}",
                )

        state.touch()

    # Extract prompt and images from messages
    prompt, images = extract_content(request.messages)

    if request.stream:
        # Streaming response
        generator = ModelManager.generate_streaming(
            state.model,
            state.processor,
            state.config,
            prompt,
            images=images if images else None,
            max_tokens=request.max_tokens or 512,
            temperature=request.temperature or 0.7,
        )
        return StreamingResponse(
            stream_response(request.model, request_id, generator),
            media_type="text/event-stream",
        )
    else:
        # Non-streaming response
        response = ModelManager.generate_response(
            state.model,
            state.processor,
            state.config,
            prompt,
            images=images if images else None,
            max_tokens=request.max_tokens or 512,
            temperature=request.temperature or 0.7,
            stream=False,
        )
        return format_completion_response(request.model, response, request_id)


@router.get("/status", response_model=DaemonStatusResponse)
async def daemon_status():
    """Get daemon status including loaded model and memory usage."""
    from vmlx.config import Config
    from vmlx.daemon.state import get_state

    state = get_state()
    config = Config.load()
    now = datetime.now()

    # Get idle seconds remaining from timer if running
    idle_seconds_remaining = None
    if state.idle_timer:
        idle_seconds_remaining = state.idle_timer.seconds_until_timeout

    return DaemonStatusResponse(
        running=True,
        pid=os.getpid(),
        uptime_seconds=(now - state.start_time).total_seconds(),
        loaded_model=state.loaded_model_name,
        model_loaded_at=state.loaded_at.isoformat() if state.loaded_at else None,
        last_request_at=state.last_request_at.isoformat() if state.last_request_at else None,
        idle_seconds_remaining=idle_seconds_remaining,
        memory_usage_mb=get_memory_usage_mb(),
        idle_timeout=config.daemon.idle_timeout,
    )


@router.post("/_internal/unload")
async def internal_unload():
    """Force unload current model (internal endpoint)."""
    from vmlx.daemon.state import get_state
    from vmlx.models.manager import ModelManager

    state = get_state()

    async with state.lock:
        if state.model is not None:
            unloaded_model = state.loaded_model_name
            # Stop idle tracking before unloading
            state.stop_idle_tracking()
            ModelManager.unload_model(state.model, state.processor)
            state.reset_model_state()
            return {"success": True, "unloaded_model": unloaded_model}
        else:
            return {"success": True, "unloaded_model": None}
