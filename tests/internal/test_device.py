import asyncio
import threading
import time
from unittest.mock import patch, MagicMock, AsyncMock, PropertyMock

import pytest

from palabra_ai.internal.device import (
    SoundDeviceManager, InputSoundDevice, OutputSoundDevice, batch
)


def test_batch():
    result = list(batch([1, 2, 3, 4, 5], 2))
    assert result == [[1, 2], [3, 4], [5]]


class TestInputSoundDevice:
    def test_get_read_delay_ms(self):
        device = InputSoundDevice("test", MagicMock())
        device.stream_latency = 0.01
        device.audio_chunk_seconds = 0.5

        delay = device.get_read_delay_ms()
        assert delay == 520  # (0.01 + 0.5 + 0.01) * 1000

    @pytest.mark.asyncio
    async def test_start_reading_basic(self, mock_sounddevice):
        """Test start_reading without hanging"""
        manager = MagicMock()
        manager.get_device_info.return_value = {
            "input_devices": {"test": {"index": 0}}
        }

        device = InputSoundDevice("test", manager)

        # Mock thread to not actually start
        mock_thread = MagicMock()

        with patch("palabra_ai.internal.device.threading.Thread", return_value=mock_thread):
            # Create task and set up immediate latency
            callback = AsyncMock()

            # Start reading but immediately set latency
            start_task = asyncio.create_task(device.start_reading(callback))
            await asyncio.sleep(0.01)  # Let it start
            device.stream_latency = 0.1  # Set latency to exit wait loop

            await start_task

            assert device.sample_rate == 48000
            assert device.channels == 2
            assert device.async_callback_fn == callback
            mock_thread.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_reading_cancelled(self, mock_sounddevice):
        manager = MagicMock()
        manager.get_device_info.return_value = {
            "input_devices": {"test": {"index": 0}}
        }

        device = InputSoundDevice("test", manager)

        # Mock the thread to set latency immediately
        def mock_thread_target(*args, **kwargs):
            device.stream_latency = 0.1

        with patch("palabra_ai.internal.device.threading.Thread") as mock_thread:
            mock_thread_instance = MagicMock()
            mock_thread_instance.start = MagicMock(side_effect=mock_thread_target)
            mock_thread.return_value = mock_thread_instance

            # Cancel during the task creation
            with patch("asyncio.create_task", side_effect=asyncio.CancelledError):
                with pytest.raises(asyncio.CancelledError):
                    await device.start_reading(AsyncMock())

    def test_push_to_buffer(self):
        device = InputSoundDevice("test", MagicMock())
        device.reading_device = True

        device._push_to_buffer(b"audio")
        assert device.buffer.get_nowait() == b"audio"

    @pytest.mark.asyncio
    async def test_run_callback_worker(self):
        device = InputSoundDevice("test", MagicMock())
        device.reading_device = True
        device.async_callback_fn = AsyncMock()

        # Add data to buffer
        device.buffer.put(b"test_audio")

        # Run for one iteration then stop
        async def run_once(audio_bytes):
            device.reading_device = False

        device.async_callback_fn.side_effect = run_once

        await device._run_callback_worker()
        device.async_callback_fn.assert_called_once_with(b"test_audio")

    @pytest.mark.asyncio
    async def test_run_callback_worker_empty_queue(self):
        device = InputSoundDevice("test", MagicMock())
        device.reading_device = True

        # Run briefly then stop
        async def stop_after_delay():
            await asyncio.sleep(0.15)
            device.reading_device = False

        task = asyncio.create_task(stop_after_delay())
        await device._run_callback_worker()
        await task

    @pytest.mark.asyncio
    async def test_run_callback_cancelled(self):
        device = InputSoundDevice("test", MagicMock())
        device.reading_device = True
        device.async_callback_fn = AsyncMock(side_effect=asyncio.CancelledError)
        device.buffer.put(b"test")

        with pytest.raises(asyncio.CancelledError):
            await device._run_callback_worker()

    def test_read_from_device_to_buffer(self, mock_sounddevice):
        manager = MagicMock()
        manager.get_device_info.return_value = {
            "input_devices": {"test": {"index": 0}}
        }

        device = InputSoundDevice("test", manager)

        # Set required parameters
        device.channels = 2
        device.sample_rate = 48000
        device.audio_chunk_seconds = 0.5

        # Mock stream
        mock_stream = MagicMock()
        mock_stream.latency = 0.1
        mock_stream.active = True
        mock_sounddevice.RawInputStream.return_value.__enter__.return_value = mock_stream

        # Run briefly
        def stop_reading():
            time.sleep(0.1)
            device.reading_device = False
            mock_stream.active = False  # Stop the stream

        stop_thread = threading.Thread(target=stop_reading)
        stop_thread.start()

        device._read_from_device_to_buffer()
        stop_thread.join()

        assert device.stream_latency == 0.1

    def test_read_from_device_exception(self, mock_sounddevice):
        manager = MagicMock()
        manager.get_device_info.return_value = {
            "input_devices": {"test": {"index": 0}}
        }

        device = InputSoundDevice("test", manager)
        mock_sounddevice.RawInputStream.side_effect = Exception("Test error")

        device._read_from_device_to_buffer()
        assert not device.reading_device

    def test_read_from_device_inactive_stream(self, mock_sounddevice):
        manager = MagicMock()
        manager.get_device_info.return_value = {
            "input_devices": {"test": {"index": 0}}
        }

        device = InputSoundDevice("test", manager)

        # Mock inactive stream
        mock_stream = MagicMock()
        mock_stream.latency = 0.1
        mock_stream.active = False
        mock_sounddevice.RawInputStream.return_value.__enter__.return_value = mock_stream

        device._read_from_device_to_buffer()
        assert not device.reading_device


