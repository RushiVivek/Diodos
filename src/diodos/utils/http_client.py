import json
import os
import tempfile
from pathlib import Path

import requests
import fcntl

from .config import get_config_path

CONFIG_PATH = get_config_path().parent
COOKIE_FILE = CONFIG_PATH / "cookies.json"
LOCK_FILE = CONFIG_PATH / "cookies.lock"


def _load_cookies(session):
    if not COOKIE_FILE.exists():
        return

    with COOKIE_FILE.open("r", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_SH)

        try:
            cookies = json.load(f)
        except (json.JSONDecodeError, OSError):
            cookies = []
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)

    for cookie in cookies:
        session.cookies.set(
            cookie["name"],
            cookie["value"],
            domain=cookie.get("domain"),
            path=cookie.get("path", "/"),
        )


def _save_cookies(session):
    cookies = [
        {
            "name": c.name,
            "value": c.value,
            "domain": c.domain,
            "path": c.path,
        }
        for c in session.cookies
    ]

    with LOCK_FILE.open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)

        # Atomic replacement
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

        fcntl.flock(lock, fcntl.LOCK_UN)


session = requests.Session()
_load_cookies(session)


def get(*args, **kwargs):
    _load_cookies(session)
    response = session.get(*args, **kwargs)
    _save_cookies(session)
    return response


def post(*args, **kwargs):
    _load_cookies(session)
    response = session.post(*args, **kwargs)
    _save_cookies(session)
    return response


def put(*args, **kwargs):
    _load_cookies(session)
    response = session.put(*args, **kwargs)
    _save_cookies(session)
    return response


def delete(*args, **kwargs):
    _load_cookies(session)
    response = session.delete(*args, **kwargs)
    _save_cookies(session)
    return response


def patch(*args, **kwargs):
    _load_cookies(session)
    response = session.patch(*args, **kwargs)
    _save_cookies(session)
    return response
