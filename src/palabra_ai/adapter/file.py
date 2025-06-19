from __future__ import annotations

import asyncio
from dataclasses import KW_ONLY, dataclass
from pathlib import Path

from loguru import logger

from palabra_ai.adapter._common import warn_if_cancel
from palabra_ai.base.adapter import Reader, Writer
from palabra_ai.config import SLEEP_INTERVAL_DEFAULT
from palabra_ai.internal.audio import (
    convert_any_to_pcm16,
    read_from_disk,
    write_to_disk,
)
from palabra_ai.internal.buffer import AudioBufferWriter
from palabra_ai.internal.webrtc import AudioTrackSettings


@dataclass
class FileReader(Reader):
    """Read PCM audio from file."""

    path: Path | str
    _: KW_ONLY

    _pcm_data: bytes | None = None
    _position: int = 0
    _track_settings: AudioTrackSettings | None = None

    def __post_init__(self):
        self.path = Path(self.path)
        if not self.path.exists():
            raise FileNotFoundError(f"File not found: {self.path}")

    def set_track_settings(self, track_settings: AudioTrackSettings) -> None:
        self._track_settings = track_settings

    async def boot(self):
        if not self._track_settings:
            self._track_settings = AudioTrackSettings()

        logger.debug(f"Loading and converting audio file {self.path}...")
        raw_data = await warn_if_cancel(
            read_from_disk(self.path), "FileReader read_from_disk cancelled"
        )
        logger.debug(f"Loaded {len(raw_data)} bytes from {self.path}")

        logger.debug("Converting audio to PCM16 format...")
        try:
            self._pcm_data = convert_any_to_pcm16(
                raw_data, sample_rate=self._track_settings.sample_rate
            )
            logger.debug(f"Converted to {len(self._pcm_data)} bytes")
        except Exception as e:
            logger.error(f"Failed to convert audio: {e}")
            raise

    async def do(self):
        while not self.stopper and not self.eof:
            await asyncio.sleep(SLEEP_INTERVAL_DEFAULT)

    async def exit(self):
        logger.debug(
            f"{self.name} exiting, position: {self._position}, eof: {self.eof}"
        )
        if not self.eof:
            logger.warning(f"{self.name} stopped without reaching EOF")
        else:
            logger.debug(f"{self.name} reached EOF at position {self._position}")

    async def read(self, size: int | None = None) -> bytes | None:
        await self.ready
        size = size or self.chunk_size

        if self._position >= len(self._pcm_data):
            logger.debug(f"EOF reached at position {self._position}")
            +self.eof  # noqa
            return None

        chunk = self._pcm_data[self._position : self._position + size]
        self._position += len(chunk)

        return chunk if chunk else None


@dataclass
class FileWriter(Writer):
    """Write PCM audio to file."""

    path: Path | str
    delete_on_error: bool = False
    _: KW_ONLY

    def __post_init__(self):
        self.path = Path(self.path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._buffer_writer = AudioBufferWriter(queue=self.q)

    async def boot(self):
        await self._buffer_writer.start()

    async def do(self):
        while not self.stopper:
            await asyncio.sleep(SLEEP_INTERVAL_DEFAULT)

    async def exit(self) -> bytes:
        logger.debug("Finalizing FileWriter...")

        # Wait for the buffer writer task to complete (it will finish when EOF marker is processed)
        if self._buffer_writer._task and not self._buffer_writer._task.done():
            try:
                logger.debug("Waiting for AudioBufferWriter task to complete...")
                await self._buffer_writer._task
                logger.debug("AudioBufferWriter task completed")
            except asyncio.CancelledError:
                logger.warning("AudioBufferWriter task was cancelled")
            except Exception as e:
                logger.warning(f"AudioBufferWriter task failed: {e}")

        logger.debug("All frames processed, generating WAV...")

        wav_data = b""
        try:
            wav_data = self._buffer_writer.to_wav_bytes()
            if wav_data:
                logger.debug(f"Generated {len(wav_data)} bytes of WAV data")
                await warn_if_cancel(
                    write_to_disk(self.path, wav_data),
                    "FileWriter write_to_disk cancelled",
                )
                logger.debug(f"Saved {len(wav_data)} bytes to {self.path}")
            else:
                logger.warning("No WAV data generated")
        except asyncio.CancelledError:
            logger.warning("FileWriter finalize cancelled during WAV processing")
            raise
        except Exception as e:
            logger.error(f"Error converting to WAV: {e}", exc_info=True)

        +self.eof  # noqa

        if self.delete_on_error and self.path.exists():
            try:
                self.path.unlink()
                logger.debug(f"Removed partial file {self.path}")
            except asyncio.CancelledError:
                logger.warning("FileWriter cancel interrupted")
                raise
            except Exception as e:
                logger.error(f"Failed to remove partial file: {e}")
        else:
            logger.debug(
                f"Keeping partial file {self.path} (delete_on_error={self.delete_on_error})"
            )
        return wav_data
