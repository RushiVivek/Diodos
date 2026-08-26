import re
import subprocess
import sys


def _run_command(command: list[str]) -> str | None:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=5,
            check=True,
        )
        return result.stdout

    except (
        subprocess.CalledProcessError,
        FileNotFoundError,
        subprocess.TimeoutExpired,
    ):
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

        if line.startswith("SSID") and not line.startswith("BSSID"):
            return line.split(":", 1)[1].strip()

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
                return ssid

    return None


def is_correct_network(expected_ssid: str) -> bool:
    """
    Return True if the currently connected Wi-Fi SSID matches the expected SSID, False otherwise.
    """

    if not expected_ssid:
        return False

    if sys.platform == "win32":
        current_ssid = _get_windows_ssid()

    elif sys.platform == "darwin":
        current_ssid = _get_macos_ssid()

    else:
        current_ssid = _get_linux_ssid()
        
    return current_ssid == expected_ssid
