import os
import subprocess
import sys
import psutil
import logging

logger = logging.getLogger(__name__)


def launch_daemon() -> None:
    """
    Launches the diodos daemon in the background.
    """
    logger.debug("Launching diodos daemon in the background.")
    kwargs = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "close_fds": True,
    }

    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    else:
        kwargs["start_new_session"] = True

    logger.info("Starting diodos daemon for platform: %s", sys.platform)
    subprocess.Popen(["diodos", "daemon"], **kwargs)


def stop_daemon() -> bool:
    """
    Stops the diodos daemon if it is running.
    """
    logger.debug("Attempting to stop diodos daemon if it is running.")
    daemon_stopped = False
    for proc in psutil.process_iter(["cmdline"]):
        try:
            cmdline = proc.info["cmdline"] or []
            cmd = " ".join(cmdline)
            if "diodos" in cmd and "daemon" in cmd:
                logger.debug("Found diodos daemon process: %s with command line: %s", proc.pid, cmd)
                children = proc.children(recursive=True)

                proc.terminate()

                for child in children:
                    child.terminate()
                logger.info("Diodos daemon stopped.")
                daemon_stopped = True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            logger.error("Failed to stop diodos daemon.")
            pass
    return daemon_stopped
