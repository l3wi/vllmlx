# CLI Reference

Complete reference for all vmlx commands.

## Global Options

```bash
vmlx --version  # Show version
vmlx --help     # Show help
```

---

## Model Management

### vmlx pull

Download a model from HuggingFace.

```bash
vmlx pull <model>
```

**Arguments:**
- `<model>` - Model alias or full HuggingFace path

**Examples:**
```bash
# Pull using alias
vmlx pull qwen2-vl-7b

# Pull using full HuggingFace path
vmlx pull mlx-community/Qwen2-VL-7B-Instruct-4bit
```

---

### vmlx ls

List downloaded MLX models.

```bash
vmlx ls
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

### vmlx rm

Remove a model from the HuggingFace cache.

```bash
vmlx rm <model> [--force]
```

**Arguments:**
- `<model>` - Model alias or full HuggingFace path

**Options:**
- `-f, --force` - Skip confirmation prompt

**Examples:**
```bash
# Remove with confirmation
vmlx rm qwen2-vl-2b

# Remove without confirmation
vmlx rm qwen2-vl-2b --force
```

---

## Interactive Chat

### vmlx run

Start an interactive chat session.

```bash
vmlx run [model]
```

**Arguments:**
- `[model]` - Model alias or path (optional if default configured)

**Requirements:**
- Daemon must be running (`vmlx daemon start`)

**Examples:**
```bash
# Start chat with specific model
vmlx run qwen2-vl-7b

# Start chat with default model (if configured)
vmlx run
```

**Interactive commands:**
- Type your message and press Enter to send
- Press `Ctrl+C` to exit
- Use `/exit` or `/quit` to exit

---

## Server

### vmlx serve

Start the vmlx API server in foreground (for development).

```bash
vmlx serve [options]
```

**Options:**
- `-p, --port <port>` - Port to listen on (default: 11434)
- `-h, --host <host>` - Host to bind to (default: 127.0.0.1)
- `-l, --log-level <level>` - Log level: debug, info, warning, error, critical (default: info)

**Examples:**
```bash
# Start with defaults (localhost:11434)
vmlx serve

# Start on custom port
vmlx serve --port 8080

# Allow external connections (use with caution)
vmlx serve --host 0.0.0.0

# Debug logging
vmlx serve --log-level debug
```

---

## Daemon Management

### vmlx daemon start

Start the vmlx daemon.

```bash
vmlx daemon start
```

Installs the launchd plist if not present and loads the daemon. The daemon will auto-start on future logins.

---

### vmlx daemon stop

Stop the vmlx daemon.

```bash
vmlx daemon stop
```

Unloads the daemon from launchd. The daemon will still auto-start on next login unless you remove the plist.

---

### vmlx daemon restart

Restart the vmlx daemon.

```bash
vmlx daemon restart
```

Stops the daemon if running, then starts it again. Useful after configuration changes.

---

### vmlx daemon status

Show daemon status.

```bash
vmlx daemon status
```

Displays whether the daemon is running, its PID, and information about loaded models and resource usage.

**Example output:**
```
        vmlx Daemon Status        
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

### vmlx daemon logs

View daemon logs.

```bash
vmlx daemon logs [options]
```

**Options:**
- `-f, --follow` - Follow log output (tail -f)
- `-n, --lines <number>` - Number of lines to show (default: 50)

**Examples:**
```bash
# Show last 50 lines
vmlx daemon logs

# Show last 100 lines
vmlx daemon logs -n 100

# Follow log output (Ctrl+C to stop)
vmlx daemon logs -f
```

---

## Configuration

### vmlx config

View current configuration.

```bash
vmlx config
```

Displays the current configuration from `~/.vmlx/config.toml`.

---

### vmlx config set

Set a configuration value.

```bash
vmlx config set <key> <value>
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
| `models.default` | string | Default model for `vmlx run` |
| `aliases.<name>` | string | Custom model alias |

**Examples:**
```bash
# Set idle timeout to 2 minutes
vmlx config set daemon.idle_timeout 120

# Set default model
vmlx config set models.default qwen2-vl-7b

# Add custom alias
vmlx config set aliases.my-model some-org/some-model-4bit
```

---

### vmlx config get

Get a configuration value.

```bash
vmlx config get <key>
```

**Examples:**
```bash
vmlx config get daemon.port
# daemon.port = 11434

vmlx config get models.default
# models.default = qwen2-vl-7b
```

---

### vmlx config path

Show the config file path.

```bash
vmlx config path
```

**Output:**
```
/Users/yourusername/.vmlx/config.toml
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
