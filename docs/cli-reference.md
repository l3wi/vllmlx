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
vllmlx pull qwen2-vl-7b-instruct-4bit

# Pull using full HuggingFace path
vllmlx pull mlx-community/Qwen2-VL-7B-Instruct-4bit
```

---

### vllmlx search

Search the packaged `mlx-community` model catalog.

```bash
vllmlx search [query] [--limit N] [--type text|vision|embedding|audio] [--json]
```

**Arguments:**
- `[query]` - Optional search text (matches alias, repo id, type, description)

**Options:**
- `--limit <N>` - Maximum number of results (default: 20)
- `--type <kind>` - Filter by model type
- `--json` - Output raw JSON

**Examples:**
```bash
# Search by keyword
vllmlx search qwen3

# Show embedding models only
vllmlx search embedding --type embedding

# Machine-readable output
vllmlx search qwen --json
```

`vllmlx search` reads only the packaged catalog, so it works offline.

---

### vllmlx ls

List downloaded MLX models.

```bash
vllmlx ls [--type text|vision|embedding|audio]
```

Shows all MLX-VLM compatible models in the HuggingFace cache with their sizes and modification dates.

**Options:**
- `--type <kind>` - Filter downloaded models by model type

`vllmlx ls` uses packaged catalog sizes when available, so listing and incomplete-download detection keep working offline for known `mlx-community` models.

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
vllmlx rm qwen2-vl-2b-instruct-4bit

# Remove without confirmation
vllmlx rm qwen2-vl-2b-instruct-4bit --force
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
- Starts the daemon automatically if it is not already running

**Examples:**
```bash
# Start chat with specific model
vllmlx run qwen2-vl-7b-instruct-4bit

# Start chat with default model (if configured)
vllmlx run
```

**Interactive commands:**
- Type your message and press Enter to send
- Press `Ctrl+C` to exit
- Use `/exit` or `/quit` to exit

---

## Benchmarking

### vllmlx benchmark

Measure cold start, warm start, memory usage, time to first token, and token generation rate.

```bash
vllmlx benchmark <model> [options]
```

**Options:**
- `-n, --iterations <count>` - Iterations per prompt (default: 5)
- `-t, --max-tokens <count>` - Maximum generated tokens per response (default: 100)
- `-p, --prompt <text>` - Custom prompt, repeatable
- `-w, --warmup <count>` - Warmup iterations before measurement (default: 1)
- `--temp <value>` - Sampling temperature (default: 0.7)
- `--skip-cold-start` - Skip cold-start timing when model is already resident
- `--timeout-load <seconds>` - Load timeout (default: 300)
- `--timeout-gen <seconds>` - Generation timeout (default: 120)
- `--json` - Emit machine-readable JSON summary to stdout

**Examples:**
```bash
# Human-readable benchmark table
vllmlx benchmark qwen3-4b-4bit

