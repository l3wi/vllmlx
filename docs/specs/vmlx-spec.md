# Technical Specification: vllmlx

**Status:** Draft  
**ADRs:** [ADR-0001: Embed MLX-VLM](../decisions/ADR-0001-embed-mlx-vlm.md)  
**PRD:** [docs/prds/vllmlx.md](../prds/vllmlx.md)  
**Date:** 2026-01-30  

---

## Overview

vllmlx is an Ollama-style CLI wrapper for MLX-VLM that provides:
- A persistent daemon with OpenAI-compatible API
- Simple model management (pull, list, remove)
- Interactive chat interface
- Automatic model loading/unloading with idle timeout

### Terminology

| Term | Definition |
|------|------------|
| **Daemon** | Background launchd-managed process running the API server |
| **Model alias** | Short name mapping to full HuggingFace path (e.g., `qwen2-vl-7b-instruct-4bit` → `mlx-community/Qwen2-VL-7B-Instruct-4bit`) |
| **Hot-swap** | Unloading current model and loading a different one on demand |
| **Idle timeout** | Duration after which loaded model is unloaded to free RAM |
| **HF cache** | HuggingFace Hub's local model cache at `~/.cache/huggingface/hub/` |

---

## Background & Context

### Current State (MLX-VLM)

MLX-VLM provides:
- `python -m mlx_vlm.server` - FastAPI server on port 8000
- `/generate` endpoint - native API with model, prompt, image, audio support
- `/responses` endpoint - OpenAI-compatible chat completions
- Dynamic model loading - server loads requested model on first use
- Single model caching - keeps one model loaded at a time

**Gaps:**
- No daemon management (manual start/stop)
- No model aliasing (must use full HF paths)
- No CLI for model management
- No idle unloading (model stays in RAM forever)
- No interactive chat command

### Constraints

- macOS only (launchd, Apple Silicon)
- Python 3.12+ (MLX requirement)
- Must use HuggingFace Hub for model storage (no custom registry)
- Must wrap (not fork) MLX-VLM to stay current with upstream

---

## Goals

### Product Goals (from PRD)
- Zero-friction local VLM API - always available after install
- Ollama-familiar CLI UX
- Minimal resource usage when idle

### Technical Goals
- Clean separation: CLI ↔ Daemon ↔ MLX-VLM
- Single source of truth for config (`~/.vllmlx/config.toml`)
- Graceful degradation (daemon down → helpful error messages)
- Extensible alias registry

### Non-Goals
- Windows/Linux support
- Custom model hosting (HuggingFace only)
- Multi-model concurrent loading (hot-swap only)
- Fine-tuning or training features

---

## Proposed Solution

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                          vllmlx CLI                               │
│   pull | ls | rm | run | serve | daemon | config                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ HTTP (localhost:8000)
                              │ Unix socket (~/.vllmlx/vllmlx.sock)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       vllmlx Daemon                               │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────────┐  │
