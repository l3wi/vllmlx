# Changelog

## Unreleased

### Changed
- Refactored daemon runtime state to a single slot map (`model_slots`) using a `ModelSlot` dataclass instead of parallel dictionaries.
- Replaced concrete supervisor type checks with a `SupervisorProtocol` contract for primary and per-model supervisors.
- Updated model-targeted proxy routing to reuse the supervisor returned by model loading, avoiding an immediate second supervisor lookup.

### Added
- Added daemon config key `daemon.health_ttl_seconds` (default `1.0`) to cache backend health checks per model slot.
- Added daemon state tests covering loaded-model/supervisor consistency, health TTL cache hits, health TTL expiry re-probes, and unhealthy slot replacement.
- Added integration coverage that guards against a second supervisor lookup on model-targeted proxy requests.
