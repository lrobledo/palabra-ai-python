import json
import pytest
from palabra_ai.util.orjson import to_json


class TestOrjson:
    def test_basic_types(self):
        data = {"key": "value", "number": 123, "list": [1, 2, 3]}

        json_bytes = to_json(data)
        assert isinstance(json_bytes, bytes)

        # Test that it's valid JSON
        result = json.loads(json_bytes)
        assert result == data

    def test_special_types(self):
        # Test that functions handle special types gracefully
        from pathlib import Path
        data = {"path": Path("/tmp/test")}

        # Should convert Path to string
        json_bytes = to_json(data)
        result = json.loads(json_bytes)
        assert result["path"] == "/tmp/test"
