import typer

from diodos.utils.config import load_config
from diodos.utils.network import attempt_logout

def main() -> None:
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