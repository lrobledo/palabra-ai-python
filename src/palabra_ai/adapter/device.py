from __future__ import annotations

import asyncio
import hashlib
import signal
from concurrent.futures import ThreadPoolExecutor
from dataclasses import KW_ONLY, dataclass, field
from functools import partial
from typing import NamedTuple

from loguru import logger

from palabra_ai.adapter._common import run_until_stopped
from palabra_ai.base.adapter import Reader, Writer
from palabra_ai.base.task import TaskEvent
from palabra_ai.config import (
    CHANNELS_MONO,
    DEVICE_ID_HASH_LENGTH,
    QUEUE_READ_TIMEOUT,
    QUEUE_WAIT_TIMEOUT,
    SAMPLE_RATE_DEFAULT,
    THREADPOOL_MAX_WORKERS,
)
from palabra_ai.internal.buffer import AudioBufferWriter
from palabra_ai.internal.device import SoundDeviceManager
from palabra_ai.internal.webrtc import AudioTrackSettings


class Device(NamedTuple):
    name: str
    id: str
    channels: int
    sample_rate: int
    is_default: bool = False


class DeviceManager:
    """Manage audio devices."""

    def __init__(self):
        self._sdm = SoundDeviceManager()
        self._refresh_devices()

    def _refresh_devices(self):
        """Refresh device list."""
        info = self._sdm.get_device_info()

        self._input_devices = self._parse_devices(
            info["input_devices"], info.get("default_input_device", "")
        )

        self._output_devices = self._parse_devices(
            info["output_devices"], info.get("default_output_device", "")
        )

    def _parse_devices(self, devices: dict, default_name: str) -> list[Device]:
        """Parse device info into Device objects."""
        result = []
        for name, dev_info in devices.items():
            if isinstance(dev_info, dict):
                channels = dev_info.get("channels", CHANNELS_MONO)
                sample_rate = dev_info.get("sample_rate", SAMPLE_RATE_DEFAULT)
            else:
                channels = CHANNELS_MONO
                sample_rate = SAMPLE_RATE_DEFAULT

            result.append(
                Device(
                    name=name,
                    id=hashlib.md5(name.encode()).hexdigest()[:DEVICE_ID_HASH_LENGTH],
                    channels=channels,
                    sample_rate=sample_rate,
                    is_default=(name == default_name),
                )
            )
        return result

    def get_input_devices(self) -> list[Device]:
        return self._input_devices

    def get_output_devices(self) -> list[Device]:
        return self._output_devices

    def get_device_info(self) -> dict:
        return self._sdm.get_device_info()

    def get_default_devices(self) -> tuple[Device | None, Device | None]:
        default_input = next((d for d in self._input_devices if d.is_default), None)
        default_output = next((d for d in self._output_devices if d.is_default), None)
        return default_input, default_output

    def get_default_readers_writers(
        self,
    ) -> tuple[DeviceReader | None, DeviceWriter | None]:
        input_device, output_device = self.get_default_devices()
        reader = DeviceReader(input_device) if input_device else None
        writer = DeviceWriter(output_device) if output_device else None
        return reader, writer

    def get_device_by_name(
        self, name: str, device_type: str = "input"
    ) -> Device | None:
        devices = (
            self._input_devices if device_type == "input" else self._output_devices
        )
        return next((d for d in devices if d.name == name), None)

    def get_device_by_id(
        self, device_id: str, device_type: str = "input"
    ) -> Device | None:
        devices = (
            self._input_devices if device_type == "input" else self._output_devices
        )
        return next((d for d in devices if d.id == device_id), None)

    def get_device_by_index(
        self, index: int, device_type: str = "input"
    ) -> Device | None:
        devices = (
            self._input_devices if device_type == "input" else self._output_devices
        )
        if 0 <= index < len(devices):
            return devices[index]
        return None

    def get_mic_by_name(self, name: str) -> DeviceReader | None:
        device = self.get_device_by_name(name, "input")
        return DeviceReader(device) if device else None

    def get_speaker_by_name(self, name: str) -> DeviceWriter | None:
        device = self.get_device_by_name(name, "output")
        return DeviceWriter(device) if device else None

    def select_devices_interactive(self) -> tuple[DeviceReader, DeviceWriter]:
        """Interactive device selection."""

        def select_device(devices: list[Device], device_type: str) -> Device:
            print(f"\nSelect {device_type} device:")
            for i, device in enumerate(devices):
                default = " [DEFAULT]" if device.is_default else ""
                print(f"{i}: {device.name}{default}")

            while True:
                try:
                    idx = int(input(f"{device_type.capitalize()} device: "))
                    if 0 <= idx < len(devices):
                        return devices[idx]
                    print("Invalid selection.")
                except ValueError:
                    print("Enter a number.")

        input_device = select_device(self._input_devices, "input")
        output_device = select_device(self._output_devices, "output")

        return DeviceReader(input_device), DeviceWriter(output_device)


