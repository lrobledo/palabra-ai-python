import asyncio
import io
from unittest.mock import patch, AsyncMock, MagicMock

import pytest

from palabra_ai.internal.buffer import AudioBufferWriter


class TestAudioBufferWriter:
    @pytest.mark.asyncio
    async def test_start_creates_task(self):
        async with asyncio.TaskGroup() as tg:
            writer = AudioBufferWriter(tg)
            await writer.start()
            assert writer._task is not None
            assert not writer._task.done()
            await writer.stop()

    @pytest.mark.asyncio
    async def test_start_existing_task(self):
        async with asyncio.TaskGroup() as tg:
            writer = AudioBufferWriter(tg)
            await writer.start()
            first_task = writer._task

            # Start again - should warn but not create new task
            await writer.start()
            assert writer._task is first_task

            await writer.stop()

    @pytest.mark.asyncio
    async def test_task_dies_immediately(self):
        # TaskGroup will catch and re-raise exceptions as ExceptionGroup
        with pytest.raises(ExceptionGroup) as exc_info:
            async with asyncio.TaskGroup() as tg:
                writer = AudioBufferWriter(tg)

                # Mock _write to raise exception immediately
                async def failing_write():
                    raise Exception("Test error")

                writer._write = failing_write
                await writer.start()
                await asyncio.sleep(0.2)  # Let task fail

        # Check that the exception was raised
        assert len(exc_info.value.exceptions) == 1
        assert isinstance(exc_info.value.exceptions[0], Exception)
        assert str(exc_info.value.exceptions[0]) == "Test error"

    @pytest.mark.asyncio
    async def test_write_to_buffer(self, mock_audio_frame):
        async with asyncio.TaskGroup() as tg:
            writer = AudioBufferWriter(tg)
            await writer.start()

            await writer.queue.put(mock_audio_frame)

            # Wait for frame to be processed
            timeout = 1.0
            start_time = asyncio.get_event_loop().time()
            while writer._frames_processed == 0:
                await asyncio.sleep(0.01)
                if asyncio.get_event_loop().time() - start_time > timeout:
                    break

            assert writer.buffer.tell() > 0
            assert writer._frames_processed == 1

            await writer.stop()

    @pytest.mark.asyncio
    async def test_write_none_frame(self):
        async with asyncio.TaskGroup() as tg:
            writer = AudioBufferWriter(tg)
            await writer.start()

            await writer.queue.put(None)

            # Wait for task to finish
            timeout = 1.0
            start_time = asyncio.get_event_loop().time()
            while not writer._task.done():
                await asyncio.sleep(0.01)
                if asyncio.get_event_loop().time() - start_time > timeout:
                    break

            # Task should exit on None
            assert writer._task.done()

    @pytest.mark.asyncio
    async def test_drop_empty_frames(self, mock_audio_frame):
        async with asyncio.TaskGroup() as tg:
            writer = AudioBufferWriter(tg, drop_empty_frames=True)
            await writer.start()

            # Empty frame
            empty_frame = MagicMock()
            empty_frame.data.tobytes.return_value = b"\x00" * 100

            await writer.queue.put(empty_frame)
            await asyncio.sleep(0.2)  # Wait for processing

            # Should not write empty frames
            assert writer.buffer.tell() == 0

            await writer.stop()

    @pytest.mark.asyncio
    async def test_stop_cancelled(self):
        async with asyncio.TaskGroup() as tg:
            writer = AudioBufferWriter(tg)
            await writer.start()

            # Cancel the task
            writer._task.cancel()

            await writer.stop()
            assert writer._task is None

    @pytest.mark.asyncio
    async def test_write_cancelled(self):
        # This test needs special handling since TaskGroup catches cancellation
        writer = None
        task_ref = None

        try:
            async with asyncio.TaskGroup() as tg:
                writer = AudioBufferWriter(tg)
                await writer.start()
                task_ref = writer._task

                # Cancel and wait a bit
                writer._task.cancel()
                await asyncio.sleep(0.1)
        except* asyncio.CancelledError:
            # TaskGroup will re-raise cancellation
            pass

        # Task should be cancelled
        assert task_ref and task_ref.cancelled()

    def test_to_wav_bytes_without_frames(self):
        # This test doesn't need TaskGroup since it doesn't start the writer
        buffer = io.BytesIO()
        writer = AudioBufferWriter(MagicMock(), buffer=buffer)
        result = writer.to_wav_bytes()
        assert result == b""

    def test_to_wav_bytes_with_frame(self, mock_audio_frame):
        # This test doesn't need TaskGroup since it doesn't start the writer
        buffer = io.BytesIO()
        writer = AudioBufferWriter(MagicMock(), buffer=buffer)
        writer._frame_sample = mock_audio_frame
        writer.buffer.write(b"test_data")

        result = writer.to_wav_bytes()
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_write_to_disk(self):
        # This test doesn't need TaskGroup since write_to_disk is independent
        writer = AudioBufferWriter(MagicMock())
        writer._frame_sample = MagicMock(num_channels=1, sample_rate=48000)

        with patch("palabra_ai.internal.buffer.aiofile.async_open") as mock_open:
            mock_file = AsyncMock()
            mock_open.return_value.__aenter__.return_value = mock_file

            result = await writer.write_to_disk("test.wav")
            mock_file.write.assert_called_once()

    @pytest.mark.asyncio
    async def test_write_to_disk_cancelled(self):
        # This test doesn't need TaskGroup since write_to_disk is independent
        writer = AudioBufferWriter(MagicMock())

        with patch("palabra_ai.internal.buffer.aiofile.async_open") as mock_open:
            mock_file = AsyncMock()
            mock_file.write.side_effect = asyncio.CancelledError()
            mock_open.return_value.__aenter__.return_value = mock_file

            with pytest.raises(asyncio.CancelledError):
                await writer.write_to_disk("test.wav")
