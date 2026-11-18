import os
import shlex
import sys
import subprocess
from pathlib import Path
import logging

from tomlkit import loads
from tomlkit.exceptions import TOMLKitError

logger = logging.getLogger(__name__)

DEFAULT_CHECK_URL = "http://connectivitycheck.gstatic.com/generate_204"
DEFAULT_INTERVAL = 60


class ConfigError(Exception):
    """The config file exists but cannot be used as written."""


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
        # Linux, and Android under Termux.
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))

    return base / "diodos" / "config.toml"


def load_config(
    path: str | Path | None = None,
    create_if_missing: bool = True,
) -> dict:
    """
    Load and validate the diodos configuration.

    Returns a normalised dict: {"interval", "check": {"url", "expect"},
    "networks": [{"name", "ssids", "login": {"url", "form"},
    "logout": {"url", "form"} | None}]}.

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
    try:
        raw = loads(config_path.read_text(encoding="utf-8-sig")).unwrap()
    except TOMLKitError as e:
        raise ConfigError(f"{config_path} is not valid TOML: {e}") from e

    return _normalise(_upgrade_legacy(raw))


def _upgrade_legacy(raw: dict) -> dict:
    """
    Translate the pre-0.5 single-network layout ([network], [network_check],
    [login], [login.credentials], [logout]) into the [[networks]] layout, so
    existing config files keep working unchanged.
    """
    if "networks" in raw or "login" not in raw:
        return raw

    logger.debug("Upgrading legacy single-network config in memory.")
    old_check = raw.get("network_check", {})
    ssid = raw.get("network", {}).get("SSID")
    login = raw.get("login", {})

    check = {}
    if old_check.get("url"):
        check = {"url": old_check["url"], "expect": old_check.get("msg", "Success")}

    upgraded = {
        "check": check,
        "networks": [{
            "name": ssid or "default",
            "ssids": [ssid] if ssid else [],
            "login": {"url": login.get("url"), "form": login.get("credentials", {})},
        }],
    }

    if "interval" in old_check:
        upgraded["interval"] = old_check["interval"]
    if raw.get("logout", {}).get("url"):
        upgraded["networks"][0]["logout"] = raw["logout"]

    return upgraded


def _normalise(raw: dict) -> dict:
    """Validate the [[networks]] layout and fill in defaults."""
    interval = raw.get("interval", DEFAULT_INTERVAL)
    if isinstance(interval, bool) or not isinstance(interval, (int, float)) or interval <= 0:
        raise ConfigError(f"`interval` must be a positive number of seconds, got {interval!r}.")

    check = raw.get("check", {})
    if not isinstance(check, dict):
        raise ConfigError("[check] must be a table.")

    networks = raw.get("networks")
    if not isinstance(networks, list) or not networks:
        raise ConfigError("Add at least one [[networks]] block. See the comments in the sample config.")

    normalised = []
    for index, network in enumerate(networks, start=1):
        if not isinstance(network, dict):
            raise ConfigError(f"[[networks]] entry {index} must be a table.")

        name = str(network.get("name") or f"network {index}")

        ssids = network.get("ssids", [])
        if isinstance(ssids, str):
            ssids = [ssids]
        if not isinstance(ssids, list) or not all(isinstance(s, str) for s in ssids):
            raise ConfigError(f"{name}: `ssids` must be a list of Wi-Fi names.")

        login = _endpoint(network.get("login"), f"{name}: [networks.login]")
        if login is None:
            raise ConfigError(f"{name}: [networks.login] needs a `url`.")

        normalised.append({
            "name": name,
            "ssids": ssids,
            "login": login,
            "logout": _endpoint(network.get("logout"), f"{name}: [networks.logout]"),
        })

    return {
        "interval": interval,
        "check": {
            "url": check.get("url") or DEFAULT_CHECK_URL,
            "expect": check.get("expect") or None,
        },
        "networks": normalised,
    }


def _endpoint(section, label: str) -> dict | None:
    """A {url, form} request description, or None when no url is set."""
    if section is None:
        return None
    if not isinstance(section, dict):
        raise ConfigError(f"{label} must be a table.")
    if not section.get("url"):
        return None

    form = section.get("form", {})
    if not isinstance(form, dict):
        raise ConfigError(f"{label}: `form` must be a table of field = value pairs.")

    return {"url": str(section["url"]), "form": {k: str(v) for k, v in form.items()}}


def open_config_file(path: str | Path) -> None:
    path = Path(path)

    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)

        logger.debug("Creating default config file at: %s", path)

        sample = Path(__file__).parent / "sample.config.toml"

        # Default newline translation gives Windows editors CRLF.
        with path.open("w", encoding="utf-8") as file:
            file.write(sample.read_text(encoding="utf-8"))

        # The file holds portal passwords. A no-op on Windows, where the
        # per-user APPDATA directory is already private.
        path.chmod(0o600)

    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")

    if editor:
        logger.debug("Opening configuration file with EDITOR: %s", editor)
        # POSIX editors are often set with arguments, such as "code -w". On
        # Windows the value is usually a bare path that shlex would mangle.
        command = [editor] if sys.platform == "win32" else shlex.split(editor)
        # Blocking, so terminal editors get the console to themselves.
        subprocess.run([*command, str(path)], check=False)
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
        # Termux ships xdg-open as an alias for termux-open.
        subprocess.run(["xdg-open", str(path)], check=False)
