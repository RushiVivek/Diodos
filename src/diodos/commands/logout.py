import typer
import logging

from diodos.utils.config import load_config
from diodos.utils.network import attempt_logout

logger = logging.getLogger(__name__)


def main() -> None:
    """
    This command will attempt to log out from the captive portal using the provided configuration. It is useful for manually logging out from the network when needed.
    """
    logger.debug("Starting one-time logout.")
    try:
        config = load_config()
    except FileNotFoundError as e:
        typer.echo(f"Error: {e}")
        logger.error("Configuration file not found: %s", e)
        raise typer.Exit(code=1)

    logout_success = attempt_logout(config)
    if logout_success:
        typer.echo("Logout successful!")
        logger.info("Logout successful!")
    else:
        typer.echo("Logout failed. Please check your configuration or network status.")
        logger.error("Logout failed.")