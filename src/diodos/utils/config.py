import os
import sys
import subprocess
from pathlib import Path
import logging

from tomlkit import load

logger = logging.getLogger(__name__)


def get_config_path() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library/Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))

    logger.debug("Determined configuration path: %s", base / "diodos" / "config.toml")
    return base / "diodos" / "config.toml"


def load_config(path: str | Path | None = None) -> dict:
    """Load the diodos configuration from TOML."""
    config_path = Path(path).expanduser() if path else get_config_path()

    if not config_path.exists():
        logger.debug("Config file not found.")
        open_config_file(config_path)
        raise FileNotFoundError(f"Config file not found. Created default at: {config_path}")

    with config_path.open("rb") as file:
        return load(file).unwrap()


def open_config_file(path: str | Path) -> None:
    path = Path(path)

    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()

        logger.debug("Creating default config file at: %s", path)
        with path.open("w") as file:
            with open(Path(__file__).parent / "sample.config.toml", "r") as default_file:
                file.write(default_file.read())

    logger.debug("Opening configuration file: %s", path)
    if sys.platform == "win32":
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=False)
    else:
        subprocess.run(["xdg-open", str(path)], check=False)