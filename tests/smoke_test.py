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

# Fixtures for the local stand-in portal defined below. Not real credentials:
# nothing outside this file, and no remote host, ever sees them.
USERNAME = "test-user"
PASSWORD = "not-a-real-password"  # pragma: allowlist secret

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
            # What the real probe does: an empty 204 when online, and the
            # portal intercepting it when not.
            if state["logged_in"]:
                self.send_response(204)
                self.end_headers()
            else:
                self._send(200, "<html>Sign in to continue</html>")
        elif self.path.startswith("/status"):
            # For the legacy `msg` style check.
            self._send(200, "Success" if state["logged_in"] else "<html>Sign in</html>")
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
            # Like many real portals: a 200 page that says no.
            self._send(200, "bad credentials")


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


def write_config(path, port, bom=False, ssids=(), password=PASSWORD):
    ssid_list = ", ".join(f'"{ssid}"' for ssid in ssids)
    body = f"""interval = 2

[check]
url = "http://127.0.0.1:{port}/generate_204"

[[networks]]
name = "Elsewhere"
ssids = ["diodos-some-other-network"]

[networks.login]
url = "http://127.0.0.1:1/never-used"

[[networks]]
name = "Test portal"
ssids = [{ssid_list}]

[networks.login]
url = "http://127.0.0.1:{port}/login"

[networks.login.form]
username = "{USERNAME}"
password = "{password}"

[networks.logout]
url = "http://127.0.0.1:{port}/logout"
"""
    # Windows editors and PowerShell readily save TOML with a BOM.
    path.write_bytes((b"\xef\xbb\xbf" if bom else b"") + body.encode("utf-8"))


def write_legacy_config(path, port):
    """The pre-0.5 single-network layout, which must keep working."""
    path.write_text(f"""[network_check]
url = "http://127.0.0.1:{port}/status"
msg = "Success"
interval = 2

[login]
url = "http://127.0.0.1:{port}/login"

[login.credentials]
username = "{USERNAME}"
password = "{PASSWORD}"

[logout]
url = "http://127.0.0.1:{port}/logout"
""", encoding="utf-8")


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


def stop_any_daemon():
    """
    Best effort teardown, so a failed check never leaves a detached daemon
    running after this process exits.
    """
    try:
        from diodos.utils import background

        if background.stop_daemon():
            print("    (cleanup: stopped leftover daemon)")
    except Exception as exc:  # noqa: BLE001 - teardown must not raise
        print(f"    (cleanup: daemon teardown failed: {exc})")


def windows_image_name(pid):
    """Executable name of a Windows process, without needing psutil."""
    out = subprocess.run(
        ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
        capture_output=True,
        text=True,
    ).stdout
    return out.split(",")[0].strip().strip('"')


