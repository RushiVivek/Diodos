"""
Reaching the captive portal on Android while mobile data is on.

Android sends traffic over mobile data while the Wi-Fi network sits behind a
captive portal nobody has logged in to yet. The connectivity check would then
succeed over mobile data, and the login would never reach the portal. So on
Android diodos pins its own connections to the Wi-Fi interface with
SO_BINDTODEVICE, which unprivileged processes may use since Linux 5.7.

DNS lookups cannot be pinned the same way: they go through Android's resolver
on the default network. A portal hostname that only the campus DNS knows then
fails to resolve over mobile data. So the addresses of portal hosts are
remembered whenever they do resolve (mobile data off, or already logged in),
and used when they do not. Only the address is substituted: HTTPS still
checks the certificate against the hostname.
"""

import ipaddress
import json
import logging
import socket
import struct
import sys

from .config import get_config_path

logger = logging.getLogger(__name__)

IS_ANDROID = sys.platform == "android" or hasattr(sys, "getandroidapilevel")

SO_BINDTODEVICE = getattr(socket, "SO_BINDTODEVICE", 25)
SIOCGIFADDR = 0x8915

HOSTS_FILE = get_config_path().parent / "portal-hosts.json"

_portal_hosts: set[str] = set()
_system_getaddrinfo = socket.getaddrinfo


def _has_ipv4_address(interface: str) -> bool:
    import fcntl  # POSIX only, and this module only runs on Android.

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        try:
            fcntl.ioctl(sock.fileno(), SIOCGIFADDR, struct.pack("256s", interface.encode()[:15]))
        except OSError:
            return False
    return True


def wifi_interface() -> str | None:
    """The Wi-Fi interface, if it is connected (has an IPv4 address)."""
    try:
        names = [name for _, name in socket.if_nameindex() if name.startswith("wlan")]
    except OSError:
        names = []

    for name in names or ["wlan0"]:
        if _has_ipv4_address(name):
            return name

    return None


def _load_hosts() -> dict:
    try:
        return json.loads(HOSTS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _remember(host: str, result: list) -> None:
    addresses = sorted({entry[4][0] for entry in result})
    hosts = _load_hosts()

    if hosts.get(host) == addresses:
        return

    hosts[host] = addresses
    try:
        HOSTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        HOSTS_FILE.write_text(json.dumps(hosts, indent=2), encoding="utf-8")
        logger.debug("Remembered %s as %s.", host, addresses)
    except OSError as e:
        logger.warning("Could not save %s: %s", HOSTS_FILE, e)


def _getaddrinfo(host, port, *args, **kwargs):
    if host not in _portal_hosts:
        return _system_getaddrinfo(host, port, *args, **kwargs)

    try:
        result = _system_getaddrinfo(host, port, *args, **kwargs)
    except socket.gaierror:
        addresses = _load_hosts().get(host)
        if not addresses:
            logger.warning(
                "%s does not resolve, probably because DNS goes over mobile "
                "data. Log in once with mobile data off so diodos can remember "
                "its address.",
                host,
            )
            raise
        logger.info("%s does not resolve. Using its remembered address %s.", host, addresses)
        return [
            entry
            for address in addresses
            for entry in _system_getaddrinfo(address, port, *args, **kwargs)
        ]

    _remember(host, result)
    return result


def track_portal_host(host: str | None) -> None:
    """Remember this host's address from now on, and fall back to it."""
    if not host:
        return
    try:
        ipaddress.ip_address(host)
        return  # Already an address.
    except ValueError:
        pass

    _portal_hosts.add(host)
    # urllib3 resolves through socket.getaddrinfo. Only hosts tracked here
    # take the remembering path; every other lookup is passed straight on.
    socket.getaddrinfo = _getaddrinfo
