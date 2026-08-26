import time
import typer

from .utils.config import get_config_path, load_config, open_config_file
from .utils.network import network_check, attempt_login, attempt_logout

app = typer.Typer(no_args_is_help=True)
context_settings = dict(help_option_names=["-h", "--help"])

@app.callback(context_settings=context_settings)
def callback() -> None:
    """
    Diodos is a command-line tool that helps you automatically log in to captive portals on saved Wi-Fi networks. It monitors network connections and detects when a captive portal is present, allowing you to seamlessly authenticate without manual intervention.
    """

@app.command()
def run() -> None:
    """
    This command will start the daemon process and keep it running in the background, monitoring network connections for captive portals. When a captive portal is detected, the daemon will attempt to automatically log in using the provided credentials or configuration.
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

@app.command()
def login() -> None:
    """
    This command will perform a one-time check for a captive portal and attempt to log in if one is detected. It is useful for testing the configuration or manually triggering the login process without running the daemon continuously.
    """
    try:
        config = load_config()
    except FileNotFoundError as e:
        typer.echo(f"Error: {e}")
        raise typer.Exit(code=1)

    check = network_check(config)
    if check:
        typer.echo("Captive portal detected. Attempting to log in...")
        login_success = attempt_login(config)
        if login_success:
            typer.echo("Login successful!")
        else:
            typer.echo("Login failed. Please check your credentials or configuration.")
    else:
        typer.echo("No captive portal detected. You are already connected to the internet.")


@app.command()
def logout() -> None:
    """
    This command will attempt to log out from the captive portal using the provided configuration. It is useful for manually logging out from the network when needed.
    """
    try:
        config = load_config()
    except FileNotFoundError as e:
        typer.echo(f"Error: {e}")
        raise typer.Exit(code=1)

    logout_success = attempt_logout(config)
    if logout_success:
        typer.echo("Logout successful!")
    else:
        typer.echo("Logout failed. Please check your configuration or network status.")

@app.command()
def config() -> None:
    """
    This command will open the configuration file in the default text editor, allowing you to view or modify the settings. If the configuration file does not exist, it will be created with default values.
    """
    config_path = get_config_path()
    typer.echo(f"Opening configuration file: {config_path}")
    open_config_file(config_path)

