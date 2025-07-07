from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from dataclasses import KW_ONLY, dataclass, field
from functools import partial
from typing import Any
from typing import AsyncGenerator
from typing import AsyncIterator
from typing import Optional

from palabra_ai.base.message import Message
from palabra_ai.base.message import SetTaskMessage
from palabra_ai.base.message import TranscriptionMessage
from palabra_ai.base.enum import Channel, Direction
from palabra_ai.base.task import Task
from palabra_ai.config import Config
from palabra_ai.constant import BOOT_TIMEOUT
from palabra_ai.constant import SHUTDOWN_TIMEOUT, SLEEP_INTERVAL_LONG
from palabra_ai.internal.realtime import PalabraRTClient
from palabra_ai.internal.realtime import RemoteAudioTrack
from palabra_ai.internal.webrtc import AudioPublication
from palabra_ai.internal.webrtc import AudioTrackSettings
from palabra_ai.internal.webrtc import RoomClient, _PALABRA_TRANSLATOR_PARTICIPANT_IDENTITY_PREFIX, _PALABRA_TRANSLATOR_TRACK_NAME_PREFIX
from palabra_ai.internal.ws import Ws
from palabra_ai.util.capped_set import CappedSet
from palabra_ai.util.fanout_queue import FanoutQueue
from palabra_ai.util.logger import debug



