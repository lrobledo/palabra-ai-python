import asyncio
import logging
import queue
import threading
import time
import typing as tp

import sounddevice as sd

logger = logging.getLogger(__name__)


def batch(s: tp.Sequence, n: int = 1) -> tp.Generator:
    for index in range(0, len(s), n):
        yield s[index : min(index + n, len(s))]


class InputSoundDevice:
    def __init__(self, name: str, manager: "SoundDeviceManager"):
        self.name = name
        self.manager = manager

        self.reading_device: bool = False
        self.device_reading_thread: threading.Thread | None = None
        self.stream_latency = -1

        self.sample_rate: int | None = None
        self.channels: int | None = None
        self.audio_chunk_seconds: float | None = None

        self.async_callback_fn: tp.Callable[bytes, None] | None = None
        self.callback_task: asyncio.Task | None = None

        self.buffer: tp.Queue[bytes] = queue.Queue()

    def get_read_delay_ms(self) -> int:
        delay_time = max(0, self.stream_latency + self.audio_chunk_seconds + 0.01)
        return int(delay_time * 1000)

    async def start_reading(
        self,
        async_callback_fn: tp.Callable[[bytes], tp.Awaitable[None]],
        sample_rate: int = 48000,
        channels: int = 2,
        audio_chunk_seconds: float = 0.5,
    ) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self.audio_chunk_seconds = audio_chunk_seconds
        self.async_callback_fn = async_callback_fn

        self.device_reading_thread = threading.Thread(
            name=f'"{self.name}" reader',
            target=self._read_from_device_to_buffer,
            daemon=True,
        )
        self.device_reading_thread.start()

        try:
            self.callback_task = asyncio.create_task(self._run_callback_worker())

            # Wait for latency to be set
            while self.stream_latency < 0:
                await asyncio.sleep(0.01)
        except asyncio.CancelledError:
            logger.warning(f"InputSoundDevice {self.name} start_reading cancelled")
            self.stop_reading(timeout=1)
            raise

        logger.debug(f"Starting reading device: {self.name}")

    def stop_reading(self, timeout: int | None = None) -> None:
        self.reading_device = False
        self.stream_latency = -1

        if (
            self.device_reading_thread is not None
            and self.device_reading_thread.is_alive()
        ):
            self.device_reading_thread.join(timeout=timeout)

        if self.callback_task is not None and not self.callback_task.done():
            self.callback_task.cancel()
            try:
                asyncio.get_event_loop().run_until_complete(self.callback_task)
            except (asyncio.CancelledError, RuntimeError):
                pass

        logger.debug(f"Stopped reading device: {self.name}")

    def _push_to_buffer(self, audio_bytes: bytes, *args) -> None:
        if self.reading_device:
            self.buffer.put(audio_bytes)

    async def _run_callback_worker(self) -> None:
        try:
            while self.reading_device:
                try:
                    audio_bytes = self.buffer.get_nowait()
                    await self.async_callback_fn(audio_bytes)
                except queue.Empty:
                    try:
                        await asyncio.sleep(0.1)
                    except asyncio.CancelledError:
                        logger.warning(
                            f"InputSoundDevice {self.name} callback worker cancelled"
                        )
                        raise
                except asyncio.CancelledError:
                    logger.warning(f"InputSoundDevice {self.name} callback cancelled")
                    raise
        except asyncio.CancelledError:
            logger.warning(f"InputSoundDevice {self.name} callback worker exiting")
            raise

    def _read_from_device_to_buffer(self) -> None:
        device_info = self.manager.get_device_info()

        self.reading_device = True
        try:
            with sd.RawInputStream(
                device=device_info["input_devices"][self.name]["index"],
                channels=self.channels,
                callback=self._push_to_buffer,
                blocksize=int(round(self.audio_chunk_seconds * self.sample_rate)),
                samplerate=self.sample_rate,
                dtype="int16",
            ) as stream:
                self.stream_latency = stream.latency
                logger.debug("Started reading device")
                while self.reading_device:
                    time.sleep(self.audio_chunk_seconds)
                    if not stream.active:
                        break
                    logger.debug("Audio chunk read")
        except Exception:
            logger.exception("Failed to read device with:\n")
        finally:
            self.reading_device = False
            logger.debug("Stopped reading device")


