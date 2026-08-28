"""
Cross-platform smoke test for diodos.

Runs against a local stand-in captive portal and exercises the parts that
differ per operating system: config discovery, file locking, the cookie jar
and background daemon control. Dependency free, so `python tests/smoke_test.py`
is all it needs.
"""

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

USERNAME = "tester"
PASSWORD = "s3cret"

state = {"logged_in": False, "logins": 0, "logouts": 0}


class PortalHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code, body, cookie=None):
        raw = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path.startswith("/generate_204"):
            if state["logged_in"]:
                self._send(200, "Success")
            else:
                self._send(200, "<html>Sign in to continue</html>")
        elif self.path.startswith("/logout"):
            state["logged_in"] = False
            state["logouts"] += 1
            self._send(200, "logged out")
        else:
            self._send(404, "not found")

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        fields = parse_qs(self.rfile.read(length).decode("utf-8"))

        if fields.get("username") == [USERNAME] and fields.get("password") == [PASSWORD]:
            state["logged_in"] = True
            state["logins"] += 1
            self._send(200, "welcome", cookie="portal_session=xyz; Path=/")
        else:
            self._send(403, "bad credentials")


def check(label, condition):
    print(f"{'ok  ' if condition else 'FAIL'} {label}")
    if not condition:
        raise SystemExit(1)


def run_cli(*args):
    result = subprocess.run(
        [sys.executable, "-m", "diodos", *args],
        capture_output=True,
        text=True,
        timeout=60,
    )
    print(f"    $ diodos {' '.join(args)}\n{result.stdout.strip()}")
    return result


def write_config(path, port, bom=False, ssid=None):
    network = f'[network]\nSSID = "{ssid}"\n\n' if ssid else ""
    body = network + f"""[network_check]
url = "http://127.0.0.1:{port}/generate_204"
msg = "Success"
interval = 2

[login]
url = "http://127.0.0.1:{port}/login"

[login.credentials]
username = "{USERNAME}"
password = "{PASSWORD}"

[logout]
url = "http://127.0.0.1:{port}/logout"
"""
    # Windows editors and PowerShell readily save TOML with a BOM.
    path.write_bytes((b"\xef\xbb\xbf" if bom else b"") + body.encode("utf-8"))


def make_noop_editor(directory):
    """A do-nothing EDITOR, so no test can put a text editor on screen."""
    if sys.platform == "win32":
        editor = directory / "noop_editor.cmd"
        editor.write_text("@echo off\r\nexit /b 0\r\n", encoding="ascii")
    else:
        editor = directory / "noop_editor.sh"
        editor.write_text("#!/bin/sh\nexit 0\n", encoding="ascii")
        editor.chmod(0o755)

    return editor


def main():
    server = ThreadingHTTPServer(("127.0.0.1", 0), PortalHandler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()

    with tempfile.TemporaryDirectory() as tmp:
        config_dir = Path(tmp) / "diodos"
        config_dir.mkdir(parents=True)
        os.environ["DIODOS_CONFIG_DIR"] = str(config_dir)
        os.environ["EDITOR"] = str(make_noop_editor(Path(tmp)))
        os.environ.pop("VISUAL", None)

        from diodos.utils import background, http_client
        from diodos.utils.config import get_config_path, open_config_file

        config_path = get_config_path()
        check("config path honours DIODOS_CONFIG_DIR", config_path.parent == config_dir)

        # A default config is written and parses back.
        import diodos.utils.config as config_module

        open_config_file(config_path)
        check("default config created", config_path.exists())
        check("default config parses", "network_check" in config_module.load_config())

        # Real config, deliberately written with a BOM.
        write_config(config_path, port, bom=True)
        check("BOM-prefixed config parses", "login" in config_module.load_config())

        # Cookie jar: locking, atomic replace, no leftovers.
        import requests

        session = requests.Session()
        session.cookies.set("token", "abc", domain="127.0.0.1", path="/")
        http_client._save_cookies(session)

        reloaded = requests.Session()
        http_client._load_cookies(reloaded)
        check("cookies round-trip", reloaded.cookies.get("token") == "abc")

        errors = []

        def hammer(write):
            try:
                for _ in range(25):
                    if write:
                        http_client._save_cookies(session)
                    else:
                        http_client._load_cookies(requests.Session())
            except Exception as exc:  # noqa: BLE001 - reported, then fails the run
                errors.append(repr(exc))

        threads = [threading.Thread(target=hammer, args=(i % 2 == 0,)) for i in range(6)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        check(f"concurrent cookie access is safe {errors}", not errors)
        check("no temp files left behind", not list(config_dir.glob(".cookies.*.tmp")))

        # A configured SSID we are not joined to must suppress the login.
        write_config(config_path, port, ssid="diodos-no-such-network")
        check(
            "login skipped on the wrong network",
            "No captive portal" in run_cli("login").stdout,
        )
        check("portal saw no login attempt", state["logins"] == 0)

        # One-shot login and logout against the portal.
        write_config(config_path, port, bom=True)
        check("login reports success", "Login successful" in run_cli("login").stdout)
        check("portal saw the login", state["logins"] == 1)
        check("second login is a no-op", "No captive portal" in run_cli("login").stdout)
        check("logout reports success", "Logout successful" in run_cli("logout").stdout)
        check("portal saw the logout", state["logouts"] == 1)

        # The daemon runs detached, so it must fail on a missing config rather
        # than take the branch that creates one and opens a text editor.
        missing = Path(tmp) / "absent"
        os.environ["DIODOS_CONFIG_DIR"] = str(missing)

        result = run_cli("daemon")
        check("daemon without a config exits non-zero", result.returncode == 1)
        check("daemon says how to fix it", "Run `diodos config`" in result.stdout)
        # The directory itself is expected: setup_logging() creates it for
        # info.log and debug.log. What must not appear is a config, since
        # writing one is the step that goes on to launch an editor.
        check("daemon created no config of its own", not (missing / "config.toml").exists())

        # `start` runs in the foreground, so it may set up a first-run config,
        # but it must not report a launch it did not manage.
        result = run_cli("start")
        check("start without a config exits non-zero", result.returncode == 1)
        check("start did not claim to launch", "launched successfully" not in result.stdout)
        check("start left no daemon behind", not (missing / "diodos.pid").exists())

        os.environ["DIODOS_CONFIG_DIR"] = str(config_dir)

        # Background daemon.
        check("start reports launch", "launched successfully" in run_cli("start").stdout)
        check("pid file written", background.PID_FILE.exists())

        if sys.platform == "win32" and Path(background._daemon_interpreter()).name == "pythonw.exe":
            # Console-subsystem python.exe would be handed a fresh console
            # window, which a venv's launcher stub re-triggers for its child.
            import psutil

            daemon_exe = psutil.Process(
                int(background.PID_FILE.read_text(encoding="utf-8"))
            ).exe()
            check(
                f"daemon runs windowless under pythonw.exe (got {Path(daemon_exe).name})",
                Path(daemon_exe).name.lower() == "pythonw.exe",
            )
        check("duplicate start refused", "already running" in run_cli("start").stdout)

        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and state["logins"] < 2:
            time.sleep(0.5)
        check("daemon logged in on its own", state["logins"] >= 2)

        check("stop reports success", "Daemon stopped" in run_cli("stop").stdout)
        time.sleep(2)
        check("pid file cleaned up", not background.PID_FILE.exists())
        check("daemon is gone", not background._daemon_processes())
        check("stop on an idle machine is graceful", "No running" in run_cli("stop").stdout)

        server.shutdown()

    print("\nAll smoke checks passed.")


if __name__ == "__main__":
    main()
