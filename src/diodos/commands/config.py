import typer

from diodos.utils.config import get_config_path, open_config_file

def main() -> None:
    """
    This command will open the configuration file in the default text editor, allowing you to view or modify the settings. If the configuration file does not exist, it will be created with default values.
    """
    config_path = get_config_path()
    typer.echo(f"Opening configuration file: {config_path}")
    open_config_file(config_path)