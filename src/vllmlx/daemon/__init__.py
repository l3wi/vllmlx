"""Daemon module for vllmlx API server."""

from vllmlx.daemon.state import DaemonState, get_state, init_state

__all__ = ["DaemonState", "get_state", "init_state"]

# Note: server and routes are imported lazily to avoid loading
# uvicorn/fastapi when just importing the module
