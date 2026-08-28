import time
import typer
import logging

from diodos.utils.config import load_config
from diodos.utils.network import network_check, attempt_login

logger = logging.getLogger(__name__)


def main() -> None:
    """
    This command will start the daemon process, monitoring network connections for captive portals. When a captive portal is detected, the daemon will attempt to automatically log in using the provided credentials or configuration.
    """
    logger.debug("Starting the daemon process.")
    try:
        config = load_config()
    except FileNotFoundError as e:
        typer.echo(f"Error: {e}")
        logger.error("Configuration file not found: %s", e)
        raise typer.Exit(code=1)

    typer.echo("Starting the diodos daemon...")
    logger.info("Starting the diodos daemon...")
    interval = config.get("network_check", {}).get("interval", 60)
    logger.debug("Network check interval set to %s seconds.", interval)

    try:
        next_run = time.monotonic()
        while True:
            now = time.monotonic()
            if now >= next_run:
                logger.debug("Checking network status.")
                check = network_check(config)
                if check:
                    typer.echo("Captive portal detected. Attempting to log in...")
                    logger.info("Captive portal detected. Attempting to log in...")
                    login_success = attempt_login(config)
                    if login_success:
                        typer.echo("Login successful!")
                        logger.info("Login successful!")
                    else:
                        typer.echo("Login failed. Please check your credentials or configuration.")
                        logger.error("Login failed.")

                next_run = now + interval  # Default to 60 seconds if not specified

            time.sleep(5)  # Sleep for a short duration to avoid busy waiting
    except KeyboardInterrupt:
        typer.echo("\nDaemon stopped by user.")
        logger.info("Daemon stopped by user.")
        raise typer.Exit(code=0)