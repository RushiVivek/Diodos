import json
import logging
import os
import socket
import tempfile
from urllib.parse import urlsplit

import requests
from filelock import FileLock, Timeout
from requests.adapters import HTTPAdapter
from urllib3.connection import HTTPConnection

from . import android
from .config import get_config_path

logger = logging.getLogger(__name__)

CONFIG_PATH = get_config_path().parent
COOKIE_FILE = CONFIG_PATH / "cookies.json"
LOCK_FILE = CONFIG_PATH / "cookies.lock"


def _load_cookies(session: requests.Session) -> None:
    logger.debug("Loading cookies from %s.", COOKIE_FILE)

    if not COOKIE_FILE.exists():
        logger.debug("Cookie file does not exist at %s. No cookies to load.", COOKIE_FILE)
        return

    try:
        with FileLock(LOCK_FILE, timeout=5):
            with COOKIE_FILE.open("r", encoding="utf-8") as f:
                cookies = json.load(f)
    except Timeout:
        logger.error("Timeout occurred while trying to acquire lock for loading cookies.")
        return
    except (json.JSONDecodeError, OSError) as e:
        logger.error(
            "Error occurred while loading cookies from %s: %s",
            COOKIE_FILE,
            e,
        )
        return

    # Remove cookies that may have been deleted/changed on disk.
    session.cookies.clear()

    for cookie in cookies:
        try:
            session.cookies.set(
                cookie["name"],
                cookie["value"],
                domain=cookie.get("domain"),
                path=cookie.get("path", "/"),
            )
        except (KeyError, TypeError) as e:
            logger.warning("Invalid cookie: %s", e)


def _save_cookies(session: requests.Session) -> None:
    cookies = [
        {
            "name": c.name,
            "value": c.value,
            "domain": c.domain,
            "path": c.path,
        }
        for c in session.cookies
    ]

    logger.debug("Saving cookies to %s.", COOKIE_FILE)

    CONFIG_PATH.mkdir(parents=True, exist_ok=True)

    try:
        with FileLock(LOCK_FILE, timeout=5):
            fd, temp_path = tempfile.mkstemp(
                dir=COOKIE_FILE.parent,
                prefix=".cookies.",
                suffix=".tmp",
            )

            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(cookies, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())

                os.replace(temp_path, COOKIE_FILE)

            finally:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
    except Timeout:
        logger.error("Timeout occurred while trying to acquire lock for saving cookies.")

class _InterfaceAdapter(HTTPAdapter):
    """Sends every connection out through one network interface."""

    def __init__(self, interface: str):
        self._interface = interface
        super().__init__()

    def init_poolmanager(self, *args, **kwargs):
        kwargs["socket_options"] = [
            *HTTPConnection.default_socket_options,
            (socket.SOL_SOCKET, android.SO_BINDTODEVICE, self._interface.encode()),
        ]
        super().init_poolmanager(*args, **kwargs)


def _new_session() -> requests.Session:
    session = requests.Session()

    # Looked up per session: Wi-Fi comes and goes while the daemon runs. With
    # Wi-Fi disconnected nothing is pinned, and the check then finds the
    # internet over mobile data, so diodos correctly has nothing to do.
    interface = android.wifi_interface() if android.IS_ANDROID else None
    if interface:
        logger.debug("Sending requests through %s.", interface)
        adapter = _InterfaceAdapter(interface)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

    return session


def probe(url: str, **kwargs) -> requests.Response:
    """A GET for the connectivity check, kept out of the portal cookie jar."""
    with _new_session() as session:
        return session.get(url, **kwargs)


def _request(method: str, url: str, **kwargs) -> requests.Response:
    """
    A request to the portal. The cookie jar on disk is reloaded before and
    saved after every request, so `diodos login`, `diodos logout` and the
    daemon all share the same portal session.
    """
    if android.IS_ANDROID:
        android.track_portal_host(urlsplit(url).hostname)

    with _new_session() as session:
        _load_cookies(session)
        try:
            return session.request(method, url, **kwargs)
        finally:
            _save_cookies(session)


def get(url: str, **kwargs) -> requests.Response:
    return _request("GET", url, **kwargs)


def post(url: str, **kwargs) -> requests.Response:
    return _request("POST", url, **kwargs)