# Machine-readable smoke run
vllmlx benchmark mlx-community/Llama-3.2-1B-Instruct-4bit --json -n 1 -t 16 --warmup 0
```

When `--json` is set, stdout contains only the benchmark summary payload, which is intended for the external e2e runner and other automation.

---

## Server

### vllmlx serve

Start the vllmlx API server in foreground (for development).

```bash
vllmlx serve [options]
```

**Options:**
- `-p, --port <port>` - Port to listen on (default: 8000)
- `-h, --host <host>` - Host to bind to (default: 127.0.0.1)
- `-l, --log-level <level>` - Log level: debug, info, warning, error, critical (default: info)

**Examples:**
```bash
# Start with defaults (localhost:8000)
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
│ Port         │ 8000            │
│ Uptime       │ 3600s            │
│ Loaded Model │ qwen2-vl-7b-instruct-4bit │
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
| `daemon.preload_default_model` | bool | Preload default model at daemon startup |
| `daemon.pin_default_model` | bool | Keep default model loaded during idle unload |
| `daemon.max_loaded_models` | int | Maximum concurrently loaded backend workers |
| `daemon.min_available_memory_gb` | float | Minimum memory headroom before model eviction |
| `daemon.health_ttl_seconds` | float | Cache window for backend health checks |
| `backend.continuous_batching` | bool | Enable vLLM-style continuous batching |
| `backend.stream_interval` | int | Tokens to batch before streaming output |
| `backend.max_num_seqs` | int | Maximum concurrent sequences in scheduler |
| `backend.max_num_batched_tokens` | int | Max batched prefill tokens per scheduler step |
| `backend.scheduler_policy` | string | Scheduler policy (`fcfs` or `priority`) |
| `backend.prefill_batch_size` | int | Prefill batch size |
| `backend.completion_batch_size` | int | Completion batch size |
| `backend.prefill_step_size` | int | Prefill step size passed to scheduler |
| `backend.enable_prefix_cache` | bool | Enable prefix cache for repeated prompts |
| `backend.prefix_cache_size` | int | Prefix cache entry limit (legacy mode) |
| `backend.cache_memory_mb` | int\|none | Explicit memory-aware cache limit in MB |
| `backend.cache_memory_percent` | float | Auto cache memory fraction when MB not set |
| `backend.no_memory_aware_cache` | bool | Disable memory-aware cache eviction |
| `backend.use_paged_cache` | bool | Enable paged cache mode |
| `backend.paged_cache_block_size` | int | Paged cache block size in tokens |
| `backend.max_cache_blocks` | int | Maximum number of paged cache blocks |
| `backend.chunked_prefill_tokens` | int | Chunk size for long prefills (0 disables) |
| `backend.mid_prefill_save_interval` | int | Mid-prefill cache save interval in tokens |
| `backend.embedding_model` | string | Default embedding model route target |
| `models.default` | string | Default model for `vllmlx run` |
| `aliases.<name>` | string | Custom model alias |

**Examples:**
```bash
# Set idle timeout to 2 minutes
vllmlx config set daemon.idle_timeout 120

# Set default model
vllmlx config set models.default qwen2-vl-7b-instruct-4bit

# Add custom alias
vllmlx config set aliases.my-model some-org/some-model-4bit

# Enable balanced continuous batching defaults
vllmlx config set backend.continuous_batching true
vllmlx config set backend.max_num_batched_tokens 8192
vllmlx config set backend.chunked_prefill_tokens 0
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
# daemon.port = 8000

vllmlx config get models.default
# models.default = qwen2-vl-7b-instruct-4bit
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

### Optimization Profiles

#### Balanced API (recommended)

```bash
vllmlx config set backend.continuous_batching true
vllmlx config set backend.stream_interval 1
vllmlx config set backend.max_num_seqs 256
vllmlx config set backend.max_num_batched_tokens 8192
vllmlx config set backend.chunked_prefill_tokens 0
```

#### Single-user latency

```bash
vllmlx config set backend.continuous_batching false
vllmlx config set daemon.max_loaded_models 1
vllmlx config set daemon.idle_timeout 600
```

#### Multi-user throughput

```bash
vllmlx config set backend.continuous_batching true
vllmlx config set backend.stream_interval 4
vllmlx config set backend.chunked_prefill_tokens 2048
vllmlx config set backend.prefill_step_size 2048
```

Tradeoffs:

- `backend.continuous_batching`: higher concurrency throughput, potential single-user overhead.
- `backend.stream_interval`: lower values improve stream smoothness; higher values can improve throughput.
- `backend.chunked_prefill_tokens`: non-zero values improve fairness for long prompts by preventing prefill starvation.

---

## Built-in Model Aliases

Built-in aliases are generated from the packaged `mlx-community` catalog:

- `src/vllmlx/models/data/mlx_community_models.json`

The generated catalog is used for alias resolution and search metadata and includes:

- alias
- repo id
- simple description
- model type
- release date
- size (when present in Hub metadata)
- updated timestamp

Regenerate the catalog:

```bash
uv run python scripts/update_mlx_community_catalog.py
```

Use the generated catalog aliases shown by `vllmlx search`, or pass full HuggingFace repo ids directly.

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error (invalid input, operation failed) |
| 2 | Command not found / invalid usage |

---

## External E2E Runner

The real-model parity suite is executed via:

```bash
uv run python scripts/run_e2e.py --mode smoke
```

Key flags:

- `--mode smoke|full` - Select the scenario set
- `--scenario <name>` - Run only specific scenarios
- `--allow-launchd` - Enable the explicit launchd lifecycle scenario
- `--json-report <path>` - Write the aggregate JSON report to a custom path
- `--model`, `--secondary-model`, `--download-model` - Override the default model trio