class OutputSoundDevice:
    block_size = 1024

    def __init__(self, name: str, manager: "SoundDeviceManager"):
        self.name = name
        self.manager = manager

        self.writing_device: bool = False
        self.device_writing_thread: threading.Thread | None = None

        self.device_ix: int | None = None
        self.channels: int | None = None
        self.sample_rate: int | None = None
        self.audio_chunk_seconds: float | None = None

        self.stream = None
        self.write_buffer: queue.Queue | None = None

    def start_writing(self, channels: int = 1, sample_rate: int = 24000) -> None:
        device_info = self.manager.get_device_info()["output_devices"][self.name]
        self.device_ix = device_info["index"]
        self.channels = channels
        self.sample_rate = sample_rate
        self.write_buffer = queue.Queue()

        self.device_writing_thread = threading.Thread(
            name=f'"{self.name}" writer', target=self._write_device, daemon=True
        )
        self.device_writing_thread.start()

        logger.debug(f"Starting writing to device: {self.name}")

    def stop_writing(self, timeout: int | None = None) -> None:
        self.writing_device = False
        self.write_buffer = None

        if (
            self.device_writing_thread is not None
            and self.device_writing_thread.is_alive()
        ):
            self.device_writing_thread.join(timeout=timeout)

        logger.debug(f"Stopped writing to device: {self.name}")

    def add_audio_data(self, audio_data: bytes) -> None:
        if self.stream and self.writing_device:
            read_size = self.block_size * self.channels * self.stream.samplesize
            for chunk in batch(audio_data, read_size):
                if not self.writing_device:
                    break
                self.stream.write(chunk)

    def _write_device(self) -> None:
        self.writing_device = True
        try:
            with sd.RawOutputStream(
                device=self.device_ix,
                channels=self.channels,
                blocksize=self.block_size,
                samplerate=self.sample_rate,
                dtype="int16",
            ) as stream:
                self.stream = stream
                self.stream_latency = stream.latency
                logger.debug("Started writing to device")
                while self.writing_device:
                    time.sleep(0.01)
        except Exception:
            logger.exception("Failed to write to device with:\n")
        finally:
            self.writing_device = False
            self.stream = None
            logger.debug("Stopped writing to device")


class SoundDeviceManager:
    def __init__(self):
        self.input_device_map: dict[str, InputSoundDevice] = {}
        self.output_device_map: dict[str, OutputSoundDevice] = {}

    def get_device_info(self, reload_sd: bool = False) -> dict[str, tp.Any]:
        if reload_sd:
            sd._terminate()
            sd._initialize()

        devices = sd.query_devices()
        for hostapi in sd.query_hostapis():
            for device_idx in hostapi["devices"]:
                devices[device_idx]["hostapi_name"] = hostapi["name"]

        input_devices, output_devices = {}, {}
        for device in devices:
            if device["max_input_channels"] > 0:
                input_devices[f"{device['name']} ({device['hostapi_name']})"] = device
            if device["max_output_channels"] > 0:
                output_devices[f"{device['name']} ({device['hostapi_name']})"] = device

        return {"input_devices": input_devices, "output_devices": output_devices}

    async def start_input_device(
        self,
        device_name: str,
        async_callback_fn: tp.Callable[[bytes], tp.Awaitable[None]],
        sample_rate: int = 48000,
        channels: int = 2,
        audio_chunk_seconds: float = 0.5,
    ) -> InputSoundDevice:
        device = self.input_device_map.get(device_name)
        if device is None:
            self.input_device_map[device_name] = device = InputSoundDevice(
                name=device_name, manager=self
            )
        try:
            await device.start_reading(
                async_callback_fn, sample_rate, channels, audio_chunk_seconds
            )
        except asyncio.CancelledError:
            logger.warning(
                f"SoundDeviceManager start_input_device cancelled for {device_name}"
            )
            raise
        return device

    def start_output_device(
        self, device_name: str, channels: int = 1, sample_rate: int = 24000
    ) -> OutputSoundDevice:
        device = self.output_device_map.get(device_name)
        if device is None:
            self.output_device_map[device_name] = device = OutputSoundDevice(
                name=device_name, manager=self
            )
        device.start_writing(channels, sample_rate)
        return device

    def stop_input_device(self, device_name: str, timeout: int = 5) -> None:
        if device_name in self.input_device_map:
            self.input_device_map[device_name].stop_reading(timeout=timeout)

    def stop_output_device(self, device_name: str, timeout: int = 5) -> None:
        if device_name in self.output_device_map:
            self.output_device_map[device_name].stop_writing(timeout=timeout)

    def stop_all(self, timeout: int = 5) -> None:
        for device in self.input_device_map.values():
            device.stop_reading(timeout=timeout)
        for device in self.output_device_map.values():
            device.stop_writing(timeout=timeout)