@dataclass
class DeviceReader(Reader):
    """Read PCM audio from device."""

    device: Device | str
    _: KW_ONLY
    q: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=0))
    track_settings: AudioTrackSettings | None = field(
        default_factory=AudioTrackSettings
    )
    sdm: SoundDeviceManager = field(default_factory=SoundDeviceManager)
    started: TaskEvent = field(default_factory=asyncio.Event, init=False)

    def __post_init__(self):
        self._setup_signal_handlers()

    def _setup_signal_handlers(self):
        try:
            loop = asyncio.get_running_loop()

            def handle_signal():
                +self.eof  # noqa
                logger.debug("Device reader received signal, setting EOF")

            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, handle_signal)
        except RuntimeError:
            logger.warning("No running loop for signal handlers")

    def set_track_settings(self, track_settings: AudioTrackSettings) -> None:
        self.track_settings = track_settings

    async def _audio_callback(self, data: bytes) -> None:
        try:
            await self.q.put(data)
        except asyncio.CancelledError:
            logger.warning("DeviceReader audio callback cancelled")
            raise

    async def run(self):
        if not self.track_settings:
            self.track_settings = AudioTrackSettings()

        device_name = (
            self.device.name if isinstance(self.device, Device) else self.device
        )

        try:
            await self.sdm.start_input_device(
                device_name,
                channels=CHANNELS_MONO,
                sample_rate=self.track_settings.sample_rate,
                async_callback_fn=self._audio_callback,
                audio_chunk_seconds=self.chunk_size / self.track_settings.sample_rate,
            )
            +self.started  # noqa
            logger.debug(f"Started input: {device_name}")
            +self.ready  # noqa

            await self._benefit()

        except asyncio.CancelledError:
            logger.warning("DeviceReader run cancelled")
            raise
        finally:
            await self._cleanup()

    async def _cleanup(self):
        if self.started:
            try:
                device_name = (
                    self.device.name if isinstance(self.device, Device) else self.device
                )
                self.sdm.stop_input_device(device_name)
                -self.started  # noqa
            except Exception as e:
                logger.error(f"Error stopping input device: {e}")

    async def read(self, size: int | None = None) -> bytes | None:
        if not self.started:
            await self.ready

        try:
            chunk = await asyncio.wait_for(self.q.get(), timeout=QUEUE_READ_TIMEOUT)
            return chunk
        except TimeoutError:
            return None
        except asyncio.CancelledError:
            logger.warning("DeviceReader read cancelled")
            raise


@dataclass
class DeviceWriter(Writer):
    """Write PCM audio to device."""

    _buffer_writer: AudioBufferWriter = field(
        default_factory=AudioBufferWriter, init=False
    )
    _sdm: SoundDeviceManager = field(default_factory=SoundDeviceManager, init=False)
    _output_device: object | None = field(default=None, init=False)
    _play_task: asyncio.Task | None = field(default=None, init=False)
    _started: bool = field(default=False, init=False)
    _executor: ThreadPoolExecutor = field(
        default_factory=lambda: ThreadPoolExecutor(max_workers=THREADPOOL_MAX_WORKERS),
        init=False,
    )
    _track_settings: AudioTrackSettings | None = field(default=None, init=False)

    def set_track_settings(self, track_settings: AudioTrackSettings) -> None:
        self._track_settings = track_settings

    def get_queue(self) -> asyncio.Queue:
        return self._buffer_writer.queue

    async def run(self):
        if not self._track_settings:
            self._track_settings = AudioTrackSettings()

        try:
            await self._buffer_writer.start()
            self._started = True

            device_name = (
                self.device.name if isinstance(self.device, Device) else self.device
            )

            self._output_device = self._sdm.start_output_device(
                device_name,
                channels=CHANNELS_MONO,
                sample_rate=self._track_settings.sample_rate,
            )

            self._play_task = self._tg.create_task(self._play_audio())
            logger.debug(f"Started output: {device_name}")
            +self.ready  # noqa

            await run_until_stopped(self)

        except asyncio.CancelledError:
            logger.warning("DeviceWriter run cancelled")
            raise
        finally:
            await self.finalize()

    async def finalize(self) -> bytes:
        try:
            if self._play_task:
                await self._buffer_writer.queue.put(None)
                try:
                    await self._play_task
                except asyncio.CancelledError:
                    pass

            await self._stop_device()

            wav_data = self._buffer_writer.to_wav_bytes()
            if wav_data:
                logger.debug(f"Generated {len(wav_data)} bytes of WAV data")
            else:
                logger.warning("No WAV data generated")

            self._executor.shutdown(wait=True)
            return wav_data
        except asyncio.CancelledError:
            logger.warning("DeviceWriter finalize cancelled")
            raise

    async def cancel(self) -> None:
        if self._play_task:
            self._play_task.cancel()
            try:
                await self._play_task
            except asyncio.CancelledError:
                pass

        await self._stop_device()
        self._executor.shutdown(wait=False)

    async def _stop_device(self):
        if self._output_device:
            device_name = (
                self.device.name if isinstance(self.device, Device) else self.device
            )
            try:
                self._sdm.stop_output_device(device_name)
            except Exception as e:
                logger.error(f"Error stopping output device: {e}")

    async def _play_audio(self) -> None:
        loop = asyncio.get_running_loop()
        eof_received = False

        try:
            while True:
                try:
                    audio_frame = await asyncio.wait_for(
                        self._buffer_writer.queue.get(), timeout=QUEUE_WAIT_TIMEOUT
                    )

                    if audio_frame is None:
                        logger.debug("DeviceWriter received EOF marker")
                        eof_received = True
                        break

                    audio_bytes = audio_frame.data.tobytes()
                    await loop.run_in_executor(
                        self._executor,
                        partial(self._output_device.add_audio_data, audio_bytes),
                    )
                except TimeoutError:
                    if eof_received and self._buffer_writer.queue.qsize() == 0:
                        logger.debug("EOF received and queue empty, exiting play loop")
                        break
                    continue
                except asyncio.CancelledError:
                    logger.warning("DeviceWriter play audio cancelled")
                    raise
                except Exception as e:
                    logger.error(f"Play error: {e}")
        except asyncio.CancelledError:
            logger.warning("DeviceWriter play loop exiting due to cancellation")
            raise
