"""CLI command for serving the vllmlx API."""

import click

from vllmlx.config import Config


@click.command()
@click.option(
    "--port",
    "-p",
    default=None,
    type=int,
    help="Port to listen on (default: 11434)",
)
@click.option(
    "--host",
    "-h",
    default=None,
    type=str,
    help="Host to bind to (default: 127.0.0.1)",
)
@click.option(
    "--log-level",
    "-l",
    default=None,
    type=click.Choice(["debug", "info", "warning", "error", "critical"]),
    help="Log level (default: info)",
)
def serve(port: int | None, host: str | None, log_level: str | None):
    """Start the vllmlx API server in foreground.

    The server provides an OpenAI-compatible API by supervising
    an internal vllm-mlx backend worker on Apple Silicon.

    \b
    Examples:
        vllmlx serve                    # Start with defaults (localhost:11434)
        vllmlx serve --port 8080        # Start on port 8080
        vllmlx serve --host 0.0.0.0     # Allow external connections
    """
    from vllmlx.daemon.server import run_server

    config = Config.load()

    click.echo(
        f"Starting vllmlx server on {host or config.daemon.host}:{port or config.daemon.port}"
    )
    click.echo("Press Ctrl+C to stop")
    click.echo()

    run_server(
        host=host or config.daemon.host,
        port=port or config.daemon.port,
        log_level=log_level or config.daemon.log_level,
    )
