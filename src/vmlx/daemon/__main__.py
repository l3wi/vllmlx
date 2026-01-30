"""Entry point for running daemon directly: python -m vmlx.daemon

This module allows the daemon to be started via launchd with:
    ProgramArguments: [python, -m, vmlx.daemon]
"""

from vmlx.config import Config
from vmlx.daemon.server import run_server

if __name__ == "__main__":
    config = Config.load()
    run_server(
        host=config.daemon.host,
        port=config.daemon.port,
        log_level=config.daemon.log_level,
    )
