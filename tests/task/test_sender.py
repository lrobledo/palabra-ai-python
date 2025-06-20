import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from palabra_ai.task.sender import SenderSourceAudio
from palabra_ai.config import Config
from palabra_ai.internal.webrtc import AudioTrackSettings


class TestSenderSourceAudio:
    @pytest.mark.asyncio
    async def test_boot(self):
        cfg = MagicMock(spec=Config)
        rt = MagicMock()
        # Create a proper awaitable
        async def ready_coro():
            pass
        rt.ready = ready_coro()
        rt.c = MagicMock()
        rt.c.new_translated_publication = AsyncMock(return_value=MagicMock())

        reader = MagicMock()
        settings = {}
        track_settings = AudioTrackSettings()

        sender = SenderSourceAudio(cfg, rt, reader, settings, track_settings)
        await sender.boot()

        rt.c.new_translated_publication.assert_called_once_with(settings, track_settings)
        assert sender._track is not None

    @pytest.mark.asyncio
    async def test_do_processes_audio(self):
        cfg = MagicMock(spec=Config)
        rt = MagicMock()

        reader = MagicMock()
        reader.read = AsyncMock(side_effect=[b"chunk1", b"chunk2", None])

        track = MagicMock()
        track.push = AsyncMock()

        sender = SenderSourceAudio(cfg, rt, reader, {}, AudioTrackSettings())
        sender._track = track

        await sender.do()

        # Should have processed 2 chunks
        assert track.push.call_count == 2
        assert sender.bytes_sent == len(b"chunk1") + len(b"chunk2")
        assert sender.eof.is_set()

    @pytest.mark.asyncio
    async def test_do_empty_chunk(self):
        cfg = MagicMock(spec=Config)
        rt = MagicMock()

        reader = MagicMock()
        reader.read = AsyncMock(side_effect=[b"", b"data", None])

        track = MagicMock()
        track.push = AsyncMock()

        sender = SenderSourceAudio(cfg, rt, reader, {}, AudioTrackSettings())
        sender._track = track

        await sender.do()

        # Should skip empty chunk and process only "data"
        assert track.push.call_count == 1
        assert sender.bytes_sent == len(b"data")

    @pytest.mark.asyncio
    async def test_exit_with_track(self):
        cfg = MagicMock(spec=Config)
        rt = MagicMock()
        reader = MagicMock()

        sender = SenderSourceAudio(cfg, rt, reader, {}, AudioTrackSettings())

        track = MagicMock()
        track.close = AsyncMock()
        sender._track = track

        # Mock sleep to avoid waiting
        with patch('asyncio.sleep', new_callable=AsyncMock):
            await sender.exit()

        track.close.assert_called_once()
        assert sender.eof.is_set()

    @pytest.mark.asyncio
    async def test_exit_track_close_timeout(self):
        cfg = MagicMock(spec=Config)
        rt = MagicMock()
        reader = MagicMock()

        sender = SenderSourceAudio(cfg, rt, reader, {}, AudioTrackSettings())

        track = MagicMock()
        # Make close hang
        async def hanging_close():
            await asyncio.sleep(10)
        track.close = hanging_close
        sender._track = track

        with patch('palabra_ai.constant.TRACK_CLOSE_TIMEOUT', 0.1):
            with patch('asyncio.sleep', new_callable=AsyncMock):
                await sender.exit()

        assert sender.eof.is_set()
