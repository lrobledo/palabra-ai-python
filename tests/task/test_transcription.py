import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from palabra_ai.task.transcription import Transcription
from palabra_ai.base.message import TranscriptionMessage, Message
from palabra_ai.config import Config, SourceLang, TargetLang
from palabra_ai.lang import Language
from palabra_ai.adapter.dummy import DummyWriter
from palabra_ai.task.realtime import RtMsg
from palabra_ai.base.enum import Channel, Direction
from palabra_ai.base.adapter import Reader


class MinimalReader(Reader):
    """Minimal Reader implementation for tests"""
    async def boot(self):
        pass

    async def do(self):
        pass

    async def exit(self):
        pass

    async def read(self, size=None):
        return None


class TestTranscription:
    @pytest.mark.asyncio
    async def test_init_with_callbacks(self):
        # Create config with callbacks
        source_callback = MagicMock()
        target_callback = MagicMock()

        source = SourceLang(
            lang=Language("en"),
            reader=MinimalReader(),
            on_transcription=source_callback
        )

        target = TargetLang(
            lang=Language("es"),
            writer=DummyWriter(),
            on_transcription=target_callback
        )

        cfg = Config(source=source, targets=[target])
        rt = MagicMock()

        trans = Transcription(cfg, rt)

        assert trans._callbacks["en"] == source_callback
        assert trans._callbacks["es"] == target_callback

    @pytest.mark.asyncio
    async def test_boot(self):
        source = SourceLang(lang=Language("en"), reader=MinimalReader())
        target = TargetLang(lang=Language("es"), writer=DummyWriter())
        cfg = Config(source=source, targets=[target])

        rt = MagicMock()
        # Create a proper awaitable
        async def ready_coro():
            pass
        rt.ready = ready_coro()
        rt.out_foq.subscribe.return_value = asyncio.Queue()

        trans = Transcription(cfg, rt)
        await trans.boot()

        assert trans._webrtc_queue is not None
        # Just verify it completes without error

    @pytest.mark.asyncio
    async def test_process_message_with_sync_callback(self):
        callback = MagicMock()

        source = SourceLang(
            lang=Language("en"),
            reader=MinimalReader(),
            on_transcription=callback
        )
        target = TargetLang(lang=Language("es"), writer=DummyWriter())
        cfg = Config(source=source, targets=[target])

        rt = MagicMock()
        trans = Transcription(cfg, rt)
        trans.sub_tg = MagicMock()

        # Create a transcription message
        msg = TranscriptionMessage(
            message_type=Message.Type.PARTIAL_TRANSCRIPTION,
            transcription_id="123",
            text="Hello",
            language=Language("en"),
            segments=[]
        )

        # Mock run_in_executor
        with patch('asyncio.get_event_loop') as mock_loop:
            mock_loop.return_value.run_in_executor = AsyncMock()

            await trans._process_message(msg)

            # Verify callback was scheduled
            mock_loop.return_value.run_in_executor.assert_called_once()
            args = mock_loop.return_value.run_in_executor.call_args[0]
            assert args[0] is None  # executor
            assert args[1] == callback
            assert args[2] == msg

    @pytest.mark.asyncio
    async def test_process_message_with_async_callback(self):
        callback = AsyncMock()

        source = SourceLang(
            lang=Language("en"),
            reader=MinimalReader(),
            on_transcription=callback
        )
        target = TargetLang(lang=Language("es"), writer=DummyWriter())
        cfg = Config(source=source, targets=[target])

        rt = MagicMock()
        trans = Transcription(cfg, rt)
        trans.sub_tg = MagicMock()
        trans.sub_tg.create_task = MagicMock()

        msg = TranscriptionMessage(
            message_type=Message.Type.PARTIAL_TRANSCRIPTION,
            transcription_id="123",
            text="Hello",
            language=Language("en"),
            segments=[]
        )

        await trans._process_message(msg)

        # Verify task was created
        trans.sub_tg.create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_exit(self):
        source = SourceLang(lang=Language("en"), reader=MinimalReader())
        target = TargetLang(lang=Language("es"), writer=DummyWriter())
        cfg = Config(source=source, targets=[target])

        rt = MagicMock()
        rt.out_foq.unsubscribe = MagicMock()

        trans = Transcription(cfg, rt)
        await trans.exit()

        rt.out_foq.unsubscribe.assert_called_once_with(trans)
