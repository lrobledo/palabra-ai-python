from __future__ import annotations

import asyncio
import time
from dataclasses import KW_ONLY, dataclass, field
from typing import Any

from loguru import logger

from palabra_ai.base.enum import Channel, Direction
from palabra_ai.base.task import Task
from palabra_ai.config import SLEEP_INTERVAL_LONG, Config
from palabra_ai.internal.realtime import PalabraRTClient
from palabra_ai.util.fanout_queue import FanoutQueue
from palabra_ai.util.logger import debug, warning


@dataclass
class RtMsg:
    ch: Channel  # "ws" or "webrtc"
    dir: Direction
    msg: Any
    ts: float = field(default_factory=time.time)


@dataclass
class Realtime(Task):
    cfg: Config
    credentials: Any
    _: KW_ONLY
    c: PalabraRTClient | None = field(default=None, init=False)
    in_foq: FanoutQueue = field(default_factory=FanoutQueue, init=False)
    out_foq: FanoutQueue = field(default_factory=FanoutQueue, init=False)
    ws_in_foq: FanoutQueue = field(default_factory=FanoutQueue, init=False)
    ws_out_foq: FanoutQueue = field(default_factory=FanoutQueue, init=False)
    webrtc_out_foq: FanoutQueue = field(default_factory=FanoutQueue, init=False)

    async def _reroute(
        self,
        ch: Channel,
        dir: Direction,
        from_q: asyncio.Queue,
        to_qs: list[FanoutQueue],
    ):
        while not self.stopper:
            try:
                msg = await asyncio.wait_for(from_q.get(), timeout=SLEEP_INTERVAL_LONG)
                for to_q in to_qs:
                    await to_q.publish(RtMsg(ch, dir, msg))
                from_q.task_done()
            except TimeoutError:
                continue

    def _reroute_ws_in(self):
        ws_in_q = self.c.wsc.ws_raw_in_foq.subscribe("rtc_task", maxsize=0)
        self._tg.create_task(
            self._reroute(
                Channel.WS, Direction.IN, ws_in_q, [self.in_foq, self.ws_in_foq]
            )
        )

    def _reroute_ws_out(self):
        ws_out_q = self.c.wsc.ws_out_foq.subscribe("rtc_task", maxsize=0)
        self._tg.create_task(
            self._reroute(
                Channel.WS, Direction.OUT, ws_out_q, [self.out_foq, self.ws_out_foq]
            )
        )

    def _reroute_webrtc_out(self):
        webrtc_out_q = self.c.room.out_foq.subscribe("rtc_task", maxsize=0)
        self._tg.create_task(
            self._reroute(
                Channel.WEBRTC,
                Direction.OUT,
                webrtc_out_q,
                [self.out_foq, self.webrtc_out_foq],
            )
        )

    async def run(self):
        debug("Creating PalabraRTCClient client...")
        self.c = PalabraRTClient(
            self.credentials.publisher[0],
            self.credentials.control_url,
            self.credentials.stream_url,
        )
        self._reroute_ws_in()
        self._reroute_ws_out()
        self._reroute_webrtc_out()

        try:
            await self.c.connect()
        except asyncio.CancelledError:
            warning("PalabraRTClient new_instance cancelled")
            await self.c.close()
            raise

        logger.debug("WebRTC client connected")
        +self.ready  # noqa

        try:
            while not self.stopper:
                await asyncio.sleep(SLEEP_INTERVAL_LONG)
        finally:
            await self.c.close()
