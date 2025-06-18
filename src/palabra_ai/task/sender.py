from __future__ import annotations

import asyncio
from dataclasses import KW_ONLY, dataclass, field
from typing import TYPE_CHECKING, Any

from loguru import logger

from palabra_ai.base.adapter import Reader
from palabra_ai.base.task import Task
from palabra_ai.config import (
    AUDIO_PROGRESS_LOG_INTERVAL,
    SAFE_PUBLICATION_END_DELAY,
    Config,
)
from palabra_ai.internal.webrtc import AudioTrackSettings
from palabra_ai.task.realtime import Realtime
from palabra_ai.task.receiver import ReceiverTranslatedAudio
from palabra_ai.util.logger import debug

if TYPE_CHECKING:
    from palabra_ai.task.manager import Manager


BYTES_PER_SAMPLE = 2  # PCM16 = 2 bytes per sample


@dataclass
class SenderSourceAudio(Task):
    cfg: Config
    rt: Realtime
    reader: Reader
    translation_settings: dict[str, Any]
    track_settings: AudioTrackSettings
    manager: Manager
    audio_receiver: ReceiverTranslatedAudio
    _: KW_ONLY
    _track: Any = field(default=None, init=False)
    _is_eof: bool = field(default=False, init=False)

    async def boot(self):
        await self.rt.ready

        self._track = await self.rt.c.new_translated_publication(
            self.translation_settings, self.track_settings
        )
        self.reader.sender = self
        await self.audio_receiver.ready

    async def do(self):
        while not self.stopper and not self.reader.eof:
            chunk = await self.reader.read()

            if chunk is None:
                debug(f"T{self.name}: Audio EOF reached")
                +self.stopper  # noqa

            if not chunk:
                continue

            await self._track.push(chunk)

    async def exit(self):
        if self._track:
            await asyncio.sleep(SAFE_PUBLICATION_END_DELAY)
            await asyncio.wait_for(self._track.close(), timeout=5)

    async def _stream_loop(self):
        pcm_buffer = bytearray()
        total_sent = 0

        logger.debug("Starting audio streaming loop...")

        while not self.stopper:
            chunk = await self.reader.read()

            if chunk is None:
                self._is_eof = True
                logger.debug("Audio EOF reached")
                break

            if not chunk:
                continue

            pcm_buffer.extend(chunk)
            plan_chunk_size = self.track_settings.sample_rate * BYTES_PER_SAMPLE

            while len(pcm_buffer) >= plan_chunk_size:
                send_chunk = pcm_buffer[:plan_chunk_size]
                pcm_buffer = pcm_buffer[plan_chunk_size:]
                fact_chunk_size = len(send_chunk)

                logger.debug(f"Pushing {fact_chunk_size} bytes to publication")
                await self._track.push(bytes(send_chunk))
                total_sent += fact_chunk_size
                self.manager.update_bytes_sent(fact_chunk_size)

                if total_sent % AUDIO_PROGRESS_LOG_INTERVAL < plan_chunk_size:
                    logger.debug(f"Sent {total_sent} bytes")

        if pcm_buffer and not self.stopper:
            fact_buffer_size = len(pcm_buffer)
            logger.debug(f"Pushing final {fact_buffer_size} bytes to publication")
            await self._track.push(bytes(pcm_buffer))
            total_sent += fact_buffer_size
            self.manager.update_bytes_sent(fact_buffer_size)

        debug(f"Audio streaming complete, sent {total_sent} bytes total")
