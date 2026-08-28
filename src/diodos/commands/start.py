import typer
import logging

from diodos.utils.background import launch_daemon
from diodos.utils.config import load_config

logger = logging.getLogger(__name__)


def main() -> None:
    """
    This command launches the diodos daemon in the background.
    """
    logger.debug("Starting the start command.")

    # Checked here rather than in the daemon: this is the foreground process,
    # so a first-run setup prompt and any error actually reach the user.
    try:
        load_config()
    except FileNotFoundError as e:
        typer.echo(f"Error: {e}")
        logger.error("Configuration file not found: %s", e)
        raise typer.Exit(code=1)

    typer.echo("Launching the diodos daemon in the background...")
    logger.info("Launching the diodos daemon in the background.")

    if not launch_daemon():
        typer.echo("A diodos daemon is already running.")
        raise typer.Exit(code=0)

    typer.echo("Daemon launched successfully. It will continue to monitor network connections for captive portals.")
    logger.info("Daemon launched successfully. It will continue to monitor network connections for captive portals.")