│  │ API Router  │  │ Model Manager │  │ Idle Timer           │  │
│  │ (FastAPI)   │  │ - load/unload │  │ - tracks last request │  │
│  │             │  │ - alias resolve│  │ - triggers unload    │  │
│  └─────────────┘  └──────────────┘  └───────────────────────┘  │
│                              │                                  │
│                              ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    MLX-VLM Core                          │   │
│  │   load() | generate() | processor                        │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    HuggingFace Hub Cache                        │
│                  ~/.cache/huggingface/hub/                      │
└─────────────────────────────────────────────────────────────────┘
```

### Component Design

#### 1. CLI (`vllmlx/cli/`)

**Technology:** `click` (simple, well-known, fewer dependencies than `typer`)

**Commands:**

| Command | Action |
|---------|--------|
| `vllmlx pull <model>` | Download model via `huggingface_hub.snapshot_download()` |
| `vllmlx ls` | List models from HF cache + alias resolution |
| `vllmlx rm <model>` | Remove model via `huggingface_hub.scan_cache_dir().delete_revisions()` |
| `vllmlx run <model>` | Start interactive chat (calls daemon API) |
| `vllmlx serve` | Run server in foreground (for development) |
| `vllmlx daemon status` | Check daemon via socket/pidfile |
| `vllmlx daemon start` | Install + load launchd plist |
| `vllmlx daemon stop` | Unload launchd plist |
| `vllmlx daemon restart` | Stop + start |
| `vllmlx daemon logs` | Tail `~/.vllmlx/logs/daemon.log` |
| `vllmlx config` | Show current config |
| `vllmlx config set <key> <value>` | Update config.toml |

**CLI ↔ Daemon Communication:**
- Primary: HTTP to `localhost:8000`
- Health check: Unix socket at `~/.vllmlx/vllmlx.sock` (faster, no port conflicts)

#### 2. Daemon (`vllmlx/daemon/`)

**Technology:** FastAPI + uvicorn (matches MLX-VLM's stack)

**Responsibilities:**
- Serve OpenAI-compatible API on port 8000
- Manage model lifecycle (load, unload, hot-swap)
- Track idle time and unload after timeout
- Write logs to `~/.vllmlx/logs/`
- Expose health and `/v1/status` endpoints

**Process Model:**
- Single Python process embedding MLX-VLM
- Not a subprocess wrapper - direct import for efficiency
- Uses `asyncio` for concurrent request handling

**Key Endpoints:**

| Endpoint | Purpose |
|----------|---------|
| `GET /v1/models` | List available models |
| `POST /v1/chat/completions` | OpenAI-compatible chat (main API) |
| `GET /health` | Health check for launchd/monitoring |
| `GET /v1/status` | Extended status (loaded model, RAM, uptime) |
| `POST /_internal/unload` | Force model unload (internal) |

#### 3. Model Manager (`vllmlx/models/`)

**Responsibilities:**
- Resolve aliases to full HF paths
- Track which models are downloaded (scan HF cache)
- Load/unload models via MLX-VLM's `load()` function
- Handle hot-swap requests with proper cleanup

**Alias Registry:**

```python
# vllmlx/models/aliases.py
BUILTIN_ALIASES = {
    "qwen2-vl-2b-instruct-4bit": "mlx-community/Qwen2-VL-2B-Instruct-4bit",
    "qwen2-vl-7b-instruct-4bit": "mlx-community/Qwen2-VL-7B-Instruct-4bit",
    "qwen2.5-vl-3b": "mlx-community/Qwen2.5-VL-3B-Instruct-4bit",
    "qwen2.5-vl-7b": "mlx-community/Qwen2.5-VL-7B-Instruct-4bit",
    "qwen2.5-vl-32b": "mlx-community/Qwen2.5-VL-32B-Instruct-8bit",
    "qwen2.5-vl-72b": "mlx-community/Qwen2.5-VL-72B-Instruct-4bit",
    "pixtral-12b-4bit": "mlx-community/pixtral-12b-4bit",
    "llava-qwen-0.5b": "mlx-community/llava-interleave-qwen-0.5b-bf16",
    "llava-qwen-7b": "mlx-community/llava-interleave-qwen-7b-4bit",
}
```

Custom aliases loaded from `~/.vllmlx/config.toml` override builtins.

#### 4. Idle Timer (`vllmlx/daemon/idle.py`)

**Mechanism:**
- Track timestamp of last API request
- Background asyncio task checks every 10 seconds
- If `now - last_request > timeout`: unload model
- Timeout configurable (default 60s)

**State Transitions:**
```
[No Model] --request--> [Loading] --done--> [Loaded] --timeout--> [Unloading] --done--> [No Model]
                                      ^                                |
                                      |______request__________________|
```

#### 5. Configuration (`vllmlx/config/`)

**File:** `~/.vllmlx/config.toml`

```toml
[daemon]
port = 8000
host = "127.0.0.1"
idle_timeout = 60  # seconds
log_level = "info"

[models]
default = ""  # optional default model for `vllmlx run` without args

[aliases]
# Custom aliases (override builtins)
# my-model = "some-org/some-model-4bit"
```

**Programmatic Access:**
```python
from vllmlx.config import Config

config = Config.load()  # from ~/.vllmlx/config.toml
config.daemon.port  # 8000
config.resolve_alias("qwen2-vl-7b-instruct-4bit")  # "mlx-community/Qwen2-VL-7B-Instruct-4bit"
```

#### 6. launchd Integration (`vllmlx/daemon/launchd.py`)

**Plist Location:** `~/Library/LaunchAgents/com.vllmlx.daemon.plist`

**Generated Plist:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.vllmlx.daemon</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python_path}</string>
        <string>-m</string>
        <string>vllmlx.daemon</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>
    <key>StandardOutPath</key>
    <string>{home}/.vllmlx/logs/daemon.log</string>
    <key>StandardErrorPath</key>
    <string>{home}/.vllmlx/logs/daemon.error.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>{path}</string>
    </dict>
</dict>
</plist>
```

