"""
Logging configuration.
"""
import logging
import os
import sys
from pathlib import Path

_FMT = "[%(asctime)s] [%(name)s:%(lineno)d] %(levelname)s: %(message)s"


def setup_logging() -> None:
    """
    Configure root logger for the application.

    Attaches a StreamHandler (stdout) always. If the LOG_FILE_PATH
    environment variable is set, also attaches a FileHandler writing
    to that path (parent directories are created automatically).
    """
    formatter = logging.Formatter(_FMT)

    root = logging.getLogger("dreamwatcher")
    root.setLevel(logging.DEBUG)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    root.addHandler(stream_handler)

    log_file_path = os.environ.get("LOG_FILE_PATH", "").strip()
    if log_file_path:
        path = Path(log_file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
