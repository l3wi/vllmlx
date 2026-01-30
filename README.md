# vmlx

Ollama-style CLI for [MLX-VLM](https://github.com/Blaizzy/mlx-vlm) - Run Vision Language Models on Apple Silicon with a persistent daemon and simple commands.

## Features

- 🚀 **Always-on daemon** - API available immediately after install, survives reboots
- 🎯 **Simple CLI** - `vmlx pull`, `vmlx run`, `vmlx ls` - familiar Ollama-style commands
- 🔄 **Hot-swap models** - Switch models on-the-fly without restarting
- 💾 **Smart memory** - Auto-unloads models after idle timeout
- 🤖 **OpenAI-compatible API** - Works with existing tools at `localhost:11434`

## Quick Start

```bash
# Install
pip install vmlx
# Or with uv (recommended)
uv tool install vmlx

# Pull a model
vmlx pull qwen2-vl-7b

# Start the daemon (auto-starts on login after this)
vmlx daemon start

# Chat interactively
vmlx run qwen2-vl-7b

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
uv tool install vmlx
```

### Using pip

```bash
pip install vmlx
```

### From Source

```bash
git clone https://github.com/yourusername/vmlx
cd vmlx
pip install -e .
```

For detailed installation instructions, see [docs/installation.md](docs/installation.md).

## Commands

| Command | Description |
|---------|-------------|
| `vmlx pull <model>` | Download a model |
| `vmlx ls` | List downloaded models |
| `vmlx rm <model>` | Remove a model |
| `vmlx run <model>` | Interactive chat |
| `vmlx serve` | Run server in foreground |
| `vmlx daemon start` | Start background daemon |
| `vmlx daemon stop` | Stop daemon |
| `vmlx daemon restart` | Restart daemon |
| `vmlx daemon status` | Check daemon status |
| `vmlx daemon logs` | View daemon logs |
| `vmlx config` | Show configuration |
| `vmlx config set` | Set configuration value |
| `vmlx config get` | Get configuration value |

For complete command reference, see [docs/cli-reference.md](docs/cli-reference.md).

## Available Models

vmlx works with any MLX-VLM compatible model from HuggingFace. Built-in aliases:

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
vmlx pull mlx-community/Some-Other-Model-4bit
```

## Configuration

Config file: `~/.vmlx/config.toml`

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
vmlx config set daemon.idle_timeout 120
vmlx config set models.default qwen2-vl-7b
```

## API

vmlx exposes an OpenAI-compatible API at `http://localhost:11434`:

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
curl http://localhost:11434/status
```

## Troubleshooting

See [docs/troubleshooting.md](docs/troubleshooting.md) for common issues and solutions.

## License

MIT - see [LICENSE](LICENSE) for details.