def run_checks(tmp, port):
    """Every assertion. Raises SystemExit(1) on the first failure."""
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
    check("default config parses", len(config_module.load_config()["networks"]) == 2)
    check("default config is private", sys.platform == "win32" or config_path.stat().st_mode & 0o077 == 0)

    # Real config, deliberately written with a BOM.
    write_config(config_path, port, bom=True)
    check("BOM-prefixed config parses", len(config_module.load_config()["networks"]) == 2)

    config_path.write_text("interval = 0\n[[networks]]\nname = 'x'\n", encoding="utf-8")
    try:
        config_module.load_config()
        check("invalid config rejected", False)
    except config_module.ConfigError as exc:
        check(f"invalid config rejected ({exc})", "interval" in str(exc))

    # Network selection by SSID. Done in-process with explicit SSIDs, since
    # CI machines have no Wi-Fi to read.
    from diodos.utils.network import select_network

    write_config(config_path, port, ssids=["Hostel", "Library"])
    networks = config_module.load_config()["networks"]
    pick = lambda ssid: (select_network(networks, ssid) or {}).get("name")
    check("first SSID of a network selects it", pick("Hostel") == "Test portal")
    check("second SSID of a network selects it", pick("Library") == "Test portal")
    check("other network's SSID selects that one", pick("diodos-some-other-network") == "Elsewhere")
    check("unknown SSID selects nothing", pick("Cafe") is None)
    check("unreadable SSID with several networks selects nothing", pick(None) is None)
    check("unreadable SSID never uses an SSID-restricted network", select_network(networks[1:], None) is None)
    wildcard = [networks[0], {**networks[1], "ssids": []}]
    check("network without ssids matches any SSID", select_network(wildcard, "Cafe") is wildcard[1])
    check("network without ssids used when SSID is unreadable", select_network(wildcard, None) is wildcard[1])

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

    # Android: requests pinned to the Wi-Fi interface, and a portal hostname
    # that does not resolve (DNS over mobile data) reached through its
    # remembered address. Simulated on Linux with the loopback interface.
    import socket

    from diodos.utils import android, network

    if sys.platform.startswith("linux"):
        pinned = http_client._InterfaceAdapter("lo")
        with requests.Session() as s:
            s.mount("http://", pinned)
            check("request pinned to an interface goes through", s.get(f"http://127.0.0.1:{port}/status", timeout=5).ok)
        with requests.Session() as s:
            s.mount("http://", http_client._InterfaceAdapter("diodos-none0"))
            try:
                s.get(f"http://127.0.0.1:{port}/status", timeout=5)
                check("request pinned to a missing interface fails", False)
            except requests.ConnectionError:
                check("request pinned to a missing interface fails", True)

    host = "portal.diodos.invalid"
    android.HOSTS_FILE.write_text(json.dumps({host: ["127.0.0.1"]}), encoding="utf-8")
    saved = (android.IS_ANDROID, android.wifi_interface)
    android.IS_ANDROID = True
    android.wifi_interface = (lambda: "lo") if sys.platform.startswith("linux") else (lambda: None)
    try:
        state["logged_in"] = False
        portal_config = {
            "check": {"url": f"http://127.0.0.1:{port}/generate_204", "expect": None},
            "networks": [{
                "name": "Remembered",
                "ssids": [],
                "login": {"url": f"http://{host}:{port}/login",
                          "form": {"username": USERNAME, "password": PASSWORD}},
                "logout": None,
            }],
        }
        result, _, _ = network.ensure_logged_in(portal_config)
        check(f"login through a remembered portal address ({result.name})", result is network.LoginResult.LOGGED_IN)

        http_client.get(f"http://localhost:{port}/status", timeout=5)
        remembered = json.loads(android.HOSTS_FILE.read_text(encoding="utf-8"))
        check("resolvable portal host is remembered", "localhost" in remembered)
    finally:
        android.IS_ANDROID, android.wifi_interface = saved
        socket.getaddrinfo = android._system_getaddrinfo
        # Leave the portal as the CLI checks below expect to find it.
        state.update(logged_in=False, logins=0, logouts=0)

    # A portal that answers 200 to a wrong password must not count as a login.
    write_config(config_path, port, password="wrong")
    result = run_cli("login")
    check("rejected login reported as failure", "failed" in result.stdout and result.returncode == 1)
    check("portal saw no successful login", state["logins"] == 0)

    # One-shot login and logout against the portal. The test network has no
    # SSIDs, so it is used whatever Wi-Fi this machine is on.
    write_config(config_path, port, bom=True)
    check("login reports success", "Login successful" in run_cli("login").stdout)
    check("portal saw the login", state["logins"] == 1)
    check("second login is a no-op", "No captive portal" in run_cli("login").stdout)
    check("logout reports success", "Logout successful" in run_cli("logout").stdout)
    check("portal saw the logout", state["logouts"] == 1)

    write_legacy_config(config_path, port)
    check("legacy config logs in", "Login successful" in run_cli("login").stdout)
    check("legacy config logs out", "Logout successful" in run_cli("logout").stdout)
    check("portal saw both", state["logins"] == 2 and state["logouts"] == 2)
    write_config(config_path, port)

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
    check("pid file written", background.read_daemon_pid() is not None)
    check("daemon holds its lock", background.is_daemon_running())

    if sys.platform == "win32" and Path(background._daemon_interpreter()).name == "pythonw.exe":
        # Console-subsystem python.exe would be handed a fresh console
        # window, which a venv's launcher stub re-triggers for its child.
        image = windows_image_name(background.read_daemon_pid())
        check(f"daemon runs windowless under pythonw.exe (got {image})", image.lower() == "pythonw.exe")
    check("duplicate start refused", "already running" in run_cli("start").stdout)
    check("duplicate daemon refused", run_cli("daemon").returncode == 1)

    # The logout above left the portal signed out.
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline and state["logins"] < 3:
        time.sleep(0.5)
    check("daemon logged in on its own", state["logins"] >= 3)

    check("stop reports success", "Daemon stopped" in run_cli("stop").stdout)
    check("daemon is gone", not background.is_daemon_running())
    check("pid file cleaned up", not background.PID_FILE.exists())
    check("stop on an idle machine is graceful", "No running" in run_cli("stop").stdout)


def main():
    server = ThreadingHTTPServer(("127.0.0.1", 0), PortalHandler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()

    try:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            try:
                run_checks(tmp, port)
            finally:
                # Runs even when a check fails, so the detached daemon cannot
                # outlive this process. Must happen before the temporary
                # directory holding its config and PID file disappears.
                stop_any_daemon()
    finally:
        server.shutdown()
        server.server_close()

    print("\nAll smoke checks passed.")


if __name__ == "__main__":
    main()
