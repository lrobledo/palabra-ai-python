import asyncio
from unittest.mock import patch, AsyncMock, MagicMock

import pytest

from palabra_ai.internal.buffer import AudioBufferWriter


class TestAudioBufferWriter:
    @pytest.mark.asyncio
    async def test_start_creates_task(self):
        writer = AudioBufferWriter()
        await writer.start()
        assert writer._task is not None
        assert not writer._task.done()
        await writer.stop()

    @pytest.mark.asyncio
    async def test_start_existing_task(self):
        writer = AudioBufferWriter()
        await writer.start()
        first_task = writer._task

        # Start again - should warn but not create new task
        await writer.start()
        assert writer._task is first_task

        await writer.stop()

    @pytest.mark.asyncio
    async def test_task_dies_immediately(self):
        writer = AudioBufferWriter()

        # Mock task to die immediately
        with patch.object(writer, '_write', side_effect=Exception("Test error")):
            await writer.start()
            await asyncio.sleep(0.2)  # Let task fail

            # Task should be done with exception
            assert writer._task.done()

    @pytest.mark.asyncio
    async def test_write_to_buffer(self, mock_audio_frame):
        writer = AudioBufferWriter()
        await writer.start()

        await writer.queue.put(mock_audio_frame)

        timeout = 0.5
        start_time = asyncio.get_event_loop().time()
        while writer._frames_processed == 0:
            await asyncio.sleep(0.05)
            if asyncio.get_event_loop().time() - start_time > timeout:
                break

        assert writer.buffer.tell() > 0
        assert writer._frames_processed == 1

        await writer.stop()

    @pytest.mark.asyncio
    async def test_write_none_frame(self):
        writer = AudioBufferWriter()
        await writer.start()

        await writer.queue.put(None)
        await asyncio.sleep(0.1)

        # Task should exit on None
        assert writer._task.done()

    @pytest.mark.asyncio
    async def test_drop_empty_frames(self, mock_audio_frame):
        writer = AudioBufferWriter(drop_empty_frames=True)
        await writer.start()

        # Empty frame
        empty_frame = MagicMock()
        empty_frame.data.tobytes.return_value = b"\x00" * 100

        await writer.queue.put(empty_frame)
        await asyncio.sleep(0.1)

        # Should not write empty frames
        assert writer.buffer.tell() == 0

        await writer.stop()

    @pytest.mark.asyncio
    async def test_stop_cancelled(self):
        writer = AudioBufferWriter()
        await writer.start()

        # Mock task to raise CancelledError
        writer._task.cancel()

        await writer.stop()
        assert writer._task is None

    @pytest.mark.asyncio
    async def test_write_cancelled(self):
        writer = AudioBufferWriter()

        # Start the writer task
        await writer.start()

        # Cancel the task
        writer._task.cancel()

        # Now _write should raise CancelledError when we await the task
        with pytest.raises(asyncio.CancelledError):
            await writer._task

    def test_to_wav_bytes_without_frames(self):
        writer = AudioBufferWriter()
        result = writer.to_wav_bytes()
        assert result == b""

    def test_to_wav_bytes_with_frame(self, mock_audio_frame):
        writer = AudioBufferWriter()
        writer._frame_sample = mock_audio_frame
        writer.buffer.write(b"test_data")

        result = writer.to_wav_bytes()
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_write_to_disk(self):
        writer = AudioBufferWriter()
        writer._frame_sample = MagicMock(num_channels=1, sample_rate=48000)

        with patch("palabra_ai.internal.buffer.aiofile.async_open") as mock_open:
            mock_file = AsyncMock()
            mock_open.return_value.__aenter__.return_value = mock_file

            result = await writer.write_to_disk("test.wav")
            mock_file.write.assert_called_once()

    @pytest.mark.asyncio
    async def test_write_to_disk_cancelled(self):
        writer = AudioBufferWriter()

        with patch("palabra_ai.internal.buffer.aiofile.async_open") as mock_open:
            mock_file = AsyncMock()
            mock_file.write.side_effect = asyncio.CancelledError()
            mock_open.return_value.__aenter__.return_value = mock_file

            with pytest.raises(asyncio.CancelledError):
                await writer.write_to_disk("test.wav")
