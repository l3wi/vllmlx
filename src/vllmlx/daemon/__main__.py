"""Entry point for running daemon directly: python -m vllmlx.daemon

This module allows the daemon to be started via launchd with:
    ProgramArguments: [python, -m, vllmlx.daemon]
"""

from vllmlx.config import Config
from vllmlx.daemon.server import run_server

if __name__ == "__main__":
    config = Config.load()
    run_server(
        host=config.daemon.host,
        port=config.daemon.port,
        log_level=config.daemon.log_level,
    )
