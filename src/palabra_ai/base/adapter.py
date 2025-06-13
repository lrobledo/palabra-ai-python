from __future__ import annotations

import abc
import asyncio
from dataclasses import KW_ONLY, dataclass, field

from palabra_ai.base.task import Task, TaskEvent
from palabra_ai.config import CHUNK_SIZE, SLEEP_INTERVAL_DEFAULT


@dataclass
class Reader(Task):
    """Abstract PCM audio reader process."""

    _: KW_ONLY
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
        while not self.stopper and not self.eof:
            await asyncio.sleep(seconds)


@dataclass
class Writer(Task):
    """Abstract PCM audio writer process."""

    @abc.abstractmethod
    def get_queue(self) -> asyncio.Queue:
        """Get queue for audio frames."""
        ...

    @abc.abstractmethod
    async def finalize(self) -> bytes | None:
        """Finalize writing and save/flush buffers. Must handle CancelledError."""
        ...

    @abc.abstractmethod
    async def cancel(self) -> None:
        """Cancel writing and cleanup resources. Must handle CancelledError."""
        ...
