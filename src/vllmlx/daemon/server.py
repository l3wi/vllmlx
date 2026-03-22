"""FastAPI server for vllmlx daemon."""

import logging
import signal
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI

from vllmlx.daemon.routes import router
from vllmlx.daemon.state import get_state, init_state

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan (startup/shutdown)."""
    # Startup
    state = init_state()
    should_preload = (
        state.config.daemon.preload_default_model
        or state.config.daemon.pin_default_model
    )
    default_model = state.resolve_default_model()

    if should_preload and default_model:
        async with state.lock:
            try:
                await state.supervisor.ensure_model(default_model)
                state.touch()
                logger.info("Preloaded default model '%s' at daemon startup", default_model)
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.warning("Failed to preload default model '%s': %s", default_model, exc)

    yield

    # Shutdown
    try:
        state = get_state()
        state.stop_idle_tracking()
        await state.shutdown()
    except Exception:
        # Ignore errors during shutdown
        pass


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application
    """
    app = FastAPI(
        title="vllmlx",
        description="Ollama-style API proxy for managed vllm-mlx workers",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(router)
    return app


def setup_signal_handlers():
    """Set up signal handlers for graceful shutdown."""

    def handle_sigterm(signum, frame):
        """Handle SIGTERM for graceful shutdown."""
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_sigterm)


def run_server(host: str = "127.0.0.1", port: int = 11434, log_level: str = "info"):
    """Run the vllmlx server.

    Args:
        host: Host to bind to (default: 127.0.0.1)
        port: Port to listen on (default: 11434)
        log_level: Uvicorn log level (default: info)
    """
    import uvicorn

    setup_signal_handlers()

    app = create_app()
    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level=log_level,
    )
    server = uvicorn.Server(config)
    server.run()
