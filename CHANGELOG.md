# Changelog

## Unreleased

## 0.1.2 - 2026-03-24

### Changed
- Switched the default OpenAI-compatible API port from `11434` to `8000` across the daemon, CLI, chat client, tests, and user-facing documentation so vllmlx matches the default vLLM port.
- Ignored local `.claude/` and `.pi/` agent artifacts and removed them from version control without deleting local files.

## 0.1.1 - 2026-03-24

### Fixed
- Included the packaged `mlx-community` catalog JSON in source distributions so release builds can produce wheels from the sdist and publish successfully.

### Changed
- Refactored daemon runtime state to a single slot map (`model_slots`) using a `ModelSlot` dataclass instead of parallel dictionaries.
- Replaced concrete supervisor type checks with a `SupervisorProtocol` contract for primary and per-model supervisors.
- Updated model-targeted proxy routing to reuse the supervisor returned by model loading, avoiding an immediate second supervisor lookup.
- Reused daemon-lifetime pooled HTTP clients per backend URL for proxying, replacing per-request `httpx.AsyncClient` construction.
- Added runtime overrides for isolated daemon state and launchd labels/paths via `VLLMLX_STATE_DIR`, `VLLMLX_HOME`, `VLLMLX_LAUNCHD_LABEL`, and `VLLMLX_LAUNCHD_DIR`.
- Updated README default config example to `idle_timeout = 600` to match runtime defaults.
- Expanded CLI docs with backend scheduler/cache tuning keys and optimization profile guidance.
- Switched `vllmlx search` and `vllmlx ls` to packaged catalog size metadata so discovery and cache inspection work offline.
- Updated cached model verification to trust local snapshots when live Hub metadata is unavailable, improving offline startup behavior.
- Updated `vllmlx run` to auto-start the daemon when the local API is not already running.

### Added
- Added `vllmlx benchmark --json` for machine-readable benchmark summaries.
- Added `scripts/run_e2e.py` plus reusable `tests/e2e/` harness modules for real-model parity scenarios covering serve startup, launchd startup, API behavior, `vllmlx run`, benchmarking, downloads, LRU reuse, and live backend knob propagation.
- Added daemon config key `daemon.health_ttl_seconds` (default `1.0`) to cache backend health checks per model slot.
- Added daemon state tests covering loaded-model/supervisor consistency, health TTL cache hits, health TTL expiry re-probes, and unhealthy slot replacement.
- Added integration coverage that guards against a second supervisor lookup on model-targeted proxy requests.
- Added new backend scheduler config keys: `max_num_batched_tokens`, `scheduler_policy`, `prefill_step_size`, `enable_prefix_cache`, `prefix_cache_size`, `chunked_prefill_tokens`, and `mid_prefill_save_interval`.
- Added docs/dependency-upgrade-validation.md with phased benchmark + acceptance gates for MLX dependency upgrades.
- Added a generated `mlx-community` model catalog at `src/vllmlx/models/data/mlx_community_models.json` with alias, description, type, release date, size, and updated metadata for aliasing/search.
- Added `scripts/update_mlx_community_catalog.py` to refresh the packaged model catalog from Hugging Face.
- Added `vllmlx.models.catalog` helpers for loading catalog entries and performing metadata search.
- Added `vllmlx search` to query the packaged model catalog by alias/repo/type/description, with table and JSON output.
- Added `vllmlx ls --type <text|vision|embedding|audio>` to filter downloaded models by catalog type metadata.
- Fixed `vllmlx search --type ...` filtering so type filtering is applied before result limiting.
