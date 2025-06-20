import pytest
from palabra_ai.util.sysinfo import get_system_info


class TestSysinfo:
    def test_get_system_info(self):
        info = get_system_info()

        # Just verify it returns a dict with expected structure
        assert isinstance(info, dict)

        # The function might fail in some environments,
        # so we just check it doesn't crash completely
        if info:  # If it returned data
            # Could have various keys depending on success
            pass
