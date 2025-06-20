import pytest
from palabra_ai.base.message import (
    Message, KnownRaw, KnownRawType, EmptyMessage,
    QueueStatusMessage, UnknownMessage, PipelineTimingsMessage,
    TranscriptionMessage, TranscriptionSegment
)
from palabra_ai.lang import Language


class TestMessage:
    def test_detect_null(self):
        result = Message.detect(None)
        assert result.type == KnownRawType.null
        assert result.data is None

    def test_detect_json_bytes(self):
        result = Message.detect(b'{"test": true}')
        assert result.type == KnownRawType.json
        assert result.data == {"test": True}

    def test_detect_json_string(self):
        result = Message.detect('{"test": true}')
        assert result.type == KnownRawType.json
        assert result.data == {"test": True}

    def test_detect_invalid_json(self):
        result = Message.detect('invalid json')
        # Based on actual implementation, this returns unknown
        assert result.type == KnownRawType.unknown
        assert result.data == 'invalid json'

    def test_detect_binary(self):
        result = Message.detect(b'binary data')
        # Based on actual implementation, this returns unknown
        assert result.type == KnownRawType.unknown
        assert result.data == b'binary data'

    def test_decode_unknown(self):
        msg = Message.decode("not json")
        assert isinstance(msg, UnknownMessage)
        assert msg.raw_type == KnownRawType.unknown


class TestEmptyMessage:
    def test_create(self):
        known_raw = KnownRaw(KnownRawType.json, {})
        msg = EmptyMessage.create(known_raw)
        assert msg.type_ == Message.Type._EMPTY

    def test_model_dump(self):
        msg = EmptyMessage()
        assert msg.model_dump() == {}

    def test_str(self):
        msg = EmptyMessage()
        assert str(msg) == "⚪"


class TestQueueStatusMessage:
    def test_create(self):
        data = {"en": {"current_queue_level_ms": 100, "max_queue_level_ms": 500}}
        known_raw = KnownRaw(KnownRawType.json, data)
        msg = QueueStatusMessage.create(known_raw)

        assert msg.language.code == "en"
        assert msg.current_queue_level_ms == 100
        assert msg.max_queue_level_ms == 500

    def test_model_dump(self):
        msg = QueueStatusMessage(
            language=Language("es"),
            current_queue_level_ms=200,
            max_queue_level_ms=1000
        )

        dump = msg.model_dump()
        assert dump == {
            "es": {
                "current_queue_level_ms": 200,
                "max_queue_level_ms": 1000
            }
        }


class TestUnknownMessage:
    def test_create_with_bytes(self):
        known_raw = KnownRaw(KnownRawType.binary, b"test data")
        msg = UnknownMessage.create(known_raw)

        assert msg.raw_type == KnownRawType.binary
        assert msg.raw_data == "test data"  # Decoded to string

    def test_create_with_exception(self):
        exc = ValueError("test error")
        known_raw = KnownRaw(KnownRawType.json, {"test": 1}, exc)
        msg = UnknownMessage.create(known_raw)

        assert msg.error_info is not None
        assert msg.error_info["type"] == "ValueError"
        assert msg.error_info["message"] == "test error"


class TestPipelineTimingsMessage:
    def test_extract_from_nested(self):
        data = {
            "message_type": "pipeline_timings",
            "data": {
                "transcription_id": "123",
                "timings": {"start": 0.1, "end": 0.5}
            }
        }

        msg = PipelineTimingsMessage.model_validate(data)
        assert msg.transcription_id == "123"
        assert msg.timings == {"start": 0.1, "end": 0.5}


class TestTranscriptionMessage:
    def test_dedup(self):
        msg = TranscriptionMessage(
            message_type=Message.Type.PARTIAL_TRANSCRIPTION,
            transcription_id="123",
            text="Hello",
            language=Language("en"),
            segments=[]
        )

        dedup = msg.dedup
        assert "123" in dedup
        assert "Hello" in dedup