class TestOutputSoundDevice:
    def test_start_stop_writing(self, mock_sounddevice):
        manager = MagicMock()
        manager.get_device_info.return_value = {
            "output_devices": {"test": {"index": 0}}
        }

        device = OutputSoundDevice("test", manager)

        with patch("palabra_ai.internal.device.threading.Thread") as mock_thread:
            mock_thread_instance = MagicMock()
            mock_thread.return_value = mock_thread_instance

            device.start_writing()

            assert device.channels == 1
            assert device.sample_rate == 24000
            mock_thread_instance.start.assert_called_once()

            device.stop_writing(timeout=1)
            mock_thread_instance.join.assert_called_once()

    def test_add_audio_data(self, mock_sounddevice):
        device = OutputSoundDevice("test", MagicMock())
        device.writing_device = True
        device.channels = 1

        # Mock stream
        mock_stream = MagicMock()
        mock_stream.samplesize = 2
        device.stream = mock_stream

        # Add data - should be batched
        device.add_audio_data(b"\x00" * 4096)

        # 4096 bytes / (1024 * 1 * 2) = 2 calls
        assert mock_stream.write.call_count == 2

    def test_add_audio_data_not_writing(self):
        device = OutputSoundDevice("test", MagicMock())
        device.writing_device = False
        device.stream = MagicMock()

        device.add_audio_data(b"\x00" * 100)
        device.stream.write.assert_not_called()

    def test_write_device(self, mock_sounddevice):
        manager = MagicMock()
        device = OutputSoundDevice("test", manager)
        device.device_ix = 0
        device.channels = 1
        device.sample_rate = 24000

        # Mock stream
        mock_stream = MagicMock()
        mock_stream.latency = 0.1
        mock_sounddevice.RawOutputStream.return_value.__enter__.return_value = mock_stream

        # Run briefly
        def stop_writing():
            time.sleep(0.02)
            device.writing_device = False

        stop_thread = threading.Thread(target=stop_writing)
        stop_thread.start()

        device._write_device()
        stop_thread.join()

        assert device.stream_latency == 0.1

    def test_write_device_exception(self, mock_sounddevice):
        device = OutputSoundDevice("test", MagicMock())
        device.device_ix = 0
        device.channels = 1
        device.sample_rate = 24000

        mock_sounddevice.RawOutputStream.side_effect = Exception("Test error")

        device._write_device()
        assert not device.writing_device


class TestSoundDeviceManager:
    def test_get_device_info(self, mock_sounddevice):
        sdm = SoundDeviceManager()
        info = sdm.get_device_info()

        assert "input_devices" in info
        assert "output_devices" in info
        assert len(info["input_devices"]) > 0

    def test_get_device_info_reload(self, mock_sounddevice):
        sdm = SoundDeviceManager()
        mock_sounddevice._terminate = MagicMock()
        mock_sounddevice._initialize = MagicMock()

        info = sdm.get_device_info(reload_sd=True)

        mock_sounddevice._terminate.assert_called_once()
        mock_sounddevice._initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_input_device(self, mock_sounddevice):
        sdm = SoundDeviceManager()

        with patch("palabra_ai.internal.device.InputSoundDevice") as mock_input_device_class:
            mock_device = MagicMock()
            mock_device.name = "test (test)"
            mock_device.start_reading = AsyncMock()
            mock_input_device_class.return_value = mock_device

            callback = AsyncMock()
            device = await sdm.start_input_device("test (test)", callback)

            assert device is not None
            assert device.name == "test (test)"
            mock_device.start_reading.assert_called_once()

            mock_device.stop_reading = MagicMock()
            sdm.stop_input_device("test (test)")

    @pytest.mark.asyncio
    async def test_start_existing_input_device(self, mock_sounddevice):
        sdm = SoundDeviceManager()

        # Add existing device
        existing = MagicMock()
        existing.start_reading = AsyncMock()
        sdm.input_device_map["test"] = existing

        device = await sdm.start_input_device("test", AsyncMock())
        assert device is existing

    @pytest.mark.asyncio
    async def test_start_input_device_cancelled(self, mock_sounddevice):
        sdm = SoundDeviceManager()

        with patch("palabra_ai.internal.device.InputSoundDevice") as mock_class:
            mock_device = MagicMock()
            mock_device.start_reading = AsyncMock(side_effect=asyncio.CancelledError)
            mock_class.return_value = mock_device

            with pytest.raises(asyncio.CancelledError):
                await sdm.start_input_device("test", AsyncMock())

    def test_start_output_device(self, mock_sounddevice):
        sdm = SoundDeviceManager()

        with patch("palabra_ai.internal.device.OutputSoundDevice") as mock_output_device_class:
            mock_device = MagicMock()
            mock_device.name = "test (test)"
            mock_device.start_writing = MagicMock()
            mock_output_device_class.return_value = mock_device

            device = sdm.start_output_device("test (test)")

            assert device is not None
            assert device.name == "test (test)"
            mock_device.start_writing.assert_called_once()

            mock_device.stop_writing = MagicMock()
            sdm.stop_output_device("test (test)")

    def test_stop_nonexistent_devices(self):
        sdm = SoundDeviceManager()

        # Should not raise
        sdm.stop_input_device("nonexistent")
        sdm.stop_output_device("nonexistent")

    def test_stop_all(self):
        sdm = SoundDeviceManager()

        # Add mock devices
        input_device = MagicMock()
        output_device = MagicMock()

        sdm.input_device_map["input"] = input_device
        sdm.output_device_map["output"] = output_device

        sdm.stop_all()

        input_device.stop_reading.assert_called_once_with(timeout=5)
        output_device.stop_writing.assert_called_once_with(timeout=5)
