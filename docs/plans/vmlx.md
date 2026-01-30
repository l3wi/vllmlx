# vmlx Implementation Plan

**Spec**: [docs/specs/vmlx-spec.md](../specs/vmlx-spec.md)  
**PRD**: [docs/prds/vmlx.md](../prds/vmlx.md)  
**Created**: 2026-01-30  
**Status**: pending

---

## Orchestration

**Feature Branch**: `feat/vmlx`  
**Base Branch**: `main`

All phase branches will be created from the feature branch (not main):
- Phase branches merge back to `feat/vmlx`
- Single PR from `feat/vmlx` to `main` when all phases complete

---

## Phases

### Phase 1: Core Infrastructure
- **Branch**: `feat/vmlx-phase-1`
- **Base**: `feat/vmlx`
- **Status**: pending
- **Depends On**: none
- **Tasks**: [docs/tasks/vmlx-phase-1.md](../tasks/vmlx-phase-1.md)
- **Files**:
  - `pyproject.toml`
  - `src/vmlx/__init__.py`
  - `src/vmlx/__main__.py`
  - `src/vmlx/config/config.py`
  - `src/vmlx/models/aliases.py`
  - `src/vmlx/models/registry.py`
  - `src/vmlx/cli/main.py`
  - `src/vmlx/cli/pull.py`
  - `src/vmlx/cli/ls.py`
  - `src/vmlx/cli/rm.py`
  - `src/vmlx/cli/config_cmd.py`
  - `tests/unit/test_config.py`
  - `tests/unit/test_aliases.py`

### Phase 2: Daemon & API Server
- **Branch**: `feat/vmlx-phase-2`
- **Base**: `feat/vmlx`
- **Status**: pending
- **Depends On**: Phase 1
- **Tasks**: [docs/tasks/vmlx-phase-2.md](../tasks/vmlx-phase-2.md)
- **Files**:
  - `src/vmlx/daemon/server.py`
  - `src/vmlx/daemon/routes.py`
  - `src/vmlx/daemon/state.py`
  - `src/vmlx/models/manager.py`
  - `src/vmlx/cli/serve.py`
  - `tests/integration/test_api.py`

### Phase 3: Idle Management
- **Branch**: `feat/vmlx-phase-3`
- **Base**: `feat/vmlx`
- **Status**: pending
- **Depends On**: Phase 2
- **Parallel With**: Phase 4, Phase 5
- **Tasks**: [docs/tasks/vmlx-phase-3.md](../tasks/vmlx-phase-3.md)
- **Files**:
  - `src/vmlx/daemon/idle.py`
  - `src/vmlx/daemon/state.py` (modify - add idle tracking)
  - `tests/unit/test_idle.py`
  - `tests/integration/test_idle_timeout.py`

### Phase 4: launchd Integration
- **Branch**: `feat/vmlx-phase-4`
- **Base**: `feat/vmlx`
- **Status**: pending
- **Depends On**: Phase 2
- **Parallel With**: Phase 3, Phase 5
- **Tasks**: [docs/tasks/vmlx-phase-4.md](../tasks/vmlx-phase-4.md)
- **Files**:
  - `src/vmlx/daemon/launchd.py`
  - `src/vmlx/cli/daemon_cmd.py`
  - `tests/unit/test_launchd.py`
  - `tests/integration/test_daemon_lifecycle.py`

### Phase 5: Interactive Chat
- **Branch**: `feat/vmlx-phase-5`
- **Base**: `feat/vmlx`
- **Status**: pending
- **Depends On**: Phase 2
- **Parallel With**: Phase 3, Phase 4
- **Tasks**: [docs/tasks/vmlx-phase-5.md](../tasks/vmlx-phase-5.md)
- **Files**:
  - `src/vmlx/cli/run.py`
  - `src/vmlx/chat/repl.py`
  - `tests/unit/test_repl.py`

### Phase 6: Documentation & Release
- **Branch**: `feat/vmlx-phase-6`
- **Base**: `feat/vmlx`
- **Status**: pending
- **Depends On**: Phase 3, Phase 4, Phase 5
- **Tasks**: [docs/tasks/vmlx-phase-6.md](../tasks/vmlx-phase-6.md)
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
- **Feature Branch**: `feat/vmlx`

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

1. Each phase branch merges to `feat/vmlx` via squash merge
2. Parallel phases (3, 4, 5) merge in any order as they complete
3. After Phase 6 completes, create PR from `feat/vmlx` → `main`
4. Final PR includes all squashed phase commits
