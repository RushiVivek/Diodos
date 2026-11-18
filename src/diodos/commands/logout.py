import typer
import logging

from diodos.utils.config import ConfigError, load_config
from diodos.utils.network import attempt_logout, select_network
from diodos.utils.wifi import current_ssid

logger = logging.getLogger(__name__)


def main() -> None:
    """
    This command will attempt to log out from the captive portal using the provided configuration. It is useful for manually logging out from the network when needed.
    """
    logger.debug("Starting one-time logout.")
    try:
        config = load_config()
    except (FileNotFoundError, ConfigError) as e:
        typer.echo(f"Error: {e}")
        logger.error("Cannot load config: %s", e)
        raise typer.Exit(code=1)

    ssid = current_ssid()
    network = select_network(config["networks"], ssid)

    if network is None:
        typer.echo(f"No configured network covers the current Wi-Fi network ({ssid or 'unknown'}).")
        raise typer.Exit(code=1)

    if network["logout"] is None:
        typer.echo(f"{network['name']} has no [networks.logout] url configured.")
        raise typer.Exit(code=1)

    if attempt_logout(network):
        typer.echo("Logout successful!")
        logger.info("Logged out of %s.", network["name"])
    else:
        typer.echo("Logout failed. Please check your configuration or network status.")
        logger.error("Logout from %s failed.", network["name"])
        raise typer.Exit(code=1)