**Commands:**
```python
def install_daemon():
    """Write plist and load with launchctl."""
    write_plist()
    subprocess.run(["launchctl", "load", plist_path])

def uninstall_daemon():
    """Unload and remove plist."""
    subprocess.run(["launchctl", "unload", plist_path])
    os.remove(plist_path)
```

---

## Data Models

### Config Schema

```python
from pydantic import BaseModel
from typing import Optional

class DaemonConfig(BaseModel):
    port: int = 8000
    host: str = "127.0.0.1"
    idle_timeout: int = 60
    log_level: str = "info"

class ModelsConfig(BaseModel):
    default: Optional[str] = None

class Config(BaseModel):
    daemon: DaemonConfig = DaemonConfig()
    models: ModelsConfig = ModelsConfig()
    aliases: dict[str, str] = {}
```

### Model Info

```python
class ModelInfo(BaseModel):
    """Information about a downloaded model."""
    name: str              # Alias or full HF path
    hf_path: str           # Full HuggingFace path
    size_bytes: int        # Size on disk
    last_used: Optional[datetime]  # From access time
    is_loaded: bool        # Currently in memory
```

### Daemon Status

```python
class DaemonStatus(BaseModel):
    """Status response from /v1/status endpoint."""
    running: bool
    pid: int
    uptime_seconds: float
    loaded_model: Optional[str]
    model_loaded_at: Optional[datetime]
    last_request_at: Optional[datetime]
    memory_usage_mb: float
    idle_timeout: int
```

---

## API Design

### OpenAI-Compatible Endpoints

These mirror OpenAI's API for drop-in compatibility:

#### GET /v1/models

```json
{
  "object": "list",
  "data": [
    {
      "id": "qwen2-vl-7b-instruct-4bit",
      "object": "model",
      "created": 1706745600,
      "owned_by": "mlx-community"
    }
  ]
}
```

#### POST /v1/chat/completions

**Request:**
```json
{
  "model": "qwen2-vl-7b-instruct-4bit",
  "messages": [
    {
      "role": "user",
      "content": [
        {"type": "text", "text": "What's in this image?"},
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}}
      ]
    }
  ],
  "max_tokens": 500,
  "temperature": 0.7,
  "stream": true
}
```

**Response (streaming):**
```
data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1706745600,"model":"qwen2-vl-7b-instruct-4bit","choices":[{"index":0,"delta":{"content":"The"},"finish_reason":null}]}

data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1706745600,"model":"qwen2-vl-7b-instruct-4bit","choices":[{"index":0,"delta":{"content":" image"},"finish_reason":null}]}

data: [DONE]
```

### Internal Endpoints

#### GET /health

```json
{"status": "ok"}
```

#### GET /v1/status

```json
{
  "running": true,
  "pid": 12345,
  "uptime_seconds": 3600.5,
  "loaded_model": "qwen2-vl-7b-instruct-4bit",
  "model_loaded_at": "2026-01-30T14:00:00Z",
  "last_request_at": "2026-01-30T14:55:00Z",
  "memory_usage_mb": 4500.2,
  "idle_timeout": 60
}
```

#### POST /_internal/unload

Force unload current model (used by `vllmlx daemon restart`).

```json
{"success": true, "unloaded_model": "qwen2-vl-7b-instruct-4bit"}
```

---

## Alternative Approaches

### Option A: Subprocess Wrapper (Rejected)

**Approach:** Launch `mlx_vlm.server` as subprocess, proxy requests.

**Pros:**
- Zero coupling to MLX-VLM internals
- Easy to update MLX-VLM independently

**Cons:**
- Can't implement idle unloading (no control over model state)
- Extra process overhead
- Harder to implement hot-swap
- IPC complexity

**Decision:** Rejected - idle unloading is a P0 requirement.

### Option B: Fork MLX-VLM Server (Rejected)

**Approach:** Fork and modify MLX-VLM's server code directly.

**Pros:**
- Full control over all behavior
- Can optimize deeply

**Cons:**
- Maintenance burden - must track upstream changes
- License considerations
- Divergence over time

**Decision:** Rejected - prefer clean wrapper that imports MLX-VLM as library.

### Option C: Embed MLX-VLM (Selected)

**Approach:** Import MLX-VLM's `load()` and `generate()` functions, build custom server around them.

