from __future__ import annotations

import asyncio
from dataclasses import KW_ONLY, dataclass, field

from loguru import logger

from palabra_ai.base.adapter import Writer
from palabra_ai.base.task import Task
from palabra_ai.config import SLEEP_INTERVAL_BUFFER_CHECK, Config
from palabra_ai.internal.buffer import AudioBufferWriter
from palabra_ai.util.frame_counter import FrameCounter


@dataclass
class Buffer(Task):
    cfg: Config
    writer: Writer
    _: KW_ONLY
    frame_counter: FrameCounter = field(default_factory=FrameCounter, init=False)
    _buffer_writer: AudioBufferWriter | None = field(default=None, init=False)

    async def run(self):
        await self.writer.ready

        self._buffer_writer = self.writer._buffer_writer
        if self._buffer_writer._task and not self._buffer_writer._task.done():
            logger.debug("AudioBufferWriter is running correctly")
        else:
            logger.error("AudioBufferWriter is NOT running!")

        +self.ready  # noqa

        while not self.stopper:
            await asyncio.sleep(SLEEP_INTERVAL_BUFFER_CHECK)
            if self.stopper:
                break
            frames, bytes_count = await self.frame_counter.get_stats()
            logger.debug(f"Buffer state: frames={frames}, bytes={bytes_count}")
