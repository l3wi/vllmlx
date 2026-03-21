# PRD: vllmlx - Ollama-style CLI for MLX-VLM

**Status:** Approved  
**Author:** lewi  
**Date:** 2026-01-30  

---

## Problem Statement

MLX-VLM provides powerful Vision Language Model inference on Apple Silicon, but lacks the developer experience that made Ollama successful. Currently, using MLX-VLM requires:

1. Manually starting a server process each session
2. Remembering full HuggingFace model paths (`mlx-community/Qwen2-VL-7B-Instruct-4bit`)
3. No persistent daemon - API unavailable after reboot until manually restarted
4. No unified model management (pull, list, remove)
5. No simple interactive chat interface

**Impact:** Casual inference users who want local multi-modal AI on Mac face unnecessary friction. The power of Metal-accelerated VLMs is locked behind poor UX.

---

## Users & Use Cases

### Primary User
- **Developer/power user** wanting local VLM inference on Apple Silicon
- Familiar with terminal, comfortable with CLI tools
- Wants "set and forget" - install once, always available
- May integrate with other apps via OpenAI-compatible API

### Use Cases

1. **Background API consumer**: Apps like Open WebUI, Continue.dev, or custom scripts hit `localhost:11434` expecting an LLM API - vllmlx daemon serves this 24/7
2. **Quick model experimentation**: `vllmlx pull pixtral-12b && vllmlx run pixtral-12b` to try a new model
3. **Model hygiene**: `vllmlx ls` to see disk usage, `vllmlx rm` to clean up unused models

---

## Goals

### Primary Goal
**Zero-friction local VLM API** - After install and first `pull`, the OpenAI-compatible API is always available at `localhost:11434` without manual intervention.

### Secondary Goals
- Ollama-familiar CLI UX (`pull`, `ls`, `rm`, `run`, `serve`)
- Model aliasing for human-friendly names (`qwen2-vl-7b` not full HF path)
- Minimal resource usage when idle (unload model after timeout)
- Open source for community contribution

---

## Assumptions

### Technical
- Users have Apple Silicon Mac (M1/M2/M3/M4)
- macOS 13+ (for modern launchd features)
- Python 3.12+ available (recommend `uv tool install`)
- MLX-VLM's built-in FastAPI server provides OpenAI-compatible endpoints
- HuggingFace Hub handles model downloads and caching

### User Behavior
- Users will primarily interact via API, not CLI chat
- Model switching is infrequent (most users stick to 1-2 models)
- Users accept ~10-30s cold start when model needs loading

### Business
- Open source project, no monetization goals
- Community will contribute model aliases over time

---

## Scope

### In Scope (v1)

- [x] **Daemon**: launchd-managed background service, auto-starts on login
- [x] **OpenAI-compatible API**: `/v1/chat/completions` with image support at port 11434
- [x] **CLI: `vllmlx pull <model>`**: Download model from HuggingFace
- [x] **CLI: `vllmlx ls`**: List downloaded models with size info
- [x] **CLI: `vllmlx rm <model>`**: Remove downloaded model
- [x] **CLI: `vllmlx run <model>`**: Interactive `>` prompt chat session
- [x] **CLI: `vllmlx serve`**: Manual server start (for debugging/development)
- [x] **CLI: `vllmlx daemon status|restart|stop`**: Daemon management
- [x] **Model aliasing**: `qwen2-vl-7b` → `mlx-community/Qwen2-VL-7B-Instruct-4bit`
- [x] **Built-in alias registry**: Ship with popular MLX-VLM models pre-aliased
- [x] **Hot-swap models**: Unload current model, load requested model on demand
- [x] **Idle unload**: Unload model after configurable timeout (default 1 min)
- [x] **Config file**: `~/.vllmlx/config.toml` for settings
- [x] **Graceful concurrent requests**: Handle multiple model requests sensibly

### Out of Scope (v1)

- ❌ **Fine-tuning/LoRA training** - use MLX-VLM directly
- ❌ **Video analysis** - future version
- ❌ **Audio input** - future version  
- ❌ **Quantization tools** - use MLX-VLM directly
- ❌ **Image input in CLI chat** - API only for images
- ❌ **TUI with image preview** - simple `>` prompt only
- ❌ **Custom alias management CLI** - edit config file manually
- ❌ **Brew installation** - pip only for v1
- ❌ **Linux/Windows support** - macOS only

---

## User Stories

### US1: First-time Setup
**As a** new user  
**I want to** install vllmlx and pull my first model  
**So that** I have a working local VLM API  

