import logging
import os
import subprocess
import sys
from pathlib import Path

import psutil

from .config import get_config_path

logger = logging.getLogger(__name__)

PID_FILE = get_config_path().parent / "diodos.pid"


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


def _is_daemon_cmdline(cmdline: list[str] | None) -> bool:
    """Return True if a process command line looks like `diodos daemon`."""
    if not cmdline:
        return False

    tokens = [token.lower() for token in cmdline]

    return "daemon" in tokens and any("diodos" in token for token in tokens)


def _daemon_processes() -> list[psutil.Process]:
    """Find running diodos daemons, preferring the recorded PID."""
    own_pids = {os.getpid()}

    try:
        pid = int(PID_FILE.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        pid = None

    if pid is not None and pid not in own_pids:
        try:
            proc = psutil.Process(pid)
            if _is_daemon_cmdline(proc.cmdline()):
                logger.debug("Found diodos daemon %s from %s.", pid, PID_FILE)
                return [proc]
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    # Stale or missing PID file: fall back to scanning.
    logger.debug("No usable PID file, scanning processes for a diodos daemon.")
    found = []
    for proc in psutil.process_iter(["cmdline"]):
        if proc.pid in own_pids:
            continue
        try:
            if _is_daemon_cmdline(proc.info["cmdline"]):
                logger.debug(
                    "Found diodos daemon process: %s with command line: %s",
                    proc.pid,
                    " ".join(proc.info["cmdline"]),
                )
                found.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    return found


def _matching_ancestors(proc: psutil.Process) -> list[psutil.Process]:
    """
    Walk up through parents that are also `diodos daemon` processes.

    On Windows a venv's Scripts/python.exe is a launcher stub that runs the
    real interpreter as a child, so the daemon shows up as two processes with
    identical command lines.
    """
    ancestors = []
    own_pid = os.getpid()

    try:
        parent = proc.parent()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return ancestors

    while parent is not None and parent.pid != own_pid:
        try:
            if not _is_daemon_cmdline(parent.cmdline()):
                break
            ancestors.append(parent)
            parent = parent.parent()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            break

    return ancestors


def record_daemon_pid(pid: int) -> None:
    try:
        PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        PID_FILE.write_text(str(pid), encoding="utf-8")
    except OSError as e:
        logger.warning("Could not write PID file %s: %s", PID_FILE, e)


def clear_daemon_pid() -> None:
    try:
        PID_FILE.unlink(missing_ok=True)
    except OSError as e:
        logger.warning("Could not remove PID file %s: %s", PID_FILE, e)


def launch_daemon() -> bool:
    """
    Launch the diodos daemon in the background.

    Returns False if a daemon is already running.
    """
    logger.debug("Launching diodos daemon in the background.")

    if _daemon_processes():
        logger.info("A diodos daemon is already running.")
        return False

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
    record_daemon_pid(proc.pid)

    return True


def stop_daemon() -> bool:
    """
    Stop the diodos daemon if it is running.
    """
    logger.debug("Attempting to stop diodos daemon if it is running.")

    processes = _daemon_processes()

    if not processes:
        logger.info("No running diodos daemon found.")
        clear_daemon_pid()
        return False

    targets = []
    for proc in processes:
        try:
            targets.extend(proc.children(recursive=True))
            targets.append(proc)
            targets.extend(_matching_ancestors(proc))
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            logger.warning("Could not inspect process %s: %s", proc.pid, e)

    # De-duplicate while keeping children ahead of their parents.
    seen = set()
    targets = [p for p in targets if not (p.pid in seen or seen.add(p.pid))]

    for proc in targets:
        try:
            proc.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    _, alive = psutil.wait_procs(targets, timeout=5)

    # Windows terminate() is already a hard kill, but a POSIX daemon may ignore
    # SIGTERM while it is inside a request.
    for proc in alive:
        try:
            proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            logger.error("Failed to stop diodos daemon process %s: %s", proc.pid, e)

    clear_daemon_pid()
    logger.info("Diodos daemon stopped.")

    return True
