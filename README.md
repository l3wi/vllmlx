# vllmlx

Ollama-style daemon and CLI for [vllm-mlx](https://github.com/waybarrios/vllm-mlx).

## Breaking Change

`vmlx` is discontinued. This package is hard-cut renamed to `vllmlx` with no compatibility layer:

- no `vmlx` CLI alias
- no `vmlx` Python package import
- no `~/.vmlx` config path
- no legacy `/status` route

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
git clone https://github.com/yourusername/vllmlx
cd vllmlx
pip install -e .
```

For detailed installation instructions, see [docs/installation.md](docs/installation.md).

## Commands

| Command | Description |
|---------|-------------|
| `vllmlx pull <model>` | Download a model |
| `vllmlx ls` | List downloaded models |
| `vllmlx rm <model>` | Remove a model |
| `vllmlx run <model>` | Interactive chat |
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

vllmlx works with any MLX-VLM compatible model from HuggingFace. Built-in aliases:

| Alias | Model |
|-------|-------|
| `qwen2-vl-2b` | mlx-community/Qwen2-VL-2B-Instruct-4bit |
| `qwen2-vl-7b` | mlx-community/Qwen2-VL-7B-Instruct-4bit |
| `qwen2.5-vl-3b` | mlx-community/Qwen2.5-VL-3B-Instruct-4bit |
| `qwen2.5-vl-7b` | mlx-community/Qwen2.5-VL-7B-Instruct-4bit |
| `qwen2.5-vl-32b` | mlx-community/Qwen2.5-VL-32B-Instruct-8bit |
| `qwen2.5-vl-72b` | mlx-community/Qwen2.5-VL-72B-Instruct-4bit |
| `pixtral-12b` | mlx-community/pixtral-12b-4bit |
| `llava-qwen-0.5b` | mlx-community/llava-interleave-qwen-0.5b-bf16 |
| `llava-qwen-7b` | mlx-community/llava-interleave-qwen-7b-4bit |

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
idle_timeout = 60  # seconds
log_level = "info"

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