**Pros:**
- Full control over model lifecycle
- Can implement idle unloading
- Uses MLX-VLM as intended (library)
- Automatic compatibility with MLX-VLM updates

**Cons:**
- Tied to MLX-VLM's internal API (may change)
- Must handle generation streaming ourselves

**Decision:** Selected - best balance of control and maintainability.

---

## Further Considerations

### Security

| Concern | Mitigation |
|---------|------------|
| API exposed to network | Default bind to `127.0.0.1` only |
| Arbitrary model execution | Models only from HuggingFace (trusted source) |
| Config file tampering | Standard Unix permissions on `~/.vllmlx/` |
| Log file exposure | Logs contain prompts - user's responsibility |

### Performance

| Metric | Target | Approach |
|--------|--------|----------|
| Cold start (no model) | <2s | Daemon starts without loading model |
| Model load time | MLX-VLM baseline | Direct `load()` call, no overhead |
| Request latency (loaded) | <50ms overhead | Minimal wrapper code |
| Idle RAM (no model) | <50MB | Unload model completely via `del` + `gc.collect()` + `mx.metal.clear_cache()` |

### Reliability

| Scenario | Handling |
|----------|----------|
| Daemon crash | launchd auto-restarts (KeepAlive) |
| Model load failure | Return 503 with error message, don't crash |
| Concurrent requests during hot-swap | Queue requests, respond after swap completes |
| Disk full during pull | Catch exception, clean partial download, report error |
| HuggingFace unavailable | Clear error message, suggest retry |

### Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| `mlx-vlm` | >=0.1.0 | Core VLM inference |
| `click` | >=8.0 | CLI framework |
| `fastapi` | >=0.100 | API server |
| `uvicorn` | >=0.20 | ASGI server |
| `pydantic` | >=2.0 | Data validation |
| `toml` | >=0.10 | Config parsing |
| `huggingface_hub` | >=0.20 | Model downloads |
| `rich` | >=13.0 | CLI output formatting |

---

## Implementation Plan

### Phase 1: Core Infrastructure (Foundation)

**Goal:** Basic project structure, config system, model management

**Tasks:**
- Project scaffolding (pyproject.toml, src layout)
- Config module (`~/.vllmlx/config.toml` read/write)
- Model alias registry (builtin + custom)
- HuggingFace integration (list, download, delete models)
- CLI skeleton with `pull`, `ls`, `rm` commands

**Deliverables:**
- `vllmlx pull qwen2-vl-2b-instruct-4bit` downloads model
- `vllmlx ls` shows downloaded models
- `vllmlx rm qwen2-vl-2b-instruct-4bit` removes model
- `vllmlx config` shows config

**Tests:**
- Config load/save roundtrip
- Alias resolution (builtin, custom, full path)
- Model list matches HF cache

### Phase 2: Daemon & API Server

**Goal:** Working daemon with OpenAI-compatible API

**Tasks:**
- FastAPI server with `/v1/chat/completions`, `/v1/models`
- Model loading via MLX-VLM `load()`
- Generation via MLX-VLM `generate()`
- Streaming response support
- Hot-swap model loading
- Health and `/v1/status` endpoints
- `vllmlx serve` command (foreground server)

**Deliverables:**
- `vllmlx serve` starts server on :8000
- `curl localhost:8000/v1/models` returns models
- Chat completions work with image input
- Model hot-swap on different model request

**Tests:**
- API response format matches OpenAI spec
- Streaming works correctly
- Hot-swap doesn't leak memory

### Phase 3: Idle Management & Polish

**Goal:** Idle timeout, memory cleanup, error handling

**Tasks:**
- Idle timer implementation
- Model unloading with memory cleanup
- Graceful request queuing during transitions
- Error handling for all failure modes
- Logging infrastructure

**Deliverables:**
- Model unloads after 60s idle
- RAM returns to baseline after unload
- Concurrent requests during swap are handled
- Comprehensive error messages

**Tests:**
- Idle timeout triggers unload
- Memory measurement before/after unload
- Concurrent request handling

### Phase 4: launchd Integration

**Goal:** Persistent daemon with auto-start

**Tasks:**
- Plist generation
- `vllmlx daemon start|stop|restart|status|logs` commands
- Post-install hook to offer daemon setup
- Graceful shutdown handling (SIGTERM)

