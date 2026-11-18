import typer
import logging

from diodos.utils.background import DaemonError, stop_daemon

logger = logging.getLogger(__name__)


def main() -> None:
    """
    This command will stop the daemon process if it is running. It is useful for gracefully shutting down the background monitoring of network connections.
    """
    logger.debug("Starting the stop command.")
    typer.echo("Stopping the diodos daemon...")

    try:
        stopped = stop_daemon()
    except DaemonError as e:
        typer.echo(f"Error: {e}")
        logger.error("%s", e)
        raise typer.Exit(code=1)

    typer.echo("Daemon stopped." if stopped else "No running diodos daemon found.")
