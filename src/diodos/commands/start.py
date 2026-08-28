import typer
import logging

from diodos.utils.background import launch_daemon

logger = logging.getLogger(__name__)


def main() -> None:
    """
    This command launches the diodos daemon in the background.
    """
    logger.debug("Starting the start command.")
    typer.echo("Launching the diodos daemon in the background...")
    logger.info("Launching the diodos daemon in the background.")
    launch_daemon()
    typer.echo("Daemon launched successfully. It will continue to monitor network connections for captive portals.")
    logger.info("Daemon launched successfully. It will continue to monitor network connections for captive portals.")