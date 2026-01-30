"""FastAPI server for vmlx daemon."""

import signal
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI

from vmlx.daemon.routes import router
from vmlx.daemon.state import get_state, init_state


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan (startup/shutdown)."""
    # Startup
    init_state()

    yield

    # Shutdown - stop idle timer and unload model if loaded
    try:
        from vmlx.models.manager import ModelManager

        state = get_state()

        # Stop idle tracking first
        state.stop_idle_tracking()

        if state.model is not None:
            ModelManager.unload_model(state.model, state.processor)
            state.reset_model_state()
    except Exception:
        # Ignore errors during shutdown
        pass


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application
    """
    app = FastAPI(
        title="vmlx",
        description="Ollama-style API for MLX-VLM",
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
    """Run the vmlx server.

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
