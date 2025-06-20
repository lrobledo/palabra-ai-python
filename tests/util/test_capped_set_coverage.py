import pytest
from palabra_ai.util.capped_set import CappedSet


class TestCappedSetCoverage:
    def test_invalid_capacity(self):
        """Test that non-positive capacity raises ValueError"""
        with pytest.raises(ValueError, match="Capacity must be positive"):
            CappedSet(0)

        with pytest.raises(ValueError):
            CappedSet(-1)

    def test_capacity_property(self):
        """Test capacity property getter"""
        cs = CappedSet(5)
        assert cs.capacity == 5
