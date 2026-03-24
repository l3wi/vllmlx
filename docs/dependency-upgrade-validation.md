# Dependency Upgrade Validation

This guide defines the gated process for MLX dependency upgrades.

## Scope

- Candidate upgrades:
  - `mlx` / `mlx-metal` (start with `0.31.1`)
- Keep `vllm-mlx` pinned unless a newer stable release is explicitly validated as compatible.

## Phase A: Baseline (current lockfile)

Record baseline metrics with the current `uv.lock`:

```bash
# 1) Single-request latency profile
vllmlx benchmark qwen3-4b-4bit -n 5 -t 100 --warmup 1

# 2) Throughput profile proxying through API (5 concurrent clients)
# Use your existing load harness or benchmark script against localhost:8000.

# 3) Long-prompt fairness profile
vllmlx benchmark qwen3-4b-4bit -n 3 -t 200 \
  -p "Summarize this: $(python3 - <<'PY'
print('token ' * 12000)
PY
)"
```

Capture:

- average TTFT
- average tokens/sec
- peak Metal memory

## Phase B: Candidate Upgrade

1. Update only candidate deps (`mlx`, `mlx-metal`) and re-lock.
2. Re-run the same benchmark matrix and capture the same metrics.
3. Run full test suite.

## Phase C: Acceptance Gates

Upgrade is accepted only if all are true:

- all tests pass
- throughput regression is no worse than 5%
- TTFT regression is no worse than 10%
- peak memory increase is no worse than 10%

If any gate fails:

- keep current lockfile
- ship repo code/docs/runtime improvements without dependency bump

## Suggested Comparison Sheet

| Metric | Baseline | Candidate | Delta | Gate |
|---|---:|---:|---:|---|
| TTFT (ms) | | | | <= +10% |
| Throughput (tok/s) | | | | >= -5% |
| Peak Metal Memory (GB) | | | | <= +10% |
