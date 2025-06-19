from __future__ import annotations

import asyncio
import io
from dataclasses import KW_ONLY, dataclass

from palabra_ai.base.adapter import Reader, Writer
from palabra_ai.config import SLEEP_INTERVAL_DEFAULT
from palabra_ai.internal.buffer import AudioBufferWriter
from palabra_ai.util.logger import debug, error, warning


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

    async def boot(self):
        debug(f"{self.name} contains {self._buffer_size} bytes")

    async def do(self):
        while not self.stopper and not self.eof:
            await asyncio.sleep(SLEEP_INTERVAL_DEFAULT)

    async def exit(self):
        debug(f"{self.name} exiting")
        if not self.eof:
            warning(f"{self.name} stopped without reaching EOF")

    async def read(self, size: int | None = None) -> bytes | None:
        await self.ready
        size = size or self.chunk_size

        self.buffer.seek(self._position)
        chunk = self.buffer.read(size)

        if not chunk:
            +self.eof  # noqa
            debug(f"EOF reached at position {self._position}")
            return None

        self._position = self.buffer.tell()
        return chunk


@dataclass
class BufferWriter(Writer):
    """Write PCM audio to io.BytesIO buffer."""

    buffer: io.BytesIO
    _: KW_ONLY

    def __post_init__(self):
        self._buffer_writer = AudioBufferWriter(queue=self.q)
        self._started = False

    async def boot(self):
        await self._buffer_writer.start()
        self._transfer_task = self.sub_tg.create_task(
            self._transfer_audio(), name="Buffer:transfer"
        )

    async def do(self):
        while not self.stopper and not self.eof:
            await asyncio.sleep(SLEEP_INTERVAL_DEFAULT)

    async def exit(self):
        try:
            await self._transfer_task
        except asyncio.CancelledError:
            pass
        debug("Finalizing BufferWriter...")

        wav_data = self._buffer_writer.to_wav_bytes()
        if wav_data:
            self.buffer.seek(0)
            self.buffer.truncate()
            self.buffer.write(wav_data)
            self.buffer.seek(0)
            debug(f"Generated {len(wav_data)} bytes of WAV data in buffer")
        else:
            warning("No WAV data generated")

        return wav_data

    async def _transfer_audio(self):
        try:
            while True:
                try:
                    audio_frame = await self._buffer_writer.queue.get()
                    if audio_frame is None:
                        +self.eof  # noqa
                        return

                    audio_bytes = audio_frame.data.tobytes()
                    self.buffer.write(audio_bytes)

                except asyncio.CancelledError:
                    warning("BufferWriter transfer cancelled")
                    raise
                except Exception as e:
                    error(f"Transfer error: {e}")
        except asyncio.CancelledError:
            warning("BufferWriter transfer loop cancelled")
            raise


class PipeWrapper:
    """Simple wrapper to make pipe work like a buffer"""

    def __init__(self, pipe):
        self.pipe = pipe
        self._buffer = b""
        self._pos = 0

    def read(self, size=-1):
        if size == -1:
            # Read all remaining
            data = self._buffer[self._pos :] + self.pipe.read()
            self._pos = len(self._buffer) + len(data) - len(self._buffer[self._pos :])
            self._buffer += data[len(self._buffer[self._pos :]) :]
            return data

        # Read specific size
        while len(self._buffer) - self._pos < size:
            chunk = self.pipe.read(size - (len(self._buffer) - self._pos))
            if not chunk:
                break
            self._buffer += chunk

        data = self._buffer[self._pos : self._pos + size]
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
