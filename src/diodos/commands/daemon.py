import time
import typer

from diodos.utils.config import load_config
from diodos.utils.network import network_check, attempt_login

def main() -> None:
    """
    This command will start the daemon process, monitoring network connections for captive portals. When a captive portal is detected, the daemon will attempt to automatically log in using the provided credentials or configuration.
    """
    try:
        config = load_config()
    except FileNotFoundError as e:
        typer.echo(f"Error: {e}")
        raise typer.Exit(code=1)

    typer.echo("Starting the diodos daemon...")
    interval = config.get("network_check", {}).get("interval", 60)

    try:
        next_run = time.monotonic()
        while True:
            now = time.monotonic()
            if now >= next_run:
                check = network_check(config)
                if check:
                    typer.echo("Captive portal detected. Attempting to log in...")
                    login_success = attempt_login(config)
                    if login_success:
                        typer.echo("Login successful!")
                    else:
                        typer.echo("Login failed. Please check your credentials or configuration.")

                next_run = now + interval  # Default to 60 seconds if not specified

            time.sleep(5)  # Sleep for a short duration to avoid busy waiting
    except KeyboardInterrupt:
        typer.echo("\nDaemon stopped by user.")
        raise typer.Exit(code=0)