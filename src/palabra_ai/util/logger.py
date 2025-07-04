import sys
from dataclasses import dataclass, field
from logging import DEBUG, INFO, WARNING
from pathlib import Path

from loguru import logger


@dataclass
class Library:
    name: str = "palabra_ai"
    level: int = field(default=INFO)
    handlers: list = field(default_factory=list)

    def __call__(self, level: int):
        self.level = level

    def set_level(self, silent: bool, debug: bool):
        """Set logging level based on flags."""
        if debug:
            self(DEBUG)
        elif silent:
            self(WARNING)
        else:
            self(INFO)

    def should_log(self, record: dict) -> bool:
        """Check if record should be logged based on library settings."""
        if not self._is_library_record(record):
            return True
        return record["level"].no >= self.level

    def _is_library_record(self, record: dict) -> bool:
        """Check if record belongs to this library."""
        return record.get("name", "").startswith(self.name)

    def create_console_filter(self, original_filter):
        """Create a filter that combines library filtering with original."""

        def combined_filter(record):
            if not self.should_log(record):
                return False
            return original_filter(record) if original_filter else True

        return combined_filter

    def create_file_filter(self):
        """Create a filter for file handler (library messages only)."""
        return lambda record: self._is_library_record(record)

    def cleanup_handlers(self):
        """Remove all registered handlers."""
        for h_id in self.handlers:
            try:
                logger.remove(h_id)
            except ValueError:
                pass
        self.handlers.clear()

    def setup_console_handler(self):
        """Setup console output filtering."""
        if 0 in logger._core.handlers:
            # Modify existing default handler
            handler = logger._core.handlers[0]
            original_filter = handler._filter
            handler._filter = self.create_console_filter(original_filter)
        else:
            # No default handler, create our own
            h_id = logger.add(
                sys.stderr,
                filter=self.should_log,
                colorize=True,
            )
            self.handlers.append(h_id)

    def setup_file_handler(self, log_file: Path):
        """Setup file logging handler."""
        if not log_file:
            return

        h_id = logger.add(
            str(log_file.absolute()),
            level=DEBUG,  # File gets all debug messages
            filter=self.create_file_filter(),
            enqueue=True,
            buffering=1,
            catch=True,
            backtrace=True,
            diagnose=True,
        )
        self.handlers.append(h_id)


_lib = Library()


def set_logging(silent: bool, debug: bool, log_file: Path = None):
    """Configure logging for the library."""
    _lib.set_level(silent, debug)
    _lib.cleanup_handlers()
    _lib.setup_console_handler()
    _lib.setup_file_handler(log_file)


# Direct exports from logger
debug = logger.debug
info = logger.info
warning = logger.warning
error = logger.error
critical = logger.critical
exception = logger.exception
trace = logger.trace


__all__ = [
    "debug",
    "info",
    "warning",
    "error",
    "critical",
    "exception",
    "trace",
    "set_logging",
]
