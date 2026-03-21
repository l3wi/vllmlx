# ADR-0001: Embed MLX-VLM as Library vs Subprocess Wrapper

**Status:** Accepted  
**Date:** 2026-01-30  
**Context:** vllmlx daemon architecture

## Context

vllmlx needs to provide an always-on API server that wraps MLX-VLM. We need to decide how the daemon interacts with MLX-VLM:

1. **Subprocess wrapper**: Launch `mlx_vlm.server` as a child process, proxy requests
2. **Fork MLX-VLM**: Copy and modify MLX-VLM's server code
3. **Embed as library**: Import MLX-VLM's core functions, build custom server

Key requirements driving this decision:
- **Idle unloading**: Must unload model from RAM after configurable timeout
- **Hot-swap**: Must switch models without restarting daemon
- **Maintainability**: Should track upstream MLX-VLM updates easily
- **Performance**: Minimal overhead on request latency

## Decision

**Embed MLX-VLM as a library** - import `mlx_vlm.load()` and `mlx_vlm.generate()` functions, build our own FastAPI server around them.

## Rationale

### Why not subprocess wrapper?

MLX-VLM's server doesn't expose model lifecycle control. We can't tell it to unload a model - it keeps the model in memory until the process dies. This makes idle unloading impossible without killing and restarting the subprocess.

Additionally:
- Extra IPC overhead
- Harder to implement request queuing during hot-swap
- Process management complexity

### Why not fork?

Forking creates a maintenance burden. MLX-VLM is actively developed, and we'd need to manually merge upstream changes. Over time, our fork would diverge, making updates increasingly difficult.

### Why embed?

Embedding gives us:
- **Full lifecycle control**: We call `load()` and can `del model` + `gc.collect()` to unload
- **Direct integration**: No IPC, minimal latency overhead
- **Easy updates**: `pip install --upgrade mlx-vlm` brings new features
- **Hot-swap capability**: We control when to unload old model and load new one

The risk is that MLX-VLM's internal API (`load`, `generate`) could change. However:
- These are documented public functions
- Changes would be in release notes
- We can pin versions if needed

## Consequences

### Positive
- Idle unloading achievable via `del model` + memory cleanup
- Hot-swap achievable with full control over model state
- Minimal request latency overhead
- Automatic compatibility with MLX-VLM improvements

### Negative
- Coupled to MLX-VLM's `load()` and `generate()` function signatures
- Must handle streaming ourselves (wrap MLX-VLM's generator)
- Breaking changes in MLX-VLM may require vllmlx updates

### Mitigations
- Pin `mlx-vlm` version in dependencies with compatible range
- Integration tests catch API changes early
- Monitor MLX-VLM releases for breaking changes

## Alternatives Considered

See main spec document for detailed comparison of all three options.
