import pytest
from palabra_ai.util.orjson import to_json, _default
from unittest.mock import MagicMock


class TestOrjsonCoverage:
    def test_default_with_model_dump(self):
        """Test _default with object having model_dump method"""
        obj = MagicMock()
        obj.model_dump.return_value = {"key": "value"}

        result = _default(obj)
        assert result == {"key": "value"}
        obj.model_dump.assert_called_once()

    def test_default_with_dict(self):
        """Test _default with object having dict method"""
        obj = MagicMock()
        del obj.model_dump  # Remove model_dump attribute
        obj.dict.return_value = {"key": "value"}

        result = _default(obj)
        assert result == {"key": "value"}
        obj.dict.assert_called_once()

    def test_default_fallback_to_str(self):
        """Test _default fallback to str()"""
        obj = object()  # Plain object without model_dump or dict

        result = _default(obj)
        assert isinstance(result, str)
        assert "object" in result

    def test_to_json_with_indent_and_sort(self):
        """Test to_json with different options"""
        data = {"b": 2, "a": 1}

        # Test with indent
        result = to_json(data, indent=True, sort_keys=True)
        assert isinstance(result, bytes)
        # Indented JSON should have newlines
        assert b"\n" in result

        # Test without sort_keys
        result = to_json(data, indent=False, sort_keys=False)
        assert isinstance(result, bytes)
