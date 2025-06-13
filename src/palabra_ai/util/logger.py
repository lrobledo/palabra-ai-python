from typing import Any

from loguru import logger

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
