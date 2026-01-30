"""CLI command for serving the vmlx API."""

import click

from vmlx.config import Config


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
    """Start the vmlx API server in foreground.

    The server provides an OpenAI-compatible API for vision-language models
    using MLX-VLM on Apple Silicon.

    \b
    Examples:
        vmlx serve                    # Start with defaults (localhost:11434)
        vmlx serve --port 8080        # Start on port 8080
        vmlx serve --host 0.0.0.0     # Allow external connections
    """
    from vmlx.daemon.server import run_server

    config = Config.load()

    click.echo(f"Starting vmlx server on {host or config.daemon.host}:{port or config.daemon.port}")
    click.echo("Press Ctrl+C to stop")
    click.echo()

    run_server(
        host=host or config.daemon.host,
        port=port or config.daemon.port,
        log_level=log_level or config.daemon.log_level,
    )
