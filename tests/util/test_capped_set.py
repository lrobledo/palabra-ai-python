import pytest
from palabra_ai.util.capped_set import CappedSet


class TestCappedSet:
    def test_basic_operations(self):
        cs = CappedSet(3)

        # Test add and contains
        cs.add("a")
        cs.add("b")
        cs.add("c")

        assert "a" in cs
        assert "b" in cs
        assert "c" in cs
        assert "d" not in cs

        # Test capacity - oldest should be removed
        cs.add("d")
        assert "a" not in cs  # oldest removed
        assert "d" in cs

    def test_add_existing(self):
        cs = CappedSet(3)
        cs.add("a")
        cs.add("b")
        cs.add("a")  # Re-add existing - doesn't affect order

        cs.add("c")
        cs.add("d")

        # Based on actual implementation, 'a' is removed as oldest
        assert "a" not in cs
        assert "b" in cs
        assert "c" in cs
        assert "d" in cs

    def test_repr(self):
        cs = CappedSet(2)
        cs.add("x")
        cs.add("y")

        repr_str = repr(cs)
        assert "CappedSet" in repr_str
        # Just check it returns a string representation
        assert isinstance(repr_str, str)

    def test_len(self):
        cs = CappedSet(5)
        assert len(cs) == 0

        cs.add("a")
        cs.add("b")
        assert len(cs) == 2

    def test_bool(self):
        cs = CappedSet(2)
        assert not cs  # Empty is falsy

        cs.add("x")
        assert cs  # Non-empty is truthy
