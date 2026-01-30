"""Config command for viewing and modifying configuration."""

import click
import toml
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

from vmlx.config import Config

console = Console()


@click.group(invoke_without_command=True)
@click.pass_context
def config_cmd(ctx):
    """View or modify vmlx configuration.

    Without arguments, displays the current configuration.

    Examples:

        vmlx config

        vmlx config set daemon.idle_timeout 120

        vmlx config get daemon.port
    """
    if ctx.invoked_subcommand is None:
        # No subcommand, show current config
        show_config()


def show_config():
    """Display current configuration."""
    config = Config.load()
    config_path = Config.path()

    # Convert to TOML string for display
    config_str = toml.dumps(config.model_dump())

    # Show path
    console.print(f"[dim]Config file: {config_path}[/dim]\n")

    # Show config with syntax highlighting
    syntax = Syntax(config_str, "toml", theme="monokai", line_numbers=False)
    console.print(Panel(syntax, title="Configuration", border_style="blue"))


@config_cmd.command()
@click.argument("key")
@click.argument("value")
def set(key: str, value: str):
    """Set a configuration value.

    KEY is a dot-separated path (e.g., daemon.port, aliases.my-model).

    Examples:

        vmlx config set daemon.idle_timeout 120

        vmlx config set daemon.port 8080

        vmlx config set aliases.my-model some-org/some-model-4bit
    """
    config = Config.load()

    try:
        config.set(key, value)
        config.save()
        console.print(f"[green]✓[/green] Set [cyan]{key}[/cyan] = [yellow]{value}[/yellow]")
    except KeyError as e:
        console.print(f"[red]✗[/red] Invalid key: {e}")
        raise SystemExit(1)


@config_cmd.command()
@click.argument("key")
def get(key: str):
    """Get a configuration value.

    KEY is a dot-separated path (e.g., daemon.port, aliases.my-model).

    Examples:

        vmlx config get daemon.idle_timeout

        vmlx config get aliases.my-model
    """
    config = Config.load()

    try:
        value = config.get(key)
        console.print(f"[cyan]{key}[/cyan] = [yellow]{value}[/yellow]")
    except KeyError as e:
        console.print(f"[red]✗[/red] Invalid key: {e}")
        raise SystemExit(1)


@config_cmd.command()
def path():
    """Show the config file path.

    Examples:

        vmlx config path
    """
    config_path = Config.path()
    console.print(str(config_path))
