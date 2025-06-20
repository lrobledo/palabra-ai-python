import pytest
from palabra_ai.util.logger import set_logging, debug, info, warning, error, exception, logger


class TestLogger:
    def test_set_logging_silent(self, capfd):
        set_logging(silent=True, debug=False, log_file=None)
        info("test message")
        captured = capfd.readouterr()
        assert "test message" not in captured.out

    def test_set_logging_debug(self, capfd):
        set_logging(silent=False, debug=True, log_file=None)
        debug("debug message")
        info("info message")
        warning("warning message")
        error("error message")

        # Just verify functions work without errors
        try:
            raise ValueError("test")
        except ValueError:
            exception("exception message")

        assert logger is not None

    def test_set_logging_with_file(self, tmp_path):
        log_file = tmp_path / "test.log"
        set_logging(silent=False, debug=True, log_file=log_file)
        info("test file logging")
        # Just verify it doesn't crash with file logging
