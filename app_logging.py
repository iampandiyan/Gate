import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

_DEFAULT_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(process)d:%(threadName)s | "
    "%(name)s:%(funcName)s:%(lineno)d | %(message)s"
)

# Global reference to the handler so we can add/remove it dynamically
_FILE_HANDLER = None

def setup_logging(
    log_dir: str | None = None,
    log_file_name: str = "smartgate.log",
    level: int = logging.INFO,
    also_console: bool = False,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 10,
    redirect_stdout: bool = False,
) -> None:
    """
    Configure root logging.
    """
    global _FILE_HANDLER

    if log_dir is None:
        # Use a reliable path relative to the script/executable
        base_dir = Path(getattr(sys, "_MEIPASS", Path.cwd()))
        log_dir = str(Path(base_dir) / "logs")

    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, log_file_name)

    root = logging.getLogger()
    root.setLevel(level)

    # Clean up existing handlers if called multiple times (optional safety)
    if _FILE_HANDLER and _FILE_HANDLER in root.handlers:
        root.removeHandler(_FILE_HANDLER)

    formatter = logging.Formatter(_DEFAULT_FORMAT)

    # Create the File Handler
    _FILE_HANDLER = RotatingFileHandler(
        log_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    _FILE_HANDLER.setFormatter(formatter)
    _FILE_HANDLER.setLevel(level)
    
    # Add it to root
    root.addHandler(_FILE_HANDLER)

    if also_console:
        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(formatter)
        console.setLevel(level)
        root.addHandler(console)

    if redirect_stdout:
        sys.stdout = _StreamToLogger(logging.getLogger("STDOUT"), logging.INFO)
        sys.stderr = _StreamToLogger(logging.getLogger("STDERR"), logging.ERROR)

def enable_file_logging(enabled: bool):
    """
    Dynamically add or remove the file handler to start/stop writing to disk.
    """
    global _FILE_HANDLER
    root = logging.getLogger()
    
    if _FILE_HANDLER is None:
        return # Setup hasn't been called yet

    if enabled:
        # Add if not present
        if _FILE_HANDLER not in root.handlers:
            root.addHandler(_FILE_HANDLER)
    else:
        # Remove if present
        if _FILE_HANDLER in root.handlers:
            root.removeHandler(_FILE_HANDLER)

def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)

class _StreamToLogger:
    def __init__(self, logger, level):
        self.logger = logger
        self.level = level
    def write(self, message):
        if message.rstrip(): self.logger.log(self.level, message.rstrip())
    def flush(self): pass