**Acceptance Criteria:**
- `uv tool install vllmlx` succeeds
- `vllmlx pull qwen2-vl-2b` downloads model to HF cache
- `vllmlx daemon status` shows daemon running
- `curl localhost:11434/v1/models` returns available models

### US2: Persistent API Access
**As a** developer with apps that need LLM APIs  
**I want** the API to survive reboots  
**So that** my apps don't break when I restart my Mac  

**Acceptance Criteria:**
- Reboot Mac
- Without any manual intervention, `curl localhost:11434/v1/models` works
- First `/v1/chat/completions` request loads model and responds

### US3: Model Management
**As a** user with limited disk space  
**I want to** see what models I have and remove unused ones  
**So that** I can manage storage  

**Acceptance Criteria:**
- `vllmlx ls` shows model name, size, last used
- `vllmlx rm pixtral-12b` removes model and frees disk space
- Removed model no longer appears in `vllmlx ls`

### US4: Interactive Chat
**As a** user who wants quick model testing  
**I want** a simple chat interface  
**So that** I can test prompts without writing code  

**Acceptance Criteria:**
- `vllmlx run qwen2-vl-7b` starts interactive session
- Simple `>` prompt accepts text input
- Responses stream to terminal
- Ctrl+C exits cleanly

### US5: Resource Efficiency
**As a** user running vllmlx alongside other apps  
**I want** minimal resource usage when idle  
**So that** my Mac stays responsive  

**Acceptance Criteria:**
- Model unloads after 1 minute of inactivity (configurable)
- Daemon process uses <50MB RAM when no model loaded
- No significant battery impact when idle

### US6: Model Hot-Swap
**As a** user with multiple models  
**I want** to switch models via API request  
**So that** I don't need to manually restart anything  

**Acceptance Criteria:**
- Request to model A while model B is loaded triggers hot-swap
- Model B unloads, model A loads
- Response returns from model A
- Concurrent requests during swap are queued, not rejected

---

## Success Metrics

| Metric | Baseline | Target | Measurement |
|--------|----------|--------|-------------|
| Setup-to-working-API time | N/A (no tool exists) | <5 minutes | Time from `pip install` to successful API call |
| Post-reboot API availability | Manual start required | Automatic | API responds without user action after reboot |
| Idle RAM usage | N/A | <50MB | Activity Monitor when no model loaded |
| Cold model load time | MLX-VLM baseline | Same as MLX-VLM | Time from request to first token |
| Model switch time | N/A | <30s for 7B model | Time from request to model A while B loaded |

---

## Open Questions

1. **Alias registry format**: JSON file shipped with package? Fetched from GitHub?
2. **Multiple simultaneous models**: Worth supporting if RAM allows, or always single-model?
3. **Health check endpoint**: `/health` for monitoring? What should it return?
4. **Logging**: Where to write daemon logs? `~/.vllmlx/logs/`? 

---

## Appendix: Model Alias Examples

| Alias | HuggingFace Path |
|-------|------------------|
| `qwen2-vl-2b` | `mlx-community/Qwen2-VL-2B-Instruct-4bit` |
| `qwen2-vl-7b` | `mlx-community/Qwen2-VL-7B-Instruct-4bit` |
| `qwen2.5-vl-32b` | `mlx-community/Qwen2.5-VL-32B-Instruct-8bit` |
| `pixtral-12b` | `mlx-community/pixtral-12b-4bit` |
| `llava-qwen-0.5b` | `mlx-community/llava-interleave-qwen-0.5b-bf16` |

---

## Appendix: CLI Reference (Proposed)

```bash
# Model management
vllmlx pull <model>          # Download model (alias or full HF path)
vllmlx ls                    # List downloaded models
vllmlx rm <model>            # Remove model

# Interactive
vllmlx run <model>           # Start chat session with model

# Server
vllmlx serve                 # Start server manually (foreground)
vllmlx serve --port 8080     # Custom port

# Daemon
vllmlx daemon status         # Show daemon status
vllmlx daemon start          # Start daemon (usually automatic)
vllmlx daemon stop           # Stop daemon
vllmlx daemon restart        # Restart daemon
vllmlx daemon logs           # Tail daemon logs

# Config
vllmlx config                # Show current config
vllmlx config set timeout 5m # Set idle timeout
vllmlx config set port 8080  # Set default port
```

---

## Appendix: Config File (`~/.vllmlx/config.toml`)

```toml
[daemon]
port = 11434
idle_timeout = "1m"
auto_start = true

[models]
default = "qwen2-vl-7b"

[aliases]
# Custom aliases (in addition to built-in)
my-vision = "mlx-community/Some-Custom-Model-4bit"
```
