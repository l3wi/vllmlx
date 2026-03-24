# Task: Daemon & API Server

**Phase**: 2  
**Branch**: `feat/vllmlx-phase-2`  
**Plan**: [docs/plans/vllmlx.md](../plans/vllmlx.md)  
**Spec**: [docs/specs/vllmlx-spec.md](../specs/vllmlx-spec.md)  
**Status**: completed

---

## Objective

Build the core daemon with FastAPI server exposing OpenAI-compatible endpoints, model loading/unloading via MLX-VLM, and hot-swap capability.

---

## Acceptance Criteria

- [x] `vllmlx serve` starts FastAPI server on port 8000
- [x] `GET /health` returns `{"status": "ok"}`
- [x] `GET /v1/models` returns list of available models
- [x] `POST /v1/chat/completions` works with text-only messages
- [x] `POST /v1/chat/completions` works with image input (base64)
- [x] Streaming responses work (`stream: true`)
- [x] Model loads on first request automatically
- [x] Hot-swap: requesting different model unloads current, loads new
- [x] `GET /v1/status` returns daemon status (loaded model, memory, uptime)
- [x] Graceful shutdown on SIGTERM
- [x] All tests pass (71 tests)
- [x] Lint clean

---

## Files to Create

| File | Description |
|------|-------------|
| `src/vllmlx/daemon/__init__.py` | Daemon module init |
| `src/vllmlx/daemon/server.py` | FastAPI app setup, uvicorn runner |
| `src/vllmlx/daemon/routes.py` | API endpoint handlers |
| `src/vllmlx/daemon/state.py` | DaemonState class (loaded model, timestamps) |
| `src/vllmlx/models/manager.py` | ModelManager class (load, unload, generate) |
| `src/vllmlx/cli/serve.py` | `vllmlx serve` command |
| `tests/integration/__init__.py` | Integration tests package |
| `tests/integration/test_api.py` | API endpoint tests |

---

## Implementation Notes

### DaemonState (state.py)

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Any
import asyncio

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
        return self.model is not None

    def touch(self) -> None:
        """Update last request timestamp."""
        self.last_request_at = datetime.now()
```

### ModelManager (manager.py)

```python
import gc
from typing import Optional, Tuple, Any
from mlx_vlm import load, generate
from mlx_vlm.prompt_utils import apply_chat_template
from mlx_vlm.utils import load_config
import mlx.core as mx

class ModelManager:
    """Handles model loading, unloading, and generation."""

    @staticmethod
    def load_model(model_path: str) -> Tuple[Any, Any, Any]:
        """Load model, processor, and config from HuggingFace path."""
        model, processor = load(model_path)
        config = load_config(model_path)
        return model, processor, config

    @staticmethod
    def unload_model(model: Any, processor: Any) -> None:
        """Unload model and free memory."""
        del model
        del processor
        gc.collect()
        # Clear MLX metal cache
        if hasattr(mx.metal, 'clear_cache'):
            mx.metal.clear_cache()

    @staticmethod
    def generate_response(
        model: Any,
        processor: Any,
        config: Any,
        prompt: str,
        images: list[str] = None,
        max_tokens: int = 512,
        temperature: float = 0.7,
        stream: bool = False,
    ):
        """Generate response from model."""
        formatted_prompt = apply_chat_template(
            processor, config, prompt,
            num_images=len(images) if images else 0
        )
        
        if stream:
            # Return generator for streaming
            return generate(
                model, processor, formatted_prompt,
                images or [],
                max_tokens=max_tokens,
                temp=temperature,
                verbose=False,
            )
        else:
            # Return complete response
            return generate(
                model, processor, formatted_prompt,
                images or [],
                max_tokens=max_tokens,
                temp=temperature,
                verbose=False,
            )
```

### API Routes (routes.py)

```python
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Union
import json
import time

router = APIRouter()

class Message(BaseModel):
    role: str
    content: Union[str, List[dict]]

class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[Message]
    max_tokens: Optional[int] = 512
    temperature: Optional[float] = 0.7
    stream: Optional[bool] = False

@router.get("/health")
async def health():
    return {"status": "ok"}

