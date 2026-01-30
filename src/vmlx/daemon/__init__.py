"""Daemon module for vmlx API server."""

from vmlx.daemon.state import DaemonState, get_state, init_state

__all__ = ["DaemonState", "get_state", "init_state"]

# Note: server and routes are imported lazily to avoid loading
# uvicorn/fastapi when just importing the module
