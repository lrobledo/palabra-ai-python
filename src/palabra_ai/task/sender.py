from __future__ import annotations

import asyncio
from dataclasses import KW_ONLY, dataclass, field
from typing import TYPE_CHECKING, Any

from palabra_ai.base.adapter import Reader
from palabra_ai.base.task import Task
from palabra_ai.config import (
    SAFE_PUBLICATION_END_DELAY,
    TRACK_CLOSE_TIMEOUT,
    Config,
)
from palabra_ai.internal.webrtc import AudioTrackSettings
from palabra_ai.task.realtime import Realtime
from palabra_ai.util.logger import debug

if TYPE_CHECKING:
    pass


BYTES_PER_SAMPLE = 2  # PCM16 = 2 bytes per sample


@dataclass
class SenderSourceAudio(Task):
    cfg: Config
    rt: Realtime
    reader: Reader
    translation_settings: dict[str, Any]
    track_settings: AudioTrackSettings
    _: KW_ONLY
    _track: Any = field(default=None, init=False)
    bytes_sent: int = field(default=0, init=False)

    async def boot(self):
        await self.rt.ready

        self._track = await self.rt.c.new_translated_publication(
            self.translation_settings, self.track_settings
        )

    async def do(self):
        while not self.stopper and not self.eof:
            chunk = await self.reader.read()

            if chunk is None:
                debug(f"T{self.name}: Audio EOF reached")
                +self.eof  # noqa
                break

            if not chunk:
                continue

            await self._track.push(chunk)

    async def exit(self):
        if self._track:
            await asyncio.sleep(SAFE_PUBLICATION_END_DELAY)
            await asyncio.wait_for(self._track.close(), timeout=TRACK_CLOSE_TIMEOUT)
        +self.eof  # noqa
