import os
import sys
import subprocess
from pathlib import Path
import logging

from tomlkit import load

logger = logging.getLogger(__name__)


def get_config_path() -> Path:
    # An explicit override keeps tests and throwaway setups out of the real
    # per-user config directory, which macOS otherwise hardcodes.
    override = os.environ.get("DIODOS_CONFIG_DIR")

    if override:
        return Path(override).expanduser() / "config.toml"

    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library/Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))

    logger.debug("Determined configuration path: %s", base / "diodos" / "config.toml")
    return base / "diodos" / "config.toml"


def load_config(
    path: str | Path | None = None,
    create_if_missing: bool = True,
) -> dict:
    """
    Load the diodos configuration from TOML.

    Pass create_if_missing=False from anything running in the background: the
    missing-config path opens a text editor, which a detached daemon must never
    do.
    """
    config_path = Path(path).expanduser() if path else get_config_path()

    if not config_path.exists():
        logger.debug("Config file not found.")

        if not create_if_missing:
            raise FileNotFoundError(
                f"No config file at: {config_path}. Run `diodos config` to create one."
            )

        open_config_file(config_path)
        raise FileNotFoundError(f"Config file not found. Created default at: {config_path}")

    # utf-8-sig drops the BOM that Windows editors and PowerShell add, which
    # tomlkit would otherwise reject as a stray character before the first key.
    with config_path.open("r", encoding="utf-8-sig") as file:
        return load(file).unwrap()


def open_config_file(path: str | Path) -> None:
    path = Path(path)

    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)

        logger.debug("Creating default config file at: %s", path)

        sample = Path(__file__).parent / "sample.config.toml"

        # Default newline translation gives Windows editors CRLF.
        with path.open("w", encoding="utf-8") as file:
            file.write(sample.read_text(encoding="utf-8"))

    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")

    if editor:
        logger.debug("Opening configuration file with EDITOR: %s", editor)
        # Blocking, so terminal editors get the console to themselves.
        subprocess.run([editor, str(path)], check=False)
        return

    logger.debug("Opening configuration file: %s", path)
    if sys.platform == "win32":
        # No fallback on purpose: with no .toml association Windows shows its
        # own "How do you want to open this file?" picker, which lets the user
        # choose an editor and remember it.
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=False)
    else:
        subprocess.run(["xdg-open", str(path)], check=False)