**Deliverables:**
- `vllmlx daemon start` installs and starts daemon
- Daemon survives reboot
- `vllmlx daemon logs` tails log file
- Clean shutdown on `stop`

**Tests:**
- Daemon starts on `launchctl load`
- Daemon restarts after crash
- Logs written correctly

### Phase 5: Interactive Chat

**Goal:** Simple REPL chat interface

**Tasks:**
- `vllmlx run <model>` command
- Simple `>` prompt with readline
- Streaming output display
- Ctrl+C handling
- History support (optional)

**Deliverables:**
- `vllmlx run qwen2-vl-7b-instruct-4bit` starts chat
- Responses stream to terminal
- Clean exit on Ctrl+C

**Tests:**
- Basic chat flow works
- Streaming displays correctly

### Phase 6: Documentation & Release

**Goal:** Ready for public release

**Tasks:**
- README with quick start
- CLI help text for all commands
- Installation guide (uv, pip)
- Troubleshooting guide
- PyPI package publishing
- GitHub release

**Deliverables:**
- Published to PyPI as `vllmlx`
- Complete documentation
- GitHub repo with CI

---

## Testing Strategy

### Unit Tests (70%)
- Config parsing/serialization
- Alias resolution
- Model info extraction from HF cache
- Plist generation
- Idle timer logic

### Integration Tests (20%)
- CLI commands against real HF cache
- API endpoints against running server
- Model load/unload cycles
- launchd integration (macOS CI)

### E2E Tests (10%)
- Full workflow: install → pull → reboot → API works
- Interactive chat session
- Model hot-swap under load

### Test Infrastructure
- `pytest` with `pytest-asyncio` for async tests
- `httpx` for API testing
- Mock HF cache for fast unit tests
- Real model tests marked slow (optional in CI)

---

## Success Criteria

### Acceptance Criteria (from PRD)

- [ ] `uv tool install vllmlx` succeeds
- [ ] `vllmlx pull qwen2-vl-2b-instruct-4bit` downloads model
- [ ] After reboot, `curl localhost:8000/v1/models` works without manual intervention
- [ ] `vllmlx ls` shows model name, size
- [ ] `vllmlx rm` removes model
- [ ] `vllmlx run` provides interactive chat
- [ ] Model unloads after idle timeout
- [ ] Daemon process uses <50MB RAM when no model loaded

### Performance Benchmarks

| Metric | Target |
|--------|--------|
| Daemon startup (no model) | <2s |
| Model load time (7B 4-bit) | <15s |
| First token latency (loaded) | <100ms |
| Idle RAM (no model) | <50MB |
| RAM after unload vs before load | Within 100MB |

---

## Implementation Details

**Feature Branch:** `feat/vllmlx`  
**Base Branch:** `main`

This feature will be implemented using the feature branch orchestration pattern:
1. All phase branches created from `feat/vllmlx`
2. Phases merge back to `feat/vllmlx`
3. Single PR from `feat/vllmlx` to `main` when complete

---

## Open Questions (Resolved)

| Question | Resolution |
|----------|------------|
| Alias registry format | Python dict in code + TOML overrides |
| Multiple simultaneous models | Not supported - hot-swap only |
| Health endpoint format | Simple `{"status": "ok"}` |
| Log location | `~/.vllmlx/logs/daemon.log` |

---

## Appendix: Directory Structure

```
vllmlx/
├── pyproject.toml
├── README.md
├── src/
│   └── vllmlx/
│       ├── __init__.py
│       ├── __main__.py          # Entry point for `python -m vllmlx`
│       ├── cli/
│       │   ├── __init__.py
│       │   ├── main.py          # Click app
│       │   ├── pull.py
│       │   ├── ls.py
│       │   ├── rm.py
│       │   ├── run.py
│       │   ├── serve.py
│       │   ├── daemon.py
│       │   └── config.py
│       ├── daemon/
│       │   ├── __init__.py
│       │   ├── server.py        # FastAPI app
│       │   ├── routes.py        # API endpoints
│       │   ├── idle.py          # Idle timer
│       │   ├── launchd.py       # Plist management
│       │   └── state.py         # Daemon state
│       ├── models/
│       │   ├── __init__.py
│       │   ├── aliases.py       # Builtin aliases
│       │   ├── manager.py       # Load/unload logic
│       │   └── registry.py      # HF cache scanning
│       └── config/
│           ├── __init__.py
│           └── config.py        # Config loading/saving
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
└── docs/
    ├── prds/
    └── specs/
```
