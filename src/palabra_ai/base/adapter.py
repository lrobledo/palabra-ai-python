from __future__ import annotations

import abc
import asyncio
import io
import wave
from dataclasses import KW_ONLY, dataclass, field
from typing import TYPE_CHECKING

from palabra_ai.base.task import Task
from palabra_ai.base.task_event import TaskEvent
from palabra_ai.constant import CHUNK_SIZE

if TYPE_CHECKING:
    from palabra_ai.base.audio import AudioFrame
    from palabra_ai.config import Config


@dataclass
class Reader(Task):
    """Abstract PCM audio reader process."""

    _: KW_ONLY
    cfg: Config = field(default=None, init=False, repr=False)
    # sender: Optional["palabra_ai.task.sender.SenderSourceAudio"] = None  # noqa
    q: asyncio.Queue[AudioFrame] = field(default_factory=asyncio.Queue)
    # chunk_size: int = CHUNK_SIZE
    eof: TaskEvent = field(default_factory=TaskEvent, init=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.eof.set_owner(f"{self.__class__.__name__}.eof")

    @abc.abstractmethod
    async def read(self, size: int = CHUNK_SIZE) -> bytes | None:
        """Read PCM16 data. Must handle CancelledError."""
        ...


@dataclass
class Writer(Task):
    """Abstract PCM audio writer process."""

    _: KW_ONLY
    cfg: Config = field(default=None, init=False, repr=False)
    q: asyncio.Queue[AudioFrame | None] = field(default_factory=asyncio.Queue)
    _frames_processed: int = field(default=0, init=False)
    _process_task: asyncio.Task | None = field(default=None, init=False)

    async def boot(self):
        """Start the queue processing task"""
        if self._process_task is None:
            self._process_task = self.sub_tg.create_task(
                self._process_queue(), name=f"{self.name}:process_queue"
            )
        # Don't call super().boot() as it raises NotImplementedError

    async def _process_queue(self):
        """Process frames from the queue"""
        from palabra_ai.util.logger import debug, warning

        debug(f"{self.name}._process_queue() started")
        try:
            while not self.stopper or not self.eof:
                try:
                    frame: AudioFrame | None = await asyncio.wait_for(
                        self.q.get(), timeout=0.1
                    )

                    if frame is None:
                        debug(f"{self.name}: received None frame, stopping")
                        +self.eof  # noqa
                        break

                    self._frames_processed += 1
                    await self._write_frame(frame)
                    self.q.task_done()

                except TimeoutError:
                    continue
                except asyncio.CancelledError:
                    warning(f"{self.name}: queue processing cancelled")
                    raise

        finally:
            debug(f"{self.name}: processed {self._frames_processed} frames total")
            await self._finalize()

    @abc.abstractmethod
    async def _write_frame(self, frame: AudioFrame):
        """Write a single frame. Override in subclasses."""
        ...

    async def _finalize(self):
        """Finalize writing. Override in subclasses if needed."""
        pass

    async def exit(self):
        """Ensure queue is empty and finalize before exit"""
        # Signal end of stream
        await self.q.put(None)

        # Wait for processing to complete
        if self._process_task:
            try:
                await self._process_task
            except asyncio.CancelledError:
                pass


@dataclass
class BufferedWriter(Writer):
    """Writer that buffers audio frames before writing."""

    _: KW_ONLY
    buffer: io.BytesIO = field(default_factory=io.BytesIO, init=False)
    drop_empty_frames: bool = field(default=False)
    _frame_sample: AudioFrame | None = field(default=None, init=False)

    async def _write_frame(self, frame: AudioFrame):
        """Write frame to buffer"""
        frame_bytes = frame.data.tobytes()

        if self.drop_empty_frames and all(byte == 0 for byte in frame_bytes):
            return

        self.buffer.write(frame_bytes)

        if self._frame_sample is None:
            self._frame_sample = frame

    def to_wav_bytes(self) -> bytes:
        """Convert buffer to WAV format"""
        if self._frame_sample is None:
            from palabra_ai.util.logger import error

            error("No frame sample available for WAV conversion")
            return b""

        with io.BytesIO() as wav_file:
            with wave.open(wav_file, "wb") as wav:
                wav.setnchannels(self._frame_sample.num_channels)
                wav.setframerate(self._frame_sample.sample_rate)
                wav.setsampwidth(2)
                wav.writeframes(self.buffer.getvalue())
            return wav_file.getvalue()

    async def _finalize(self):
        """Convert buffer to WAV and write to destination"""
        await self._write_buffer()

    @abc.abstractmethod
    async def _write_buffer(self):
        """Write the buffered data. Override in subclasses."""
        ...
