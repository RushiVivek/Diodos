import os
import subprocess
import sys
import psutil


def launch_daemon() -> None:
    """
    Launches the diodos daemon in the background.
    """

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

    subprocess.Popen(["diodos", "daemon"], **kwargs)


def stop_daemon() -> bool:
    """
    Stops the diodos daemon if it is running.
    """
    daemon_stopped = False
    for proc in psutil.process_iter(["cmdline"]):
        try:
            cmdline = proc.info["cmdline"] or []
            cmd = " ".join(cmdline)
            if "diodos" in cmd and "daemon" in cmd:
                children = proc.children(recursive=True)

                proc.terminate()

                for child in children:
                    child.terminate()
                daemon_stopped = True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return daemon_stopped
