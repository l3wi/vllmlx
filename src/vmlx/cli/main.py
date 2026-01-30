"""Main CLI entry point for vmlx."""

import os
import sys
import warnings

# Suppress TensorFlow/PyTorch not found warnings from transformers
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

# Suppress all deprecation warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", message=".*PyTorch.*")
warnings.filterwarnings("ignore", message=".*TensorFlow.*")
warnings.filterwarnings("ignore", message=".*Flax.*")
warnings.filterwarnings("ignore", message=".*slow image processor.*")
warnings.filterwarnings("ignore", message=".*deprecated.*")

# Monkey-patch mlx to suppress its deprecation warning
try:
    import mlx.core as mx
    _original_device_info = getattr(mx.metal, 'device_info', None)
    if _original_device_info:
        def _quiet_device_info():
            import io
            old_stderr = sys.stderr
            sys.stderr = io.StringIO()
            try:
                return mx.device_info()
            finally:
                sys.stderr = old_stderr
        mx.metal.device_info = _quiet_device_info
except ImportError:
    pass

import click

from vmlx import __version__
from vmlx.cli.config_cmd import config_cmd
from vmlx.cli.daemon_cmd import daemon
from vmlx.cli.ls import ls
from vmlx.cli.pull import pull
from vmlx.cli.rm import rm
from vmlx.cli.run import run
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
cli.add_command(run)
cli.add_command(config_cmd, name="config")
cli.add_command(serve)
cli.add_command(daemon)


if __name__ == "__main__":
    cli()
