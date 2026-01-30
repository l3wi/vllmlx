# Task: Documentation & Release

**Phase**: 6  
**Branch**: `feat/vmlx-phase-6`  
**Plan**: [docs/plans/vmlx.md](../plans/vmlx.md)  
**Spec**: [docs/specs/vmlx-spec.md](../specs/vmlx-spec.md)  
**Status**: pending  
**Depends On**: Phase 3, Phase 4, Phase 5

---

## Objective

Complete documentation, CI/CD setup, and prepare for PyPI release.

---

## Acceptance Criteria

- [ ] README.md with quick start, features, installation
- [ ] CLI reference documentation
- [ ] Troubleshooting guide
- [ ] GitHub Actions CI (lint, test on macOS)
- [ ] GitHub Actions release workflow (publish to PyPI)
- [ ] `pyproject.toml` has all metadata for PyPI
- [ ] Package installable via `pip install vmlx`
- [ ] All existing tests still pass
- [ ] Lint clean

---

## Files to Create

| File | Action | Description |
|------|--------|-------------|
| `README.md` | create | Main documentation |
| `docs/installation.md` | create | Detailed installation guide |
| `docs/cli-reference.md` | create | Full CLI documentation |
| `docs/troubleshooting.md` | create | Common issues and solutions |
| `.github/workflows/ci.yml` | create | CI workflow |
| `.github/workflows/release.yml` | create | PyPI release workflow |
| `pyproject.toml` | modify | Add PyPI metadata |
| `LICENSE` | create | MIT license |

---

## Implementation Notes

### README.md

```markdown
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
- Python 3.12+

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
| `vmlx daemon status` | Check daemon status |
| `vmlx daemon logs` | View daemon logs |
| `vmlx config` | Show configuration |

## Available Models

vmlx works with any MLX-VLM compatible model from HuggingFace. Built-in aliases:

| Alias | Model |
|-------|-------|
| `qwen2-vl-2b` | mlx-community/Qwen2-VL-2B-Instruct-4bit |
| `qwen2-vl-7b` | mlx-community/Qwen2-VL-7B-Instruct-4bit |
| `qwen2.5-vl-7b` | mlx-community/Qwen2.5-VL-7B-Instruct-4bit |
| `pixtral-12b` | mlx-community/pixtral-12b-4bit |

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

## Troubleshooting

See [troubleshooting guide](docs/troubleshooting.md).

## License

MIT
```

### CI Workflow (.github/workflows/ci.yml)

```yaml
name: CI

on:
  push:
    branches: [main, feat/*]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: uv sync --dev
      - run: uv run ruff check src tests
      - run: uv run ruff format --check src tests

  test:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: uv sync --dev
      - run: uv run pytest tests/unit -v
      
  # Integration tests need real models - run separately
  test-integration:
    runs-on: macos-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: uv sync --dev
      - run: uv run pytest tests/integration -v --timeout=300
```

### Release Workflow (.github/workflows/release.yml)

```yaml
name: Release

on:
  push:
    tags:
      - 'v*'

jobs:
  release:
    runs-on: macos-latest
    permissions:
      id-token: write  # For trusted publishing
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      
      - name: Build package
        run: uv build
      
      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
```

### pyproject.toml Updates

