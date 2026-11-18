import signal
import sys
import time

import typer
import logging

from diodos.utils.background import AlreadyRunning, daemon_lock
from diodos.utils.config import ConfigError, load_config
from diodos.utils.network import LoginResult, ensure_logged_in

logger = logging.getLogger(__name__)


def main() -> None:
    """
    This command will start the daemon process, monitoring network connections for captive portals. When a captive portal is detected, the daemon will attempt to automatically log in using the provided credentials or configuration.
    """
    logger.debug("Starting the daemon process.")
    try:
        config = load_config(create_if_missing=False)
    except (FileNotFoundError, ConfigError) as e:
        typer.echo(f"Error: {e}")
        logger.error("Cannot start the daemon: %s", e)
        raise typer.Exit(code=1)

    # `diodos stop` sends SIGTERM. Turning it into SystemExit runs the cleanup
    # below instead of dying on the spot with the PID file left behind.
    if sys.platform != "win32":
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

    try:
        with daemon_lock():
            typer.echo("Starting the diodos daemon...")
            logger.info("Starting the diodos daemon...")
            _run(config)
    except AlreadyRunning as e:
        typer.echo(str(e))
        logger.info("%s", e)
        raise typer.Exit(code=1)
    except KeyboardInterrupt:
        typer.echo("\nDaemon stopped by user.")
        logger.info("Daemon stopped by user.")


def _run(config: dict) -> None:
    while True:
        # Reloaded every round, so edits apply without a restart. A broken
        # edit keeps the last good config running rather than killing the
        # daemon.
        try:
            config = load_config(create_if_missing=False)
        except (FileNotFoundError, ConfigError) as e:
            logger.error("Keeping the previous config: %s", e)

        logger.debug("Checking network status.")
        result, network, ssid = ensure_logged_in(config)

        if result is LoginResult.LOGGED_IN:
            typer.echo(f"Logged in to {network['name']}.")
        elif result is LoginResult.FAILED:
            typer.echo(f"Login to {network['name']} failed. Check the credentials and login url.")

        time.sleep(config["interval"])
