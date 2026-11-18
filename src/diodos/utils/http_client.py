import json
import logging
import os
import tempfile

import requests
from filelock import FileLock, Timeout

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

# One session per process. The cookie jar on disk is reloaded before and saved
# after every request, so `diodos login`, `diodos logout` and the daemon all
# see the same portal session.
session = requests.Session()


def _request(method: str, *args, **kwargs) -> requests.Response:
    _load_cookies(session)
    try:
        return session.request(method, *args, **kwargs)
    finally:
        _save_cookies(session)


def get(*args, **kwargs) -> requests.Response:
    return _request("GET", *args, **kwargs)


def post(*args, **kwargs) -> requests.Response:
    return _request("POST", *args, **kwargs)
