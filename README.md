# vllmlx

Ollama-style daemon and CLI for [vllm-mlx](https://github.com/waybarrios/vllm-mlx).

## Features

- 🚀 **Always-on daemon** - API available immediately after install, survives reboots
- 🎯 **Simple CLI** - `vllmlx pull`, `vllmlx run`, `vllmlx ls` - familiar Ollama-style commands
- 🔄 **Hot-swap models** - Switch models on-the-fly without restarting
- 💾 **Smart memory** - Auto-unloads models after idle timeout
- 🤖 **OpenAI-compatible API** - Works with existing tools at `localhost:11434`

## Quick Start

```bash
# Install
pip install vllmlx
# Or with uv (recommended)
uv tool install vllmlx

# Pull a model
vllmlx pull qwen2-vl-7b

# Start the daemon (auto-starts on login after this)
vllmlx daemon start

# Chat interactively
vllmlx run qwen2-vl-7b

# Or use the API
curl http://localhost:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen2-vl-7b",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

## Requirements

- macOS 13+ (Apple Silicon)
- Python 3.11+

## Installation

### Using uv (Recommended)

```bash
uv tool install vllmlx
```

### Using pip

```bash
pip install vllmlx
```

### From Source

```bash
git clone https://github.com/lewi/vllmlx
cd vllmlx
pip install -e .
```

For detailed installation instructions, see [docs/installation.md](docs/installation.md).

## Commands

| Command | Description |
|---------|-------------|
| `vllmlx pull <model>` | Download a model |
| `vllmlx search [query]` | Search packaged mlx-community model catalog |
| `vllmlx ls` | List downloaded models |
| `vllmlx rm <model>` | Remove a model |
| `vllmlx run <model>` | Interactive chat (auto-starts daemon if needed) |
| `vllmlx serve` | Run server in foreground |
| `vllmlx daemon start` | Start background daemon |
| `vllmlx daemon stop` | Stop daemon |
| `vllmlx daemon restart` | Restart daemon |
| `vllmlx daemon status` | Check daemon status |
| `vllmlx daemon logs` | View daemon logs |
| `vllmlx config` | Show configuration |
| `vllmlx config set` | Set configuration value |
| `vllmlx config get` | Get configuration value |

For complete command reference, see [docs/cli-reference.md](docs/cli-reference.md).

## Available Models

vllmlx works with any MLX-compatible model from HuggingFace.

Built-in aliases are generated from the packaged `mlx-community` catalog at:

- `src/vllmlx/models/data/mlx_community_models.json`

Each catalog entry includes:

- alias
- HuggingFace repo id
- simple description
- model type (`text`, `vision`, `embedding`, `audio`)
- release date
- size in bytes (when available from Hub metadata)
- updated timestamp

`vllmlx search` and `vllmlx ls` use this packaged metadata locally, so discovery and cache inspection still work offline. Cached models also remain runnable offline; only new downloads require network access.

Regenerate the catalog with:

```bash
uv run python scripts/update_mlx_community_catalog.py
```

Legacy short aliases like `qwen2-vl-7b`, `qwen3:8b`, and `qwen3-embedding:4b` are retained for compatibility.

You can also use full HuggingFace paths:

```bash
vllmlx pull mlx-community/Some-Other-Model-4bit
```

## Configuration

Config file: `~/.vllmlx/config.toml`

```toml
[daemon]
port = 11434
host = "127.0.0.1"
idle_timeout = 600  # seconds
log_level = "info"
health_ttl_seconds = 1.0

[models]
default = "qwen2-vl-7b"

[aliases]
my-model = "mlx-community/Custom-Model-4bit"
```

Set values via CLI:

```bash
vllmlx config set daemon.idle_timeout 120
vllmlx config set models.default qwen2-vl-7b
```

## Optimization Profiles

`vllmlx` supports upstream `vllm-mlx` scheduler controls through `backend.*` config keys.

Balanced API (recommended):

```bash
vllmlx config set backend.continuous_batching true
vllmlx config set backend.stream_interval 1
vllmlx config set backend.max_num_seqs 256
vllmlx config set backend.max_num_batched_tokens 8192
vllmlx config set backend.chunked_prefill_tokens 0
```

Single-user latency:

```bash
vllmlx config set backend.continuous_batching false
vllmlx config set daemon.max_loaded_models 1
vllmlx config set daemon.idle_timeout 600
```

Multi-user throughput:

```bash
vllmlx config set backend.continuous_batching true
vllmlx config set backend.stream_interval 4
vllmlx config set backend.max_num_seqs 256
vllmlx config set backend.chunked_prefill_tokens 2048
vllmlx config set backend.prefill_step_size 2048
```

Tradeoffs:

- `backend.continuous_batching=true` improves throughput under concurrency but may add
  overhead for single-user workloads.
- Lower `backend.stream_interval` improves stream smoothness; higher values can improve throughput.
- `backend.chunked_prefill_tokens > 0` improves fairness under long prompts by preventing prefill starvation.

See [docs/dependency-upgrade-validation.md](docs/dependency-upgrade-validation.md) for the
benchmark matrix and gating criteria used when validating MLX dependency upgrades.

## API

vllmlx exposes an OpenAI-compatible API at `http://localhost:11434`:

### Chat Completions

```bash
curl http://localhost:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen2-vl-7b",
    "messages": [
      {
        "role": "user",
        "content": [
          {"type": "text", "text": "What is in this image?"},
          {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}}
        ]
      }
    ],
    "stream": true
  }'
```

### List Models

```bash
curl http://localhost:11434/v1/models
```

### Health Check

```bash
curl http://localhost:11434/health
```

### Status

```bash
curl http://localhost:11434/v1/status
```

## Troubleshooting

See [docs/troubleshooting.md](docs/troubleshooting.md) for common issues and solutions.

## License

MIT - see [LICENSE](LICENSE) for details.
