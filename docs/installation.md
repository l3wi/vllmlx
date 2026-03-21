# Installation Guide

## Requirements

- **macOS 13+** (Ventura or later)
- **Apple Silicon** (M1, M2, M3 series)
- **Python 3.11+** (3.12 recommended)

## Using uv (Recommended)

[uv](https://docs.astral.sh/uv/) is the recommended way to install vllmlx. It's fast and handles Python version management automatically.

```bash
# Install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install vllmlx as a tool
uv tool install vllmlx
```

## Using pip

```bash
pip install vllmlx
```

Or with a specific Python version:

```bash
python3.12 -m pip install vllmlx
```

## Using pipx

```bash
pipx install vllmlx
```

## From Source

```bash
# Clone the repository
git clone https://github.com/yourusername/vllmlx
cd vllmlx

# Install with pip
pip install -e .

# Or with uv
uv sync
uv run vllmlx --help
```

## Post-Installation

### 1. Pull a Model

Download your first model:

```bash
# Recommended starter model (~2GB)
vllmlx pull qwen2-vl-2b

# Or a larger, more capable model (~5GB)
vllmlx pull qwen2-vl-7b
```

### 2. Start the Daemon

Start the background service that provides the API:

```bash
vllmlx daemon start
```

This installs a launchd service that:
- Starts automatically on login
- Provides the API at `http://localhost:11434`
- Manages model loading/unloading

### 3. Test the Installation

```bash
# Check daemon status
vllmlx daemon status

# Test the API
curl http://localhost:11434/health

# Start an interactive chat
vllmlx run qwen2-vl-7b
```

## Updating

### With uv

```bash
uv tool upgrade vllmlx
```

### With pip

```bash
pip install --upgrade vllmlx
```

After updating, restart the daemon to use the new version:

```bash
vllmlx daemon restart
```

## Uninstalling

### 1. Stop and Remove the Daemon

```bash
vllmlx daemon stop
rm ~/Library/LaunchAgents/com.vllmlx.daemon.plist
```

### 2. Remove Models (Optional)

```bash
# List models
vllmlx ls

# Remove each model
vllmlx rm qwen2-vl-7b --force
```

### 3. Remove Configuration (Optional)

```bash
rm -rf ~/.vllmlx
```

### 4. Uninstall the Package

```bash
# If installed with uv
uv tool uninstall vllmlx

# If installed with pip
pip uninstall vllmlx

# If installed with pipx
pipx uninstall vllmlx
```

## Verifying Installation

Run the following commands to verify your installation:

```bash
# Check vllmlx is installed
vllmlx --version

# Check daemon is working
vllmlx daemon status

# List downloaded models
vllmlx ls

# Test API (requires daemon running)
curl -s http://localhost:11434/health
# Should output: {"status":"ok"}
```

## Model Storage

Models are stored in the HuggingFace cache directory:

```
~/.cache/huggingface/hub/
```

vllmlx configuration is stored in:

```
~/.vllmlx/
├── config.toml      # Configuration file
└── logs/
    ├── daemon.log       # Standard output
    └── daemon.error.log # Error output
```

## Troubleshooting Installation

### "command not found: vllmlx"

The vllmlx binary is not in your PATH. Check your shell configuration:

```bash
# For uv tool installs, add to your shell profile:
export PATH="$HOME/.local/bin:$PATH"

# Reload your shell
source ~/.zshrc  # or ~/.bashrc
```

### Python version errors

vllmlx requires Python 3.11+. Check your Python version:

```bash
python3 --version
```

If you need to install a newer Python:

```bash
# With uv
uv python install 3.12

# With Homebrew
brew install python@3.12
```

### MLX installation fails

MLX requires Apple Silicon. Verify you're on an M1/M2/M3 Mac:

```bash
uname -m
# Should output: arm64
```

If you're on Intel Mac, vllmlx is not supported.

### For more troubleshooting help

See [troubleshooting.md](troubleshooting.md).
