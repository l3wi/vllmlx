# Task: Idle Management

**Phase**: 3  
**Branch**: `feat/vllmlx-phase-3`  
**Plan**: [docs/plans/vllmlx.md](../plans/vllmlx.md)  
**Spec**: [docs/specs/vllmlx-spec.md](../specs/vllmlx-spec.md)  
**Status**: pending  
**Parallel With**: Phase 4, Phase 5

---

## Objective

Implement idle timeout that unloads the model from memory after configurable inactivity period, with proper memory cleanup to return RAM to baseline.

---

## Acceptance Criteria

- [ ] Model unloads automatically after idle timeout (default 60s)
- [ ] Idle timeout configurable via `vllmlx config set daemon.idle_timeout 120`
- [ ] RAM usage returns to <50MB after model unload
- [ ] New request after unload triggers reload (cold start)
- [ ] Requests during model transition are queued, not rejected
- [ ] Timer resets on each request
- [ ] `GET /v1/status` shows `idle_seconds_remaining` when model loaded
- [ ] Unload logged with model name and idle duration
- [ ] All tests pass
- [ ] Lint clean

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `src/vllmlx/daemon/idle.py` | create | IdleTimer class with asyncio task |
| `src/vllmlx/daemon/state.py` | modify | Add idle tracking fields |
| `src/vllmlx/daemon/server.py` | modify | Start/stop idle timer in lifespan |
| `src/vllmlx/daemon/routes.py` | modify | Update /v1/status endpoint |
| `tests/unit/test_idle.py` | create | Unit tests for idle timer logic |
| `tests/integration/test_idle_timeout.py` | create | Integration test for timeout |

---

## Implementation Notes

### IdleTimer (idle.py)

```python
import asyncio
from datetime import datetime, timedelta
from typing import Callable, Optional
import logging

logger = logging.getLogger(__name__)

class IdleTimer:
    """Background timer that triggers model unload after inactivity."""
    
    def __init__(
        self,
        timeout_seconds: int,
        on_timeout: Callable[[], None],
        check_interval: int = 10,
    ):
        self.timeout_seconds = timeout_seconds
        self.on_timeout = on_timeout
        self.check_interval = check_interval
        self._task: Optional[asyncio.Task] = None
        self._last_activity: Optional[datetime] = None
        self._running = False
    
    def touch(self) -> None:
        """Reset the idle timer (called on each request)."""
        self._last_activity = datetime.now()
    
    def start(self) -> None:
        """Start the background timer task."""
        if self._running:
            return
        self._running = True
        self._last_activity = datetime.now()
        self._task = asyncio.create_task(self._run())
        logger.info(f"Idle timer started (timeout: {self.timeout_seconds}s)")
    
    def stop(self) -> None:
        """Stop the background timer task."""
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("Idle timer stopped")
    
    @property
    def seconds_until_timeout(self) -> Optional[float]:
        """Seconds remaining until timeout, or None if not tracking."""
        if not self._last_activity:
            return None
        elapsed = (datetime.now() - self._last_activity).total_seconds()
        remaining = self.timeout_seconds - elapsed
        return max(0, remaining)
    
    async def _run(self) -> None:
        """Background task that checks for idle timeout."""
        while self._running:
            try:
                await asyncio.sleep(self.check_interval)
                
                if not self._last_activity:
                    continue
                
                elapsed = (datetime.now() - self._last_activity).total_seconds()
                
                if elapsed >= self.timeout_seconds:
                    logger.info(f"Idle timeout reached ({elapsed:.1f}s)")
                    await self._trigger_timeout()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in idle timer: {e}")
    
    async def _trigger_timeout(self) -> None:
        """Trigger the timeout callback."""
        try:
            # Run callback (may be sync or async)
            result = self.on_timeout()
            if asyncio.iscoroutine(result):
                await result
            self._last_activity = None  # Stop tracking until next request
        except Exception as e:
            logger.error(f"Error in timeout callback: {e}")
```

### State Modifications (state.py)

Add to DaemonState:

```python
from vllmlx.daemon.idle import IdleTimer

@dataclass
class DaemonState:
    # ... existing fields ...
    idle_timer: Optional[IdleTimer] = None
    
    def start_idle_tracking(self, timeout: int) -> None:
        """Start tracking idle time for loaded model."""
        if self.idle_timer:
            self.idle_timer.stop()
        
        self.idle_timer = IdleTimer(
            timeout_seconds=timeout,
            on_timeout=self._unload_on_idle,
        )
        self.idle_timer.start()
    
    def stop_idle_tracking(self) -> None:
        """Stop idle tracking (model unloaded)."""
        if self.idle_timer:
            self.idle_timer.stop()
            self.idle_timer = None
    
    def touch(self) -> None:
        """Update activity timestamp."""
        self.last_request_at = datetime.now()
        if self.idle_timer:
            self.idle_timer.touch()
    
    async def _unload_on_idle(self) -> None:
        """Callback when idle timeout triggers."""
        async with self.lock:
            if self.model:
                from vllmlx.models.manager import ModelManager
                model_name = self.loaded_model_name
                ModelManager.unload_model(self.model, self.processor)
                self.model = None
                self.processor = None
                self.config = None
                self.loaded_model_name = None
                self.loaded_at = None
                logger.info(f"Unloaded model '{model_name}' due to idle timeout")
```

