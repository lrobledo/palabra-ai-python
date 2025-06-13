from __future__ import annotations

import asyncio
import io
from dataclasses import KW_ONLY, dataclass, field

from loguru import logger

from palabra_ai.adapter._common import run_until_stopped
from palabra_ai.base.adapter import Reader, Writer
from palabra_ai.internal.buffer import AudioBufferWriter


@dataclass
class BufferReader(Reader):
    """Read PCM audio from io.BytesIO buffer."""

    buffer: io.BytesIO
    _: KW_ONLY

    def __post_init__(self):
        self._position = 0
        current_pos = self.buffer.tell()
        self.buffer.seek(0, io.SEEK_END)
        self._buffer_size = self.buffer.tell()
        self.buffer.seek(current_pos)

    async def run(self):
        logger.debug(f"Buffer contains {self._buffer_size} bytes")
        +self.ready  # noqa

        await self._benefit()

    async def read(self, size: int | None = None) -> bytes | None:
        await self.ready
        size = size or self.chunk_size

        self.buffer.seek(self._position)
        chunk = self.buffer.read(size)

        if not chunk:
            +self.eof  # noqa
            logger.debug(f"EOF reached at position {self._position}")
            return None

        self._position = self.buffer.tell()
        return chunk


@dataclass
class BufferWriter(Writer):
    """Write PCM audio to io.BytesIO buffer."""

    buffer: io.BytesIO

    _: KW_ONLY
    _buffer_writer: AudioBufferWriter = field(
        default_factory=AudioBufferWriter, init=False
    )
    _started: bool = field(default=False, init=False, repr=False)
    _transfer_task: asyncio.Task | None = field(default=None, init=False, repr=False)

    def get_queue(self) -> asyncio.Queue:
        return self._buffer_writer.queue

    async def run(self):
        try:
            await self._buffer_writer.start()
            self._started = True
            self._transfer_task = self._tg.create_task(self._transfer_audio())
            logger.debug("BufferWriter started")
            +self.ready  # noqa

            await run_until_stopped(self)

        except asyncio.CancelledError:
            logger.warning("BufferWriter run cancelled")
            raise
        finally:
            if self._transfer_task:
                self._transfer_task.cancel()
                try:
                    await self._transfer_task
                except asyncio.CancelledError:
                    pass
            await self.finalize()

    async def _transfer_audio(self):
        try:
            while True:
                try:
                    audio_frame = await self._buffer_writer.queue.get()
                    if audio_frame is None:
                        break

                    audio_bytes = audio_frame.data.tobytes()
                    self.buffer.write(audio_bytes)

                except asyncio.CancelledError:
                    logger.warning("BufferWriter transfer cancelled")
                    raise
                except Exception as e:
                    logger.error(f"Transfer error: {e}")
        except asyncio.CancelledError:
            logger.warning("BufferWriter transfer loop cancelled")
            raise

    async def finalize(self) -> bytes:
        logger.debug("Finalizing BufferWriter...")

        wav_data = self._buffer_writer.to_wav_bytes()
        if wav_data:
            self.buffer.seek(0)
            self.buffer.truncate()
            self.buffer.write(wav_data)
            self.buffer.seek(0)
            logger.debug(f"Generated {len(wav_data)} bytes of WAV data in buffer")
        else:
            logger.warning("No WAV data generated")

        return wav_data

    async def cancel(self) -> None:
        logger.debug("BufferWriter cancelled")
        self.buffer.seek(0)
        self.buffer.truncate()


class PipeWrapper:
    """Simple wrapper to make pipe work like a buffer"""
    def __init__(self, pipe):
        self.pipe = pipe
        self._buffer = b''
        self._pos = 0

    def read(self, size=-1):
        if size == -1:
            # Read all remaining
            data = self._buffer[self._pos:] + self.pipe.read()
            self._pos = len(self._buffer) + len(data) - len(self._buffer[self._pos:])
            self._buffer += data[len(self._buffer[self._pos:]):]
            return data

        # Read specific size
        while len(self._buffer) - self._pos < size:
            chunk = self.pipe.read(size - (len(self._buffer) - self._pos))
            if not chunk:
                break
            self._buffer += chunk

        data = self._buffer[self._pos:self._pos + size]
        self._pos += len(data)
        return data

    def tell(self):
        return self._pos

    def seek(self, pos, whence=0):
        if whence == 0:  # SEEK_SET
            self._pos = min(pos, len(self._buffer))
        elif whence == 1:  # SEEK_CUR
            self._pos = min(self._pos + pos, len(self._buffer))
        elif whence == 2:  # SEEK_END
            self._pos = len(self._buffer) + pos
        return self._pos
