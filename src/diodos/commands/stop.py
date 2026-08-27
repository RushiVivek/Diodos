import typer

from diodos.utils.background import stop_daemon

def main() -> None:
    """
    This command will stop the daemon process if it is running. It is useful for gracefully shutting down the background monitoring of network connections.
    """
    typer.echo("Stopping the diodos daemon...")
    daemon_stopped = stop_daemon()
    if daemon_stopped:
        typer.echo("Daemon stopped.")
    else:
        typer.echo("Failed to stop daemon.")