```toml
[project]
name = "vmlx"
version = "0.1.0"
description = "Ollama-style CLI for MLX-VLM - Vision Language Models on Apple Silicon"
readme = "README.md"
license = {text = "MIT"}
requires-python = ">=3.12"
authors = [
    {name = "Your Name", email = "your@email.com"}
]
keywords = ["mlx", "vlm", "vision", "language", "model", "apple", "silicon", "ollama"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Environment :: Console",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Operating System :: MacOS",
    "Programming Language :: Python :: 3.12",
    "Topic :: Scientific/Engineering :: Artificial Intelligence",
]

dependencies = [
    "click>=8.0",
    "pydantic>=2.0",
    "toml>=0.10",
    "huggingface_hub>=0.20",
    "rich>=13.0",
    "mlx-vlm>=0.1.0",
    "fastapi>=0.100",
    "uvicorn>=0.20",
    "httpx>=0.25",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-asyncio>=0.21",
    "pytest-timeout>=2.0",
    "ruff>=0.1",
]

[project.scripts]
vmlx = "vmlx.cli.main:cli"

[project.urls]
Homepage = "https://github.com/yourusername/vmlx"
Documentation = "https://github.com/yourusername/vmlx#readme"
Repository = "https://github.com/yourusername/vmlx"
Issues = "https://github.com/yourusername/vmlx/issues"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/vmlx"]

[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
]
```

### Troubleshooting Guide (docs/troubleshooting.md)

```markdown
# Troubleshooting

## Daemon Issues

### "Cannot connect to daemon"

The daemon isn't running. Start it:

```bash
vmlx daemon start
```

If it fails to start, check logs:

```bash
vmlx daemon logs
```

### Daemon won't start

1. Check if port is in use:
   ```bash
   lsof -i :11434
   ```

2. Check plist is valid:
   ```bash
   plutil ~/Library/LaunchAgents/com.vmlx.daemon.plist
   ```

3. Remove and reinstall:
   ```bash
   vmlx daemon stop
   rm ~/Library/LaunchAgents/com.vmlx.daemon.plist
   vmlx daemon start
   ```

### Daemon uses too much memory

Reduce idle timeout to unload model faster:

```bash
vmlx config set daemon.idle_timeout 30
vmlx daemon restart
```

## Model Issues

### "Model not found"

Make sure the model is downloaded:

```bash
vmlx ls  # Check downloaded models
vmlx pull qwen2-vl-7b  # Download if needed
```

### Model loading is slow

First load is slow due to downloading. Subsequent loads are faster.

For faster startup, use smaller models:
- `qwen2-vl-2b` (~2GB) - fastest
- `qwen2-vl-7b` (~5GB) - balanced
- `qwen2.5-vl-32b` (~20GB) - slowest

### Out of memory

Your Mac doesn't have enough RAM for the model. Try a smaller model:

```bash
vmlx rm qwen2.5-vl-32b
vmlx pull qwen2-vl-2b
```

## API Issues

### Streaming doesn't work

Make sure you're handling SSE correctly:

```python
import httpx

with httpx.stream("POST", "http://localhost:11434/v1/chat/completions", 
                  json={"model": "qwen2-vl-7b", "messages": [...], "stream": True}) as r:
    for line in r.iter_lines():
        if line.startswith("data: "):
            print(line[6:])
```

### Images not working

Images must be base64 encoded in the `image_url` field:

```json
{
  "type": "image_url",
  "image_url": {
    "url": "data:image/jpeg;base64,/9j/4AAQ..."
  }
}
```

## Getting Help

1. Check daemon logs: `vmlx daemon logs`
2. Check daemon status: `vmlx daemon status`
3. Open an issue: https://github.com/yourusername/vmlx/issues
```

### LICENSE

```
MIT License

Copyright (c) 2026 Your Name

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## Testing Requirements

No new tests in this phase - ensure all existing tests pass:

```bash
pytest tests/ -v
ruff check src tests
```

---

## Agent Instructions

1. Create comprehensive README.md
2. Create docs/installation.md with detailed setup steps
3. Create docs/cli-reference.md with all commands documented
4. Create docs/troubleshooting.md
5. Create .github/workflows/ci.yml
6. Create .github/workflows/release.yml
7. Update pyproject.toml with full metadata
8. Create LICENSE file
9. Run all tests to ensure nothing broke
10. Test package build:
    ```bash
    pip install build
    python -m build
    pip install dist/vmlx-0.1.0-py3-none-any.whl
    vmlx --help
    ```
11. Commit with `wt commit`
