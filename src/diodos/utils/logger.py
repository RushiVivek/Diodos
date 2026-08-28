import logging
from logging.handlers import RotatingFileHandler

from .config import get_config_path


def setup_logging():
    log_dir = get_config_path().parent
    log_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("diodos")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    if logger.handlers:
        return logger

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")

    info_handler = RotatingFileHandler(log_dir / "info.log", maxBytes=10*1024*1024, backupCount=5, encoding="utf-8")
    info_handler.setLevel(logging.INFO)
    info_handler.setFormatter(formatter)

    debug_handler = RotatingFileHandler(log_dir / "debug.log", maxBytes=10*1024*1024, backupCount=5, encoding="utf-8")
    debug_handler.setLevel(logging.DEBUG)
    debug_handler.setFormatter(formatter)

    logger.addHandler(info_handler)
    logger.addHandler(debug_handler)

    return logger
