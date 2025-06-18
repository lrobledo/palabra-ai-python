from __future__ import annotations

import asyncio
from dataclasses import KW_ONLY, dataclass, field
from typing import TYPE_CHECKING, Any

from palabra_ai.base.adapter import Reader, Writer
from palabra_ai.base.task import Task, TaskEvent
from palabra_ai.config import (
    EOF_DRAIN_TIMEOUT,
    SLEEP_INTERVAL_DEFAULT,
    TRACK_RETRY_DELAY,
    TRACK_RETRY_MAX_ATTEMPTS,
    Config,
)
from palabra_ai.task.realtime import Realtime
from palabra_ai.util.logger import debug, info, warning

if TYPE_CHECKING:
    from palabra_ai.task.manager import Manager


@dataclass
class ReceiverTranslatedAudio(Task):
    cfg: Config
    writer: Writer
    rt: Realtime
    manager: Manager
    target_language: str
    reader: Reader
    writer_stopper: TaskEvent
    _: KW_ONLY
    _track: Any = field(default=None, init=False)

    async def run(self):
        await self.rt.ready
        await self.reader.ready
        await self.writer.ready
        debug("Waiting for translation track...")

        await self._get_translation_track()
        +self.ready  # noqa

        try:
            await self._listen_until_stopped()
            await self._drain_remaining_data()
        except asyncio.CancelledError:
            warning("ReceiverTranslatedAudio cancelled during operation")
            raise
        finally:
            await self._cleanup()

    async def _get_translation_track(self):
        """Get translation track with retries."""
        for i in range(TRACK_RETRY_MAX_ATTEMPTS):
            if self.stopper:
                debug("ReceiverTranslatedAudio stopped before getting track")
                return

            # try:
            for i in [1]:
                debug(
                    f"Attempt {i + 1}/{TRACK_RETRY_MAX_ATTEMPTS} to get translation tracks..."
                )
                tracks = await self.rt.c.get_translation_tracks(
                    langs=[self.target_language]  # TODO: know more about this
                )
                debug(f"Got tracks response: {list(tracks.keys())}")

                if self.target_language in tracks:
                    self._track = tracks[self.target_language]
                    debug(
                        f"Found track for {self.target_language}, starting listening..."
                    )
                    self._track.start_listening(self.writer.q)
                    info(f"Started receiving audio for {self.target_language}")
                    return

                debug(f"Track for {self.target_language} not found yet")
            # except Exception as e:
            #     error(f"Error getting tracks: {e}")

            await asyncio.sleep(TRACK_RETRY_DELAY)

        raise TimeoutError(
            f"Track for {self.target_language} not available after {TRACK_RETRY_MAX_ATTEMPTS}s"
        )

    async def _listen_until_stopped(self):
        """Listen for audio until stopped."""
        try:
            while not self.stopper:
                await asyncio.sleep(SLEEP_INTERVAL_DEFAULT)
        except asyncio.CancelledError:
            debug("ReceiverTranslatedAudio received stopper signal, cleaning up...")

    async def _drain_remaining_data(self):
        """Wait for remaining data to be processed."""
        debug(f"Waiting {EOF_DRAIN_TIMEOUT}s for remaining data...")

        drain_start = asyncio.get_event_loop().time()
        last_queue_size = -1

        while asyncio.get_event_loop().time() - drain_start < EOF_DRAIN_TIMEOUT:
            current_queue_size = self.writer.q.qsize() if self.writer.q else 0

            if current_queue_size != last_queue_size:
                debug(f"Queue size: {current_queue_size} items")
                last_queue_size = current_queue_size

            if current_queue_size == 0:
                await asyncio.sleep(0.5)
                if self.writer.q and self.writer.q.qsize() == 0:
                    debug("Queue empty, finishing drain early")
                    break

            await asyncio.sleep(0.1)

    async def _cleanup(self):
        debug("Cleaning up ReceiverTranslatedAudio...")
        if self._track:
            await self._track.stop_listening()
            self._track = None
        self.writer.q.put_nowait(None)
        +self.writer_stopper  # noqa
