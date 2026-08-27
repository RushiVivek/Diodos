import typer

from diodos.utils.background import launch_daemon

def main() -> None:
    """
    This command launches the diodos daemon in the background.
    """
    typer.echo("Launching the diodos daemon in the background...")
    launch_daemon()
    typer.echo("Daemon launched successfully. It will continue to monitor network connections for captive portals.")