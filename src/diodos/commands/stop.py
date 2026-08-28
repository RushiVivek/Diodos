import typer
import logging

from diodos.utils.background import stop_daemon

logger = logging.getLogger(__name__)


def main() -> None:
    """
    This command will stop the daemon process if it is running. It is useful for gracefully shutting down the background monitoring of network connections.
    """
    logger.debug("Starting the stop command.")
    typer.echo("Stopping the diodos daemon...")
    logger.info("Stopping the diodos daemon.")
    daemon_stopped = stop_daemon()
    if daemon_stopped:
        typer.echo("Daemon stopped.")
        logger.info("Daemon stopped.")
    else:
        typer.echo("Failed to stop daemon.")
        logger.error("Failed to stop daemon.")