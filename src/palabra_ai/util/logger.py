import sys
from logging import DEBUG, INFO
from pathlib import Path
from typing import Any

from loguru import logger


def set_logging(debug: bool, log_file: Path):
    logger.remove()
    logger.add(
        sys.stderr,
        level=DEBUG if debug else INFO,
        colorize=True,  # Keep default colors
    )
    if log_file:
        logger.add(
            str((log_file.with_suffix(".log")).absolute()),
            level=DEBUG,
            enqueue=True,
            buffering=1,  # Line buffering for immediate write
            # Additional options for reliability:
            catch=True,  # Catch errors in logging itself
            backtrace=True,  # Full traceback on errors
            diagnose=True,  # Extra diagnostic info
        )


debug = logger.debug
info = logger.info
warning = logger.warning
error = logger.error
critical = logger.critical
exception = logger.exception
log = logger.log
trace = logger.trace

ALL_LOGS = []


def catcher(message: Any) -> None:
    ALL_LOGS.append(message)


logger.add(catcher)


__all__ = [
    "debug",
    "info",
    "warning",
    "error",
    "critical",
    "exception",
    "log",
    "trace",
]