@dataclass
class Realtime(Task):
    cfg: Config
    credentials: Any
    _: KW_ONLY
    # c: PalabraRTClient | None = field(default=None, init=False)
    in_foq: FanoutQueue = field(default_factory=FanoutQueue, init=False)
    out_foq: FanoutQueue = field(default_factory=FanoutQueue, init=False)
    jwt_token: str|None = field(default=None, init=False)
    control_url: str|None = field(default=None, init=False)
    stream_url: str|None = field(default=None, init=False)
    ws: Ws | None = field(default=None, init=False)
    webrtc: RoomClient | None = field(default=None, init=False)
    _route_in_task: asyncio.Task | None = field(default=None, init=False)
    _route_ws_out_task: asyncio.Task | None = field(default=None, init=False)
    _route_webrtc_out_task: asyncio.Task | None = field(default=None, init=False)
    _dedup: CappedSet[str] = field(default_factory=partial(CappedSet, 100), init=False)

    def __post_init__(self):
        jwt_token = self.credentials.publisher[0]
        control_url = self.credentials.control_url
        stream_url = self.credentials.stream_url

        if not jwt_token or not control_url or not stream_url:
            raise ValueError("Missing JWT token, control URL, or stream URL")

        # Initialize WebSocket and Room clients
        self.ws = Ws(
            tg=self.sub_tg,
            uri=control_url,
            token=jwt_token,
        )
        self.webrtc = RoomClient(url=stream_url, token=jwt_token)

    async def _route_in(self):
        async with self.in_foq.receiver(self) as msgs_in:
            async for msg_in in msgs_in:
                self.ws.in_foq.publish(msg_in)

    def dedup_ok(self, msg: Message) -> bool:
        if not isinstance(msg, TranscriptionMessage):
            return True
        msg_dedup = msg.dedup
        if msg_dedup in self._dedup:
            return False
        self._dedup.add(msg_dedup)
        return True

    async def _route_ws_out(self):
        async with self.ws.out_foq.receiver(self) as msgs_ws_out:
            async for msg_ws_out in msgs_ws_out:
                if self.dedup_ok(msg_ws_out):
                    self.out_foq.publish(msg_ws_out)

    async def _route_webrtc_out(self):
        async with self.webrtc.out_foq.receiver(self) as msgs_webrtc_out:
            async for msg_webrtc_out in msgs_webrtc_out:
                if self.dedup_ok(msg_webrtc_out):
                    self.out_foq.publish(msg_webrtc_out)

    async def boot(self):
        # self.c = PalabraRTClient(
        #     self.sub_tg,
        #     self.credentials.publisher[0],
        #     self.credentials.control_url,
        #     self.credentials.stream_url,
        # )

        self._route_in_task = self.sub_tg.create_task(self._route_in(), name="Realtime:route_in")
        self._route_ws_out_task = self.sub_tg.create_task(self._route_ws_out(), name="Realtime:route_ws_out")
        self._route_webrtc_out_task = self.sub_tg.create_task(self._route_webrtc_out(), name="Realtime:route_webrtc_out")

        await self._connect()

    async def do(self):
        while not self.stopper:
            await asyncio.sleep(SLEEP_INTERVAL_LONG)

    async def exit(self):
        self.in_foq.publish(None)
        self.out_foq.publish(None)
        await asyncio.gather(
            asyncio.wait_for(self.ws.close(), timeout=SHUTDOWN_TIMEOUT),
            asyncio.wait_for(self.webrtc.close(), timeout=SHUTDOWN_TIMEOUT),
        )
        self._route_in_task.cancel()
        self._route_ws_out_task.cancel()
        self._route_webrtc_out_task.cancel()

    async def _connect(self):
        try:
            await asyncio.wait_for(asyncio.gather(
                self.ws.connect(),
                self.webrtc.connect()
            ), timeout=BOOT_TIMEOUT)
        except asyncio.CancelledError:
            debug(f"{self.name}._connect() cancelled")
            raise

    def send(self, msg: Message):
        return self.in_foq.publish(msg)

    @asynccontextmanager
    async def receiver(self, subscriber_id: Optional[str] = None, timeout: Optional[float] = None) -> AsyncIterator[
        AsyncGenerator[Message, None]]:
        async with self.out_foq.receiver(subscriber_id, timeout) as msg_gen:
            yield msg_gen







    async def new_translated_publication(
            self,
            translation_settings: dict[str, Any],
            track_settings: AudioTrackSettings | None = None,
    ) -> AudioPublication:
        track_settings = track_settings or AudioTrackSettings()
        try:
            self.in_foq.publish(SetTaskMessage(data=self.cfg.to_dict()))
            return await self.webrtc.new_publication(track_settings)
        except asyncio.CancelledError:
            debug("PalabraRTClient new_translated_publication cancelled")
            raise

    async def get_translation_settings(
            self, timeout: int | None = None
    ) -> dict[str, Any]:

        async with self.out_foq.receiver(self) as msgs_out:
            self.in_foq.publish

        start = time.perf_counter()
        while True:
            try:
                debug("PalabraRTClient get_translation_settings sending request")
                await self.wsc.send({"message_type": "get_task", "data": {}})
            except asyncio.CancelledError:
                debug("PalabraRTClient get_translation_settings send cancelled")
                raise

            if timeout and time.perf_counter() - start > timeout:
                raise TimeoutError("Timeout waiting for translation cfg")

            try:
                message = await self.wsc.receive(1)
            except asyncio.CancelledError:
                debug("PalabraRTClient get_translation_settings receive cancelled")
                raise

            if message is None:
                try:
                    await asyncio.sleep(0)
                except asyncio.CancelledError:
                    debug("PalabraRTClient get_translation_settings sleep cancelled")
                    raise
                continue

            if message["message_type"] == "current_task":
                self.wsc.mark_received()
                return message["data"]

            await asyncio.sleep(0)

    async def get_translation_languages(self, timeout: int | None = None) -> list[str]:
        _get_trans_settings = self.get_translation_settings
        if timeout:
            _get_trans_settings = partial(_get_trans_settings, timeout=timeout)
        try:
            translation_settings = await _get_trans_settings()
        except asyncio.CancelledError:
            debug("PalabraRTClient get_translation_languages cancelled")
            raise
        return [
            translation["target_language"]
            for translation in translation_settings["pipeline"]["translations"]
        ]

    async def get_translation_tracks(
            self, langs: list[str] | None = None
    ) -> dict[str, RemoteAudioTrack]:
        response = {}
        try:
            langs = langs or await self.get_translation_languages()
            participant = await self.room.wait_for_participant_join(
                _PALABRA_TRANSLATOR_PARTICIPANT_IDENTITY_PREFIX
            )
            for lang in langs:
                publication = await self.room.wait_for_track_publish(
                    participant, _PALABRA_TRANSLATOR_TRACK_NAME_PREFIX + lang
                )
                response[lang] = RemoteAudioTrack(
                    self.tg, lang, participant, publication
                )
        except asyncio.CancelledError:
            debug("PalabraRTClient get_translation_tracks cancelled")
            raise
        return response
