"""
Background daemon control.

The running daemon holds an exclusive lock on LOCK_FILE for its whole life,
and the OS drops that lock the moment the process dies, however it dies. So
"is a daemon running?" is answered by trying the lock, with no process-table
scanning, and a PID left behind by a crashed daemon can never be mistaken for
a live one. This also keeps diodos free of compiled dependencies, which is
what lets it install on Android under Termux.
"""

import contextlib
import logging
import os
import signal
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

from filelock import FileLock, Timeout

from .config import get_config_path

logger = logging.getLogger(__name__)

STATE_DIR = get_config_path().parent
PID_FILE = STATE_DIR / "diodos.pid"
LOCK_FILE = STATE_DIR / "daemon.lock"

# How long `start` waits for a freshly launched daemon to take the lock, and
# `stop` waits for one to exit.
STARTUP_TIMEOUT = 15
SHUTDOWN_TIMEOUT = 5


class DaemonError(Exception):
    """Starting or stopping the daemon did not work."""


class AlreadyRunning(DaemonError):
    pass


def _daemon_interpreter() -> str:
    """
    Interpreter to run the background daemon with.

    python.exe is a console-subsystem program, so Windows hands it a brand new
    console window when it starts without one - which is exactly what
    DETACHED_PROCESS arranges. A venv makes it worse: its python.exe is a
    launcher stub that re-spawns the real interpreter, and that child gets the
    console even if the stub avoided it. pythonw.exe is the GUI-subsystem
    build of the same interpreter, so no console is ever allocated.
    """
    if sys.platform != "win32":
        return sys.executable

    pythonw = Path(sys.executable).with_name("pythonw.exe")

    return str(pythonw) if pythonw.exists() else sys.executable


def is_daemon_running() -> bool:
    lock = FileLock(LOCK_FILE)

    try:
        lock.acquire(timeout=0)
    except Timeout:
        return True

    lock.release()
    return False


def read_daemon_pid() -> int | None:
    try:
        return int(PID_FILE.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def clear_daemon_pid() -> None:
    try:
        PID_FILE.unlink(missing_ok=True)
    except OSError as e:
        logger.warning("Could not remove PID file %s: %s", PID_FILE, e)


@contextlib.contextmanager
def daemon_lock() -> Iterator[None]:
    """
    Held by the daemon process for as long as it runs. Raises AlreadyRunning
    if another daemon holds it, so two can never run at once.
    """
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    lock = FileLock(LOCK_FILE)

    try:
        lock.acquire(timeout=0)
    except Timeout:
        raise AlreadyRunning("A diodos daemon is already running.") from None

    try:
        # Written by the daemon itself, never by the launcher: on Windows the
        # launched process can be a venv stub whose PID is not the daemon's.
        PID_FILE.write_text(str(os.getpid()), encoding="utf-8")
        yield
    finally:
        clear_daemon_pid()
        lock.release()


def launch_daemon() -> None:
    """
    Launch the diodos daemon in the background and wait until it is running.

    Raises AlreadyRunning if one is already up, or DaemonError if the new one
    exits or does not come up in time.
    """
    if is_daemon_running():
        raise AlreadyRunning("A diodos daemon is already running.")

    kwargs = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "close_fds": True,
    }

    if sys.platform == "win32":
        # DETACHED_PROCESS keeps the daemon alive after the console closes and
        # stops it from inheriting Ctrl+C sent to the launching terminal.
        kwargs["creationflags"] = (
            subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        )
    else:
        kwargs["start_new_session"] = True

    logger.info("Starting diodos daemon for platform: %s", sys.platform)

    # Invoking the interpreter directly avoids depending on the `diodos`
    # console script being on PATH, which is not guaranteed on Windows.
    proc = subprocess.Popen([_daemon_interpreter(), "-m", "diodos", "daemon"], **kwargs)

    deadline = time.monotonic() + STARTUP_TIMEOUT
    while time.monotonic() < deadline:
        if is_daemon_running() and read_daemon_pid() is not None:
            return
        if proc.poll() is not None:
            raise DaemonError(
                f"The daemon exited during startup (code {proc.returncode}). "
                f"See the logs in {STATE_DIR}."
            )
        time.sleep(0.1)

    raise DaemonError(f"The daemon did not start within {STARTUP_TIMEOUT} seconds.")


def _wait_for_exit(timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while is_daemon_running():
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.1)
    return True


def stop_daemon() -> bool:
    """
    Stop the running daemon. Returns False if none was running.
    """
    if not is_daemon_running():
        logger.info("No running diodos daemon found.")
        clear_daemon_pid()
        return False

    pid = read_daemon_pid()
    if pid is None:
        raise DaemonError(f"A daemon holds {LOCK_FILE} but {PID_FILE} is missing.")

    # SIGTERM lets a POSIX daemon clean up. On Windows os.kill with any signal
    # but the console-control ones is TerminateProcess, a hard kill; a venv
    # launcher stub waiting on the daemon then exits with it.
    logger.debug("Sending SIGTERM to daemon %s.", pid)
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    except OSError as e:
        raise DaemonError(f"Could not signal daemon {pid}: {e}") from e

    if not _wait_for_exit(SHUTDOWN_TIMEOUT) and sys.platform != "win32":
        logger.warning("Daemon %s ignored SIGTERM. Killing it.", pid)
        with contextlib.suppress(ProcessLookupError):
            os.kill(pid, signal.SIGKILL)
        _wait_for_exit(SHUTDOWN_TIMEOUT)

    if is_daemon_running():
        raise DaemonError(f"Daemon {pid} is still running.")

    clear_daemon_pid()
    logger.info("Diodos daemon stopped.")
    return True
