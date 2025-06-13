from __future__ import annotations

import asyncio
import builtins
from collections.abc import Callable
from dataclasses import KW_ONLY, dataclass, field

from loguru import logger

from palabra_ai.base.message import TranscriptionMessage
from palabra_ai.base.task import Task
from palabra_ai.config import SourceLang, TargetLang
from palabra_ai.task.realtime import Realtime


@dataclass
class Transcription(Task):
    """Processes transcriptions and calls configured callbacks."""

    rt: Realtime
    source: SourceLang
    targets: list[TargetLang]
    _: KW_ONLY
    suppress_callback_errors: bool = True
    _webrtc_queue: asyncio.Queue | None = field(default=None, init=False)
    _callbacks: dict[str, Callable] = field(default_factory=dict, init=False)

    def __post_init__(self):
        # Collect callbacks by language
        if self.source._on_transcription:
            self._callbacks[self.source.lang.bcp47] = self.source._on_transcription

        for target in self.targets:
            if target._on_transcription:
                self._callbacks[target.lang.bcp47] = target._on_transcription

    async def run(self):
        if not self._callbacks:
            logger.debug("No transcription callbacks configured")
            +self.ready  # noqa
            return

        await self.rt.ready

        # Subscribe to webrtc messages
        self._webrtc_queue = self.rt.c.room.out_foq.subscribe(
            str(builtins.id(self)), maxsize=0
        )

        logger.debug(
            f"Transcription processor started for languages: {list(self._callbacks.keys())}"
        )
        +self.ready  # noqa

        try:
            while not self.stopper:
                try:
                    packet = await asyncio.wait_for(
                        self._webrtc_queue.get(), timeout=0.1
                    )
                except TimeoutError:
                    continue

                self._webrtc_queue.task_done()

                # Process message
                await self._process_message(packet)

        except asyncio.CancelledError:
            logger.debug("Transcription processor cancelled")
            raise

    async def _process_message(self, msg):
        """Process a single message and call appropriate callbacks."""
        try:
            if not isinstance(msg, TranscriptionMessage):
                return

            callback = self._callbacks.get(msg.language.bcp47)
            if not callback:
                logger.debug(
                    f"No callback configured for language: {msg.language.bcp47}"
                )
                return

            # Call the callback
            await self._call_callback(callback, msg)

        except Exception as e:
            logger.error(f"Error processing transcription message: {e}")

    async def _call_callback(self, callback: Callable, data: TranscriptionMessage):
        """Call a callback, handling both sync and async callbacks."""
        try:
            if asyncio.iscoroutinefunction(callback):
                asyncio.create_task(callback(data))
                # await callback(data)
            else:
                # Run sync callback in executor to not block
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, callback, data)

        except Exception as e:
            if self.suppress_callback_errors:
                logger.error(f"Error in transcription callback: {e}")
            else:
                raise