@router.get("/v1/models")
async def list_models():
    # Return available models from registry
    from vllmlx.models.registry import list_models
    models = list_models()
    return {
        "object": "list",
        "data": [
            {
                "id": m.name,
                "object": "model",
                "created": int(m.last_modified.timestamp()) if m.last_modified else 0,
                "owned_by": m.hf_path.split("/")[0] if "/" in m.hf_path else "unknown"
            }
            for m in models
        ]
    }

@router.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    from vllmlx.daemon.state import get_state
    from vllmlx.models.manager import ModelManager
    from vllmlx.models.aliases import resolve_alias
    from vllmlx.config import Config

    state = get_state()
    config = Config.load()
    
    # Resolve model alias
    model_path = resolve_alias(request.model, config.aliases)
    
    async with state.lock:
        # Hot-swap if different model requested
        if state.loaded_model_name != model_path:
            if state.model is not None:
                ModelManager.unload_model(state.model, state.processor)
            
            state.model, state.processor, state.config = ModelManager.load_model(model_path)
            state.loaded_model_name = model_path
            state.loaded_at = datetime.now()
        
        state.touch()
    
    # Extract prompt and images from messages
    prompt, images = extract_content(request.messages)
    
    if request.stream:
        return StreamingResponse(
            stream_response(state, prompt, images, request),
            media_type="text/event-stream"
        )
    else:
        response = ModelManager.generate_response(
            state.model, state.processor, state.config,
            prompt, images,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
        )
        return format_completion_response(request.model, response)
```

### Server Setup (server.py)

```python
from fastapi import FastAPI
from contextlib import asynccontextmanager
import uvicorn
import signal

from vllmlx.daemon.routes import router
from vllmlx.daemon.state import init_state
from vllmlx.config import Config

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_state()
    yield
    # Shutdown - unload model if loaded
    from vllmlx.daemon.state import get_state
    from vllmlx.models.manager import ModelManager
    state = get_state()
    if state.model:
        ModelManager.unload_model(state.model, state.processor)

def create_app() -> FastAPI:
    app = FastAPI(title="vllmlx", lifespan=lifespan)
    app.include_router(router)
    return app

def run_server(host: str = "127.0.0.1", port: int = 8000):
    app = create_app()
    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    server.run()
```

### CLI serve command (serve.py)

```python
import click
from vllmlx.config import Config

@click.command()
@click.option("--port", default=None, type=int, help="Port to listen on")
@click.option("--host", default=None, help="Host to bind to")
def serve(port, host):
    """Start the vllmlx server in foreground."""
    from vllmlx.daemon.server import run_server
    
    config = Config.load()
    run_server(
        host=host or config.daemon.host,
        port=port or config.daemon.port,
    )
```

### OpenAI Message Format

Handle both simple and multimodal messages:

```python
def extract_content(messages: List[Message]) -> Tuple[str, List[str]]:
    """Extract text prompt and images from messages."""
    prompt_parts = []
    images = []
    
    for msg in messages:
        if isinstance(msg.content, str):
            prompt_parts.append(msg.content)
        elif isinstance(msg.content, list):
            for part in msg.content:
                if part.get("type") == "text":
                    prompt_parts.append(part["text"])
                elif part.get("type") == "image_url":
                    url = part["image_url"]["url"]
                    if url.startswith("data:"):
                        # Base64 encoded image
                        images.append(url)
                    else:
                        # URL or file path
                        images.append(url)
    
    return "\n".join(prompt_parts), images
```

---

## Testing Requirements

### Integration Tests (test_api.py)

Use `httpx` with `TestClient`:

```python
from fastapi.testclient import TestClient
from vllmlx.daemon.server import create_app

def test_health():
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_list_models():
    client = TestClient(create_app())
    response = client.get("/v1/models")
    assert response.status_code == 200
    assert "data" in response.json()

# Note: Full model load tests require downloaded model
# Mark as slow/optional for CI
```

---

## Agent Instructions

1. Read the full spec at `docs/specs/vllmlx-spec.md` for API details
2. Implement `DaemonState` class first
3. Implement `ModelManager` with MLX-VLM integration
4. Build FastAPI routes following OpenAI spec
5. Implement streaming response format
6. Add `vllmlx serve` CLI command
7. Write integration tests (mock model loading for fast tests)
8. Test manually with curl:
   ```bash
   vllmlx serve &
   curl localhost:8000/health
   curl localhost:8000/v1/models
   ```
9. Run `ruff check` and `pytest`
10. Commit with `wt commit`
