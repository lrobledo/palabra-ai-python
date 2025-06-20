import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from palabra_ai.task.transcription import Transcription
from palabra_ai.base.message import Message, TranscriptionMessage
from palabra_ai.config import Config, SourceLang, TargetLang
from palabra_ai.lang import Language
from palabra_ai.adapter.dummy import DummyWriter
from palabra_ai.base.adapter import Reader


class MinimalReader(Reader):
    async def boot(self): pass
    async def do(self): pass
    async def exit(self): pass
    async def read(self, size=None): return None


class TestTranscriptionCoverage:
    @pytest.mark.asyncio
    async def test_process_message_no_callback(self):
        """Test processing message for language without callback"""
        source = SourceLang(lang=Language("en"), reader=MinimalReader())
        target = TargetLang(lang=Language("es"), writer=DummyWriter())
        cfg = Config(source=source, targets=[target])

        rt = MagicMock()
        trans = Transcription(cfg, rt)

        # Message for language without callback
        msg = TranscriptionMessage(
            message_type=Message.Type.PARTIAL_TRANSCRIPTION,
            transcription_id="123",
            text="Hello",
            language=Language("fr"),  # No callback for French
            segments=[]
        )

        await trans._process_message(msg)
        # Should complete without error

    @pytest.mark.asyncio
    async def test_process_message_callback_error_suppressed(self):
        """Test callback error is suppressed when suppress_callback_errors=True"""
        def error_callback(data):
            raise ValueError("Test error")

        source = SourceLang(
            lang=Language("en"),
            reader=MinimalReader(),
            on_transcription=error_callback
        )
        target = TargetLang(lang=Language("es"), writer=DummyWriter())
        cfg = Config(source=source, targets=[target])

        rt = MagicMock()
        trans = Transcription(cfg, rt)
        trans.suppress_callback_errors = True

        msg = TranscriptionMessage(
            message_type=Message.Type.PARTIAL_TRANSCRIPTION,
            transcription_id="123",
            text="Hello",
            language=Language("en"),
            segments=[]
        )

        # Mock run_in_executor to actually call the callback
        with patch('asyncio.get_event_loop') as mock_loop:
            async def mock_executor(executor, func, *args):
                func(*args)
            mock_loop.return_value.run_in_executor = mock_executor

            # Should not raise even though callback errors
            await trans._process_message(msg)

    @pytest.mark.asyncio
    async def test_process_message_non_transcription(self):
        """Test processing non-transcription message"""
        source = SourceLang(lang=Language("en"), reader=MinimalReader())
        target = TargetLang(lang=Language("es"), writer=DummyWriter())
        cfg = Config(source=source, targets=[target])

        rt = MagicMock()
        trans = Transcription(cfg, rt)

        # Non-transcription message
        msg = Message(message_type=Message.Type.PIPELINE_TIMINGS)

        await trans._process_message(msg)
        # Should return early without processing
