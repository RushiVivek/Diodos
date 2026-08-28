import re
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


def _get_linux_ssid() -> str | None:
    output = _run_command([
        "nmcli",
        "-t",
        "-f",
        "active,ssid",
        "dev",
        "wifi",
    ])

    if not output:
        return None

    for line in output.splitlines():
        if line.startswith("yes:"):
            logger.debug("Found active SSID line: %s", line)
            return line[4:]

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


def is_correct_network(expected_ssid: str) -> bool:
    """
    Return True if the currently connected Wi-Fi SSID matches the expected SSID, False otherwise.
    """

    if not expected_ssid:
        logger.debug("No expected SSID provided.")
        return False

    if sys.platform == "win32":
        current_ssid = _get_windows_ssid()

    elif sys.platform == "darwin":
        current_ssid = _get_macos_ssid()

    else:
        current_ssid = _get_linux_ssid()
        
    return current_ssid == expected_ssid
