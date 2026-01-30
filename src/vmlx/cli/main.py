"""Main CLI entry point for vmlx."""

import click

from vmlx import __version__
from vmlx.cli.config_cmd import config_cmd
from vmlx.cli.ls import ls
from vmlx.cli.pull import pull
from vmlx.cli.rm import rm
from vmlx.cli.serve import serve


@click.group()
@click.version_option(version=__version__, prog_name="vmlx")
def cli():
    """vmlx - Ollama-style CLI for MLX-VLM.

    Manage and run vision-language models on Apple Silicon.
    """
    pass


# Register commands
cli.add_command(pull)
cli.add_command(ls)
cli.add_command(rm)
cli.add_command(config_cmd, name="config")
cli.add_command(serve)


if __name__ == "__main__":
    cli()
