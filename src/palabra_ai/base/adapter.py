from __future__ import annotations

import abc
import asyncio
from dataclasses import KW_ONLY, dataclass, field
from typing import Optional

from livekit.rtc import AudioFrame

from palabra_ai.base.task import Task, TaskEvent
from palabra_ai.config import CHUNK_SIZE, SLEEP_INTERVAL_DEFAULT
from palabra_ai.exc import ConfigurationError
from palabra_ai.util import logger


@dataclass
class Reader(Task):
    """Abstract PCM audio reader process."""

    _: KW_ONLY
    sender: Optional["palabra_ai.task.sender.SenderSourceAudio"] = None  # noqa
    q: asyncio.Queue[bytes] = field(default_factory=asyncio.Queue)
    chunk_size: int = CHUNK_SIZE
    eof: TaskEvent = field(default_factory=TaskEvent, init=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.eof.set_owner(f"{self.__class__.__name__}.eof")

    @abc.abstractmethod
    async def read(self, size: int = CHUNK_SIZE) -> bytes | None:
        """Read PCM16 data. Must handle CancelledError."""
        ...

    async def _benefit(self, seconds: float = SLEEP_INTERVAL_DEFAULT):
        while not self.stopper or not self.eof:
            try:
                await asyncio.sleep(seconds)
            except asyncio.CancelledError:
                +self.stopper  # noqa
                +self.eof  # noqa
                logger.debug(f"{self.__class__.__name__}._benefit cancelled, stopping")
                raise


@dataclass
class Writer(Task):
    """Abstract PCM audio writer process."""

    _: KW_ONLY
    reader: Reader | None = field(default=None, init=False)
    q: asyncio.Queue[AudioFrame] = field(default_factory=asyncio.Queue)

    async def _exit(self):
        +self.reader.stopper  # noqa
        return await super()._exit()

    async def _boot(self):
        if not self.reader:
            raise ConfigurationError("Reader must be set before booting Writer")
        return await super()._boot()
