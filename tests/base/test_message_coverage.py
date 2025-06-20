import pytest
from palabra_ai.base.message import Message, TranscriptionMessage, TranscriptionSegment
from palabra_ai.lang import Language


class TestMessageCoverage:
    def test_message_str(self):
        """Test Message.__str__ method"""
        # Use an actual message type from the enum
        msg = Message(message_type=Message.Type.PIPELINE_TIMINGS)
        str_repr = str(msg)
        assert isinstance(str_repr, str)
        assert "pipeline_timings" in str_repr

    def test_transcription_segment_repr(self):
        """Test TranscriptionSegment.__repr__ method"""
        # Use correct field names for TranscriptionSegment
        segment = TranscriptionSegment(
            text="Hello",
            confidence=0.95,
            start=1.0,
            end=2.0,
            start_timestamp=1.0
        )
        repr_str = repr(segment)
        assert isinstance(repr_str, str)
        assert "Hello" in repr_str

    def test_transcription_message_duration(self):
        """Test TranscriptionMessage duration calculation if it exists"""
        msg = TranscriptionMessage(
            message_type=Message.Type.PARTIAL_TRANSCRIPTION,
            transcription_id="123",
            text="Hello world",
            language=Language("en"),
            segments=[
                TranscriptionSegment(
                    text="Hello",
                    confidence=0.9,
                    start=1.0,
                    end=1.5,
                    start_timestamp=1.0
                ),
                TranscriptionSegment(
                    text="world",
                    confidence=0.9,
                    start=1.5,
                    end=2.0,
                    start_timestamp=1.5
                )
            ]
        )

        # Test basic properties exist
        assert msg.text == "Hello world"
        assert len(msg.segments) == 2

    def test_transcription_message_no_segments(self):
        """Test TranscriptionMessage with no segments"""
        msg = TranscriptionMessage(
            message_type=Message.Type.PARTIAL_TRANSCRIPTION,
            transcription_id="123",
            text="Hello",
            language=Language("en"),
            segments=[]
        )

        # Just verify it was created successfully
        assert msg.text == "Hello"
        assert len(msg.segments) == 0
