import typer
import logging

from diodos.utils.config import load_config
from diodos.utils.network import attempt_login, network_check

logger = logging.getLogger(__name__)


def main() -> None:
    """
    This command will perform a one-time check for a captive portal and attempt to log in if one is detected. It is useful for testing the configuration or manually triggering the login process without running the daemon continuously.
    """
    logger.debug("Starting one-time login check.")
    try:
        config = load_config()
    except FileNotFoundError as e:
        typer.echo(f"Error: {e}")
        logger.error("Configuration file not found: %s", e)
        raise typer.Exit(code=1)

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
    else:
        typer.echo("No captive portal detected. You are already connected to the internet.")
        logger.info("No captive portal detected. You are already connected to the internet.")