### Server Integration (server.py)

Modify lifespan to handle idle timer:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_state()
    yield
    # Shutdown
    state = get_state()
    state.stop_idle_tracking()
    if state.model:
        ModelManager.unload_model(state.model, state.processor)
```

### Routes Integration (routes.py)

Start idle tracking after model load:

```python
@router.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    # ... existing code ...
    
    async with state.lock:
        if state.loaded_model_name != model_path:
            # ... load model ...
            
            # Start idle tracking after successful load
            config = Config.load()
            state.start_idle_tracking(config.daemon.idle_timeout)
        
        state.touch()  # Reset idle timer
    
    # ... rest of handler ...
```

Update /v1/status endpoint:

```python
@router.get("/v1/status")
async def status():
    state = get_state()
    return {
        "running": True,
        "pid": os.getpid(),
        "uptime_seconds": (datetime.now() - state.start_time).total_seconds(),
        "loaded_model": state.loaded_model_name,
        "model_loaded_at": state.loaded_at.isoformat() if state.loaded_at else None,
        "last_request_at": state.last_request_at.isoformat() if state.last_request_at else None,
        "idle_seconds_remaining": state.idle_timer.seconds_until_timeout if state.idle_timer else None,
        "memory_usage_mb": get_memory_usage_mb(),
        "idle_timeout": Config.load().daemon.idle_timeout,
    }

def get_memory_usage_mb() -> float:
    """Get current process memory usage in MB."""
    import resource
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return usage.ru_maxrss / 1024 / 1024  # Convert to MB on macOS
```

### Memory Cleanup

Ensure thorough cleanup in ModelManager.unload_model:

```python
@staticmethod
def unload_model(model: Any, processor: Any) -> None:
    """Unload model and free memory."""
    import gc
    import mlx.core as mx
    
    # Delete references
    del model
    del processor
    
    # Force garbage collection
    gc.collect()
    
    # Clear MLX metal cache (returns GPU memory)
    try:
        mx.metal.clear_cache()
    except AttributeError:
        pass  # Older MLX versions may not have this
    
    # Additional GC pass after metal cache clear
    gc.collect()
```

---

## Testing Requirements

### Unit Tests (test_idle.py)

```python
import pytest
import asyncio
from vllmlx.daemon.idle import IdleTimer

@pytest.mark.asyncio
async def test_timer_triggers_after_timeout():
    triggered = False
    def on_timeout():
        nonlocal triggered
        triggered = True
    
    timer = IdleTimer(timeout_seconds=1, on_timeout=on_timeout, check_interval=0.1)
    timer.start()
    
    await asyncio.sleep(1.5)
    
    assert triggered
    timer.stop()

@pytest.mark.asyncio
async def test_touch_resets_timer():
    triggered = False
    def on_timeout():
        nonlocal triggered
        triggered = True
    
    timer = IdleTimer(timeout_seconds=1, on_timeout=on_timeout, check_interval=0.1)
    timer.start()
    
    await asyncio.sleep(0.5)
    timer.touch()  # Reset
    await asyncio.sleep(0.5)
    timer.touch()  # Reset again
    await asyncio.sleep(0.5)
    
    assert not triggered  # Should not have triggered
    timer.stop()

def test_seconds_until_timeout():
    timer = IdleTimer(timeout_seconds=60, on_timeout=lambda: None)
    timer.touch()
    
    remaining = timer.seconds_until_timeout
    assert 59 < remaining <= 60
```

### Integration Tests (test_idle_timeout.py)

```python
@pytest.mark.slow
@pytest.mark.asyncio
async def test_model_unloads_after_idle(test_client, loaded_model):
    """Test that model unloads after idle timeout."""
    # Configure short timeout for test
    # Make a request to load model
    # Wait for timeout + buffer
    # Check /v1/status shows no loaded model
    # Check memory returned to baseline
    pass
```

---

## Agent Instructions

1. Read Phase 2's state.py and routes.py to understand current structure
2. Create `IdleTimer` class with asyncio background task
3. Modify `DaemonState` to integrate idle tracking
4. Update routes to start timer on model load, touch on request
5. Update `/v1/status` endpoint with idle info
6. Ensure memory cleanup is thorough
7. Write unit tests for timer logic (fast, no model loading)
8. Write integration test (can be marked slow)
9. Test manually:
   ```bash
   vllmlx config set daemon.idle_timeout 30
   vllmlx serve &
   curl -X POST localhost:8000/v1/chat/completions -d '{"model":"qwen2-vl-2b-instruct-4bit","messages":[{"role":"user","content":"hi"}]}'
   # Wait 30+ seconds
   curl localhost:8000/v1/status  # Should show no loaded model
   ```
10. Run `ruff check` and `pytest`
11. Commit with `wt commit`
