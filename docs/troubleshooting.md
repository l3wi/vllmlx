# Troubleshooting

Common issues and solutions for vmlx.

## Daemon Issues

### "Cannot connect to daemon" / "Daemon is not running"

The daemon isn't running. Start it:

```bash
vmlx daemon start
```

If it fails to start, check logs:

```bash
vmlx daemon logs
```

### Daemon won't start

#### 1. Check if port is in use

```bash
lsof -i :11434
```

If another process is using the port, either stop it or change vmlx's port:

```bash
vmlx config set daemon.port 8080
vmlx daemon start
```

#### 2. Check plist is valid

```bash
plutil ~/Library/LaunchAgents/com.vmlx.daemon.plist
```

#### 3. Check launchd logs

```bash
# Check if launchd loaded the service
launchctl list | grep vmlx

# Check system log for errors
log show --predicate 'process == "launchd"' --last 5m | grep vmlx
```

#### 4. Remove and reinstall

```bash
vmlx daemon stop
rm ~/Library/LaunchAgents/com.vmlx.daemon.plist
vmlx daemon start
```

### Daemon uses too much memory

When a model is loaded, it uses significant RAM. To reduce idle memory usage:

1. **Reduce idle timeout** to unload model faster:
   ```bash
   vmlx config set daemon.idle_timeout 30
   vmlx daemon restart
   ```

2. **Use smaller models**:
   - `qwen2-vl-2b` (~2GB) - fastest, lightest
   - `qwen2-vl-7b` (~5GB) - balanced
   - `qwen2.5-vl-32b` (~20GB) - requires lots of RAM

### Daemon crashes repeatedly

Check error logs:

```bash
cat ~/.vmlx/logs/daemon.error.log
```

Common causes:
- Corrupted model files (re-download with `vmlx pull`)
- Insufficient system resources
- Python version mismatch

---

## Model Issues

### "Model not found"

Make sure the model is downloaded:

```bash
# Check downloaded models
vmlx ls

# Download if needed
vmlx pull qwen2-vl-7b
```

### Model alias not recognized

Check if you're using the correct alias:

```bash
# Built-in aliases
qwen2-vl-2b, qwen2-vl-7b, qwen2.5-vl-3b, qwen2.5-vl-7b
qwen2.5-vl-32b, qwen2.5-vl-72b, pixtral-12b
llava-qwen-0.5b, llava-qwen-7b
```

Or use the full HuggingFace path:

```bash
vmlx pull mlx-community/Qwen2-VL-7B-Instruct-4bit
```

### Model loading is slow

First load is slow due to downloading and initialization. Subsequent loads are faster because:
- Model weights are cached
- MLX compiles shaders on first use

For faster startup:
- Use smaller models (2B instead of 7B)
- Keep models in memory longer (`idle_timeout = 300`)

### Model download interrupted

If a download is interrupted, the model may be corrupted. Remove and re-download:

```bash
vmlx rm qwen2-vl-7b --force
vmlx pull qwen2-vl-7b
```

### Out of memory

Your Mac doesn't have enough RAM for the model. Model memory requirements (approximate):

| Model | RAM Required |
|-------|-------------|
| qwen2-vl-2b | 4 GB |
| qwen2-vl-7b | 8 GB |
| qwen2.5-vl-32b | 24 GB |
| qwen2.5-vl-72b | 48 GB |

Solutions:
1. Use a smaller model
2. Close other memory-heavy applications
3. Use 4-bit quantized models (most aliases use these)

---

## API Issues

### Connection refused

The daemon is not running or listening on a different port:

```bash
# Check daemon status
vmlx daemon status

# Verify port setting
vmlx config get daemon.port
```

### Slow response times

First request after idle timeout is slow because the model needs to load:

1. Increase idle timeout:
   ```bash
   vmlx config set daemon.idle_timeout 300
   ```

2. Keep model loaded with periodic health checks:
   ```bash
   # In a separate terminal or cron job
   watch -n 30 'curl -s http://localhost:11434/health'
   ```

### Streaming doesn't work

Make sure you're handling Server-Sent Events (SSE) correctly:

**Python example:**
```python
import httpx

with httpx.stream("POST", "http://localhost:11434/v1/chat/completions", 
                  json={
                      "model": "qwen2-vl-7b",
                      "messages": [{"role": "user", "content": "Hello"}],
                      "stream": True
                  }) as response:
    for line in response.iter_lines():
        if line.startswith("data: "):
            data = line[6:]
            if data != "[DONE]":
                print(data)
```

**curl example:**
```bash
curl -N http://localhost:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "qwen2-vl-7b", "messages": [{"role": "user", "content": "Hello"}], "stream": true}'
```

### Images not working

Images must be base64 encoded in the `image_url` field:

```json
{
  "role": "user",
  "content": [
    {"type": "text", "text": "What's in this image?"},
    {
      "type": "image_url",
      "image_url": {
        "url": "data:image/jpeg;base64,/9j/4AAQ..."
      }
    }
  ]
}
```

**Python example for encoding:**
```python
import base64

with open("image.jpg", "rb") as f:
    image_b64 = base64.b64encode(f.read()).decode()
    
url = f"data:image/jpeg;base64,{image_b64}"
```

---

## CLI Issues

### "command not found: vmlx"

The vmlx binary is not in your PATH:

```bash
# For pip/uv installs, add to ~/.zshrc or ~/.bashrc:
export PATH="$HOME/.local/bin:$PATH"

# Reload shell
source ~/.zshrc
```

### Permission denied

Make sure you have write access to the config directory:

```bash
ls -la ~/.vmlx/
# Should be owned by your user

# Fix permissions if needed
chmod -R u+rw ~/.vmlx/
```

### Config file not found

vmlx creates the config file on first use. Force creation:

```bash
vmlx config
```

Or create manually:

```bash
mkdir -p ~/.vmlx
cat > ~/.vmlx/config.toml << 'EOF'
[daemon]
port = 11434
host = "127.0.0.1"
idle_timeout = 60
log_level = "info"

[models]
default = ""

[aliases]
EOF
```

---

## Getting More Help

### 1. Check daemon logs

```bash
# Recent logs
vmlx daemon logs -n 100

# Follow live
vmlx daemon logs -f
```

### 2. Check error logs

```bash
cat ~/.vmlx/logs/daemon.error.log
```

### 3. Check daemon status

```bash
vmlx daemon status
```

### 4. Verify installation

```bash
vmlx --version
python3 -c "import mlx_vlm; print(mlx_vlm.__version__)"
```

### 5. Open an issue

If you can't resolve the issue, open an issue on GitHub with:
- Your macOS version (`sw_vers`)
- Your Mac model (`system_profiler SPHardwareDataType | grep Model`)
- Python version (`python3 --version`)
- vmlx version (`vmlx --version`)
- Full error message and logs
- Steps to reproduce

GitHub Issues: https://github.com/yourusername/vmlx/issues
