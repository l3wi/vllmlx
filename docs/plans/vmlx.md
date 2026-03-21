# vllmlx Implementation Plan

**Spec**: [docs/specs/vllmlx-spec.md](../specs/vllmlx-spec.md)  
**PRD**: [docs/prds/vllmlx.md](../prds/vllmlx.md)  
**Created**: 2026-01-30  
**Status**: pending

---

## Orchestration

**Feature Branch**: `feat/vllmlx`  
**Base Branch**: `main`

All phase branches will be created from the feature branch (not main):
- Phase branches merge back to `feat/vllmlx`
- Single PR from `feat/vllmlx` to `main` when all phases complete

---

## Phases

### Phase 1: Core Infrastructure
- **Branch**: `feat/vllmlx-phase-1`
- **Base**: `feat/vllmlx`
- **Status**: pending
- **Depends On**: none
- **Tasks**: [docs/tasks/vllmlx-phase-1.md](../tasks/vllmlx-phase-1.md)
- **Files**:
  - `pyproject.toml`
  - `src/vllmlx/__init__.py`
  - `src/vllmlx/__main__.py`
  - `src/vllmlx/config/config.py`
  - `src/vllmlx/models/aliases.py`
  - `src/vllmlx/models/registry.py`
  - `src/vllmlx/cli/main.py`
  - `src/vllmlx/cli/pull.py`
  - `src/vllmlx/cli/ls.py`
  - `src/vllmlx/cli/rm.py`
  - `src/vllmlx/cli/config_cmd.py`
  - `tests/unit/test_config.py`
  - `tests/unit/test_aliases.py`

### Phase 2: Daemon & API Server
- **Branch**: `feat/vllmlx-phase-2`
- **Base**: `feat/vllmlx`
- **Status**: pending
- **Depends On**: Phase 1
- **Tasks**: [docs/tasks/vllmlx-phase-2.md](../tasks/vllmlx-phase-2.md)
- **Files**:
  - `src/vllmlx/daemon/server.py`
  - `src/vllmlx/daemon/routes.py`
  - `src/vllmlx/daemon/state.py`
  - `src/vllmlx/models/manager.py`
  - `src/vllmlx/cli/serve.py`
  - `tests/integration/test_api.py`

### Phase 3: Idle Management
- **Branch**: `feat/vllmlx-phase-3`
- **Base**: `feat/vllmlx`
- **Status**: pending
- **Depends On**: Phase 2
- **Parallel With**: Phase 4, Phase 5
- **Tasks**: [docs/tasks/vllmlx-phase-3.md](../tasks/vllmlx-phase-3.md)
- **Files**:
  - `src/vllmlx/daemon/idle.py`
  - `src/vllmlx/daemon/state.py` (modify - add idle tracking)
  - `tests/unit/test_idle.py`
  - `tests/integration/test_idle_timeout.py`

### Phase 4: launchd Integration
- **Branch**: `feat/vllmlx-phase-4`
- **Base**: `feat/vllmlx`
- **Status**: pending
- **Depends On**: Phase 2
- **Parallel With**: Phase 3, Phase 5
- **Tasks**: [docs/tasks/vllmlx-phase-4.md](../tasks/vllmlx-phase-4.md)
- **Files**:
  - `src/vllmlx/daemon/launchd.py`
  - `src/vllmlx/cli/daemon_cmd.py`
  - `tests/unit/test_launchd.py`
  - `tests/integration/test_daemon_lifecycle.py`

### Phase 5: Interactive Chat
- **Branch**: `feat/vllmlx-phase-5`
- **Base**: `feat/vllmlx`
- **Status**: pending
- **Depends On**: Phase 2
- **Parallel With**: Phase 3, Phase 4
- **Tasks**: [docs/tasks/vllmlx-phase-5.md](../tasks/vllmlx-phase-5.md)
- **Files**:
  - `src/vllmlx/cli/run.py`
  - `src/vllmlx/chat/repl.py`
  - `tests/unit/test_repl.py`

### Phase 6: Documentation & Release
- **Branch**: `feat/vllmlx-phase-6`
- **Base**: `feat/vllmlx`
- **Status**: pending
- **Depends On**: Phase 3, Phase 4, Phase 5
- **Tasks**: [docs/tasks/vllmlx-phase-6.md](../tasks/vllmlx-phase-6.md)
- **Files**:
  - `README.md`
  - `docs/installation.md`
  - `docs/cli-reference.md`
  - `docs/troubleshooting.md`
  - `.github/workflows/ci.yml`
  - `.github/workflows/release.yml`

---

## Execution Order

| Batch | Phases | Mode | Reason |
|-------|--------|------|--------|
| 1 | Phase 1 | Sequential | Foundational: project structure, config, model management CLI |
| 2 | Phase 2 | Sequential | Core daemon/API - required by all subsequent phases |
| 3 | Phase 3, 4, 5 | **Parallel** | Independent features: idle mgmt, launchd, chat - no file conflicts |
| 4 | Phase 6 | Sequential | Final: docs and release - requires all features complete |

---

## Parallel Safety Check

**Batch 3 Analysis:**

| Phase | Files | Overlap Check |
|-------|-------|---------------|
| Phase 3 | `daemon/idle.py`, `daemon/state.py` (idle fields only) | ✓ |
| Phase 4 | `daemon/launchd.py`, `cli/daemon_cmd.py` | ✓ |
| Phase 5 | `cli/run.py`, `chat/repl.py` | ✓ |

**Result**: ✅ No file overlaps detected - safe to parallelize

**Note**: Phase 3 modifies `daemon/state.py` to add idle tracking fields. Phase 2 creates the base `state.py`. Phases 4 and 5 read from state but don't modify it.

---

## Agent Configuration

- **Agent**: worker
- **Max Parallel**: 3 (for Batch 3)
- **Timeout**: 45 minutes per phase
- **Feature Branch**: `feat/vllmlx`

---

## Progress Tracking

| Phase | Status | Agent | Started | Completed |
|-------|--------|-------|---------|-----------|
| 1 | pending | - | - | - |
| 2 | pending | - | - | - |
| 3 | pending | - | - | - |
| 4 | pending | - | - | - |
| 5 | pending | - | - | - |
| 6 | pending | - | - | - |

---

## Merge Strategy

1. Each phase branch merges to `feat/vllmlx` via squash merge
2. Parallel phases (3, 4, 5) merge in any order as they complete
3. After Phase 6 completes, create PR from `feat/vllmlx` → `main`
4. Final PR includes all squashed phase commits
