from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from palabra_ai.task.manager import Manager


class FrameCounter:
    """Thread-safe frame counter."""

    def __init__(self):
        self._count = 0
        self._bytes = 0
        self._lock = asyncio.Lock()

    async def add_frame(self, frame_bytes: int):
        try:
            async with self._lock:
                self._count += 1
                self._bytes += frame_bytes
        except asyncio.CancelledError:
            logger.warning("FrameCounter add_frame cancelled")
            raise

    async def get_stats(self) -> tuple[int, int]:
        try:
            async with self._lock:
                return self._count, self._bytes
        except asyncio.CancelledError:
            logger.warning("FrameCounter get_stats cancelled")
            raise


class FrameCountingQueue:
    """Wrapper queue that counts frames."""

    def __init__(
        self,
        target_queue: asyncio.Queue,
        frame_counter: FrameCounter,
        manager: Manager,
    ):
        self.target_queue = target_queue
        self.frame_counter = frame_counter
        self.manager = manager

    async def put(self, item):
        """Put item and count it."""
        try:
            await self.target_queue.put(item)
            if item is not None:
                frame_bytes = len(item.data.tobytes())
                await self.frame_counter.add_frame(frame_bytes)
                self.manager.update_bytes_received(frame_bytes)
        except asyncio.CancelledError:
            logger.warning("FrameCountingQueue put cancelled")
            raise

    def qsize(self):
        return self.target_queue.qsize()

    def task_done(self):
        return self.target_queue.task_done()
