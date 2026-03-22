# CLI Reference

Complete reference for all vllmlx commands.

## Global Options

```bash
vllmlx --version  # Show version
vllmlx --help     # Show help
```

---

## Model Management

### vllmlx pull

Download a model from HuggingFace.

```bash
vllmlx pull <model>
```

**Arguments:**
- `<model>` - Model alias or full HuggingFace path

**Examples:**
```bash
# Pull using alias
vllmlx pull qwen2-vl-7b

# Pull using full HuggingFace path
vllmlx pull mlx-community/Qwen2-VL-7B-Instruct-4bit
```

---

### vllmlx ls

List downloaded MLX models.

```bash
vllmlx ls
```

Shows all MLX-VLM compatible models in the HuggingFace cache with their sizes and modification dates.

**Example output:**
```
         Downloaded MLX Models          
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━┓
┃ Name                              ┃   Size ┃ Modified   ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━┩
│ mlx-community/Qwen2-VL-2B-4bit    │ 2.1 GB │ 2026-01-30 │
│ mlx-community/Qwen2-VL-7B-4bit    │ 4.8 GB │ 2026-01-28 │
└───────────────────────────────────┴────────┴────────────┘

2 model(s)
```

---

### vllmlx rm

Remove a model from the HuggingFace cache.

```bash
vllmlx rm <model> [--force]
```

**Arguments:**
- `<model>` - Model alias or full HuggingFace path

**Options:**
- `-f, --force` - Skip confirmation prompt

**Examples:**
```bash
# Remove with confirmation
vllmlx rm qwen2-vl-2b

# Remove without confirmation
vllmlx rm qwen2-vl-2b --force
```

---

## Interactive Chat

### vllmlx run

Start an interactive chat session.

```bash
vllmlx run [model]
```

**Arguments:**
- `[model]` - Model alias or path (optional if default configured)

**Requirements:**
- Daemon must be running (`vllmlx daemon start`)

**Examples:**
```bash
# Start chat with specific model
vllmlx run qwen2-vl-7b

# Start chat with default model (if configured)
vllmlx run
```

**Interactive commands:**
- Type your message and press Enter to send
- Press `Ctrl+C` to exit
- Use `/exit` or `/quit` to exit

---

## Server

### vllmlx serve

Start the vllmlx API server in foreground (for development).

```bash
vllmlx serve [options]
```

**Options:**
- `-p, --port <port>` - Port to listen on (default: 11434)
- `-h, --host <host>` - Host to bind to (default: 127.0.0.1)
- `-l, --log-level <level>` - Log level: debug, info, warning, error, critical (default: info)

**Examples:**
```bash
# Start with defaults (localhost:11434)
vllmlx serve

# Start on custom port
vllmlx serve --port 8080

# Allow external connections (use with caution)
vllmlx serve --host 0.0.0.0

# Debug logging
vllmlx serve --log-level debug
```

---

## Daemon Management

### vllmlx daemon start

Start the vllmlx daemon.

```bash
vllmlx daemon start
```

Installs the launchd plist if not present and loads the daemon. The daemon will auto-start on future logins.

---

### vllmlx daemon stop

Stop the vllmlx daemon.

```bash
vllmlx daemon stop
```

Unloads the daemon from launchd. The daemon will still auto-start on next login unless you remove the plist.

---

### vllmlx daemon restart

Restart the vllmlx daemon.

```bash
vllmlx daemon restart
```

Stops the daemon if running, then starts it again. Useful after configuration changes.

---

### vllmlx daemon status

Show daemon status.

```bash
vllmlx daemon status
```

Displays whether the daemon is running, its PID, and information about loaded models and resource usage.

**Example output:**
```
        vllmlx Daemon Status        
┏━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┓
┃ Property     ┃ Value            ┃
┡━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━┩
│ Status       │ Running          │
│ PID          │ 12345            │
│ Port         │ 11434            │
│ Uptime       │ 3600s            │
│ Loaded Model │ qwen2-vl-7b      │
│ Memory       │ 4500.2 MB        │
│ Idle Timeout │ 45s              │
└──────────────┴──────────────────┘
```

---

### vllmlx daemon logs

View daemon logs.

```bash
vllmlx daemon logs [options]
```

**Options:**
- `-f, --follow` - Follow log output (tail -f)
- `-n, --lines <number>` - Number of lines to show (default: 50)

**Examples:**
```bash
# Show last 50 lines
vllmlx daemon logs

# Show last 100 lines
vllmlx daemon logs -n 100

# Follow log output (Ctrl+C to stop)
vllmlx daemon logs -f
```

---

## Configuration

### vllmlx config

View current configuration.

```bash
vllmlx config
```

Displays the current configuration from `~/.vllmlx/config.toml`.

---

### vllmlx config set

Set a configuration value.

```bash
vllmlx config set <key> <value>
```

**Arguments:**
- `<key>` - Dot-separated config path
- `<value>` - New value

**Available keys:**
| Key | Type | Description |
|-----|------|-------------|
| `daemon.port` | int | API server port |
| `daemon.host` | string | API server host |
| `daemon.idle_timeout` | int | Seconds before model unload |
| `daemon.log_level` | string | Logging level |
| `daemon.health_ttl_seconds` | float | Cache window for backend health checks |
| `models.default` | string | Default model for `vllmlx run` |
| `aliases.<name>` | string | Custom model alias |

**Examples:**
```bash
# Set idle timeout to 2 minutes
vllmlx config set daemon.idle_timeout 120

# Set default model
vllmlx config set models.default qwen2-vl-7b

# Add custom alias
vllmlx config set aliases.my-model some-org/some-model-4bit
```

---

### vllmlx config get

Get a configuration value.

```bash
vllmlx config get <key>
```

**Examples:**
```bash
vllmlx config get daemon.port
# daemon.port = 11434

vllmlx config get models.default
# models.default = qwen2-vl-7b
```

---

### vllmlx config path

Show the config file path.

```bash
vllmlx config path
```

**Output:**
```
/Users/yourusername/.vllmlx/config.toml
```

---

## Built-in Model Aliases

| Alias | Full HuggingFace Path |
|-------|----------------------|
| `qwen2-vl-2b` | mlx-community/Qwen2-VL-2B-Instruct-4bit |
| `qwen2-vl-7b` | mlx-community/Qwen2-VL-7B-Instruct-4bit |
| `qwen2.5-vl-3b` | mlx-community/Qwen2.5-VL-3B-Instruct-4bit |
| `qwen2.5-vl-7b` | mlx-community/Qwen2.5-VL-7B-Instruct-4bit |
| `qwen2.5-vl-32b` | mlx-community/Qwen2.5-VL-32B-Instruct-8bit |
| `qwen2.5-vl-72b` | mlx-community/Qwen2.5-VL-72B-Instruct-4bit |
| `pixtral-12b` | mlx-community/pixtral-12b-4bit |
| `llava-qwen-0.5b` | mlx-community/llava-interleave-qwen-0.5b-bf16 |
| `llava-qwen-7b` | mlx-community/llava-interleave-qwen-7b-4bit |

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error (invalid input, operation failed) |
| 2 | Command not found / invalid usage |
