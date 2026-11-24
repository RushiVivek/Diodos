import json
import re
import shutil
import subprocess
import sys
import logging

logger = logging.getLogger(__name__)


def _console_encoding() -> str:
    """
    Encoding used by console tools whose output we capture.

    Windows console programs write their output in the OEM code page, not
    UTF-8, so decoding as UTF-8 mangles non-ASCII SSIDs.
    """
    if sys.platform != "win32":
        return "utf-8"

    try:
        import ctypes

        return f"cp{ctypes.windll.kernel32.GetOEMCP()}"
    except Exception:
        import locale

        return locale.getpreferredencoding(False)


def _run_command(command: list[str]) -> str | None:
    kwargs = {}

    if sys.platform == "win32":
        # The daemon runs detached, so without this each poll flashes a console
        # window on screen.
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding=_console_encoding(),
            errors="replace",
            timeout=5,
            check=True,
            **kwargs,
        )
        return result.stdout

    except (
        subprocess.CalledProcessError,
        FileNotFoundError,
        subprocess.TimeoutExpired,
        OSError,
    ):
        logger.error("Failed to run command: %s", ' '.join(command))
        return None


def _get_windows_ssid() -> str | None:
    output = _run_command([
        "netsh",
        "wlan",
        "show",
        "interfaces",
    ])

    if not output:
        return None

    for line in output.splitlines():
        line = line.strip()

        if not line.startswith("SSID") or line.startswith("BSSID"):
            continue

        label, separator, value = line.partition(":")

        # Only the "SSID : <name>" row, not "SSID name" or similar.
        if not separator or label.strip() != "SSID":
            continue

        value = value.strip()

        if value:
            logger.debug("Found SSID line: %s", line)
            return value

    return None


def _get_networkmanager_ssid() -> str | None:
    # --rescan no reads the cached scan instead of triggering a fresh one,
    # which can take seconds on every daemon poll.
    output = _run_command([
        "nmcli",
        "-t",
        "-f",
        "active,ssid",
        "dev",
        "wifi",
        "list",
        "--rescan",
        "no",
    ])

    if not output:
        return None

    for line in output.splitlines():
        if line.startswith("yes:"):
            logger.debug("Found active SSID line: %s", line)
            # Terse mode escapes ':' and '\\' inside values.
            return line[4:].replace("\\:", ":").replace("\\\\", "\\") or None

    return None


def _get_iwgetid_ssid() -> str | None:
    # wireless-tools, for Linux setups without NetworkManager.
    output = _run_command(["iwgetid", "-r"])

    return (output or "").strip() or None


def _get_termux_ssid() -> str | None:
    """
    Android, through the Termux:API app and the termux-api package. Android
    only reveals the SSID to apps holding the location permission, so without
    it the name reads as "<unknown ssid>".
    """
    output = _run_command(["termux-wifi-connectioninfo"])

    if not output:
        return None

    try:
        ssid = json.loads(output).get("ssid")
    except (json.JSONDecodeError, AttributeError):
        logger.warning("Unexpected termux-wifi-connectioninfo output: %s", output)
        return None

    if not ssid or ssid == "<unknown ssid>":
        logger.warning(
            "Android hid the Wi-Fi name. Give the Termux:API app location "
            "access 'Allow all the time' with 'Use precise location' on, and "
            "keep location turned on."
        )
        return None

    return ssid


# Tried in order. Only tools present on PATH are run, so a missing one never
# costs a failed process launch on each poll.
_LINUX_READERS = [
    ("nmcli", _get_networkmanager_ssid),
    ("iwgetid", _get_iwgetid_ssid),
    ("termux-wifi-connectioninfo", _get_termux_ssid),
]


def _get_linux_ssid() -> str | None:
    for tool, reader in _LINUX_READERS:
        if shutil.which(tool):
            ssid = reader()
            if ssid:
                return ssid

    return None


def _get_macos_ssid() -> str | None:
    output = _run_command([
        "networksetup",
        "-listallhardwareports",
    ])

    if not output:
        return None

    wifi_device = None
    lines = output.splitlines()

    for i, line in enumerate(lines):
        if line.strip() in ("Hardware Port: Wi-Fi", "Hardware Port: AirPort"):
            if i + 1 < len(lines):
                match = re.search(r"Device:\s*(\S+)", lines[i + 1])

                if match:
                    logger.debug("Found Wi-Fi device: %s", match.group(1))
                    wifi_device = match.group(1)

            break

    if not wifi_device:
        return None

    output = _run_command([
        "networksetup",
        "-getairportnetwork",
        wifi_device,
    ])

    if not output:
        return None

    prefix = "Current Wi-Fi Network:"

    for line in output.splitlines():
        if line.startswith(prefix):
            ssid = line[len(prefix):].strip()

            if ssid and "not associated" not in ssid.lower():
                logger.debug("Found connected SSID: %s", ssid)
                return ssid

    return None


def current_ssid() -> str | None:
    """
    The SSID of the Wi-Fi network currently joined, or None if it cannot be
    determined (not on Wi-Fi, or no supported tool on this system).
    """
    if sys.platform == "win32":
        ssid = _get_windows_ssid()
    elif sys.platform == "darwin":
        ssid = _get_macos_ssid()
    else:
        # Linux, and Android, whether Python reports it as "linux" or "android".
        ssid = _get_linux_ssid()

    logger.debug("Current SSID: %s", ssid)
    return ssid
