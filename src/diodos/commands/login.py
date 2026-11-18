import typer
import logging

from diodos.utils.config import ConfigError, load_config
from diodos.utils.network import LoginResult, ensure_logged_in

logger = logging.getLogger(__name__)


def main() -> None:
    """
    This command will perform a one-time check for a captive portal and attempt to log in if one is detected. It is useful for testing the configuration or manually triggering the login process without running the daemon continuously.
    """
    logger.debug("Starting one-time login check.")
    try:
        config = load_config()
    except (FileNotFoundError, ConfigError) as e:
        typer.echo(f"Error: {e}")
        logger.error("Cannot load config: %s", e)
        raise typer.Exit(code=1)

    result, network, ssid = ensure_logged_in(config)

    if result is LoginResult.ONLINE:
        typer.echo("No captive portal detected. You are already connected to the internet.")
    elif result is LoginResult.UNKNOWN_NETWORK:
        name = repr(ssid) if ssid else "this network (could not read its Wi-Fi name)"
        typer.echo(f"Offline, but no configured network covers {name}. Add it to `ssids` in the config.")
        raise typer.Exit(code=1)
    elif result is LoginResult.LOGGED_IN:
        typer.echo(f"Login successful! ({network['name']})")
    else:
        typer.echo(f"Login to {network['name']} failed. Please check your credentials or configuration.")
        raise typer.Exit(code=1)
