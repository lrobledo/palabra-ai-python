import asyncio
import json
from asyncio import get_running_loop
from asyncio import sleep
from dataclasses import dataclass
from dataclasses import field
from dataclasses import KW_ONLY
from functools import cached_property
from typing import Optional

import numpy as np

from palabra_ai.base.audio import AudioFrame
from palabra_ai.base.enum import Channel
from palabra_ai.base.enum import Direction
from palabra_ai.base.message import Dbg
from palabra_ai.task.io.base import Io
from websockets.asyncio.client import connect as ws_connect, ClientConnection

from palabra_ai.util.logger import debug
from palabra_ai.util.orjson import to_json


@dataclass
class WsIo(Io):
    _: KW_ONLY
    ws: Optional[ClientConnection] = field(default=None, init=False)
    _ws_cm: Optional[object] = field(default=None, init=False)
    reader_chunk_size: int = field(default=None, init=False)

    def __post_init__(self):
        self.reader_chunk_size = int(self.cfg.mode.sample_rate * (self.cfg.mode.chunk_duration_ms / 1000) * 2)


    @property
    def dsn(self) -> str:
        return f"{self.credentials.ws_url}?token={self.credentials.jwt_token}"



    async def push_in_msg(self, msg: "Message"):
        dbg = Dbg(Channel.WS, Direction.IN)
        msg._dbg = dbg
        self.dbg(f"Pushing message: {msg!r}")
        self.in_msg_foq.publish(msg)

    async def in_msg_sender(self):
        async with self.in_msg_foq.receiver(self, self.stopper) as msgs:
            async for msg in msgs:
                if msg is None or self.stopper:
                    self.dbg("stopping in_msg_sender due to None or stopper")
                    return
                raw = to_json(msg)
                self.dbg(f"<- {raw[0:30]}")
                await self.ws.send(raw)

    async def ws_receiver(self):
        from palabra_ai.base.message import Message
        async for raw_msg in self.ws:
            if self.stopper or raw_msg is None:
                self.dbg("Stopping ws_receiver due to stopper or None message")
                return
            self.dbg(f"-> {raw_msg[:30]}")
            audio_frame = AudioFrame.from_ws(raw_msg)
            if audio_frame is not None:
                self.dbg(f"Received audio frame: {audio_frame!r}")
                self.reader.q.put_nowait(audio_frame)
            else:
                msg = Message.decode(raw_msg)
                msg._dbg = Dbg(Channel.WS, Direction.OUT)
                self.out_msg_foq.publish(msg)


    async def boot(self):
        """Start WebSocket connection"""
        # Create context manager and enter it
        self._ws_cm = ws_connect(self.dsn)
        self.ws = await self._ws_cm.__aenter__()

        # Verify connection is ready
        await self.ws.ping()
        self.sub_tg.create_task(self.ws_receiver(), name="WsIo:receiver")
        self.sub_tg.create_task(self.in_msg_sender(), name=f"WsIo:in_msg_sender")
        await self.set_task()


    async def do(self):
        await self.reader.ready
        while not self.stopper and not self.eof:
            chunk = await self.reader.read(self.reader_chunk_size)

            if chunk is None:
                self.dbg(f"T{self.name}: Audio EOF reached")
                +self.eof  # noqa
                break

            if not chunk:
                continue

            # self.bytes_sent += len(chunk)
            await self.push(chunk)
            await sleep(self.cfg.mode.chunk_duration_ms / 1000)

    async def exit(self):
        """Clean up WebSocket connection"""
        if self._ws_cm and self.ws:
            await self._ws_cm.__aexit__(None, None, None)
        self.ws = None

    async def push(self, audio_bytes: bytes) -> None:
        samples_per_channel = self.chunk_size
        total_samples = len(audio_bytes) // 2
        audio_frame = self.new_frame()
        audio_data = np.frombuffer(audio_frame.data, dtype=np.int16)

        for i in range(0, total_samples, samples_per_channel):
            if get_running_loop().is_closed():
                break
            frame_chunk = audio_bytes[i * 2 : (i + samples_per_channel) * 2]

            if len(frame_chunk) < samples_per_channel * 2:
                padded_chunk = np.zeros(samples_per_channel, dtype=np.int16)
                frame_chunk = np.frombuffer(frame_chunk, dtype=np.int16)
                padded_chunk[: len(frame_chunk)] = frame_chunk
            else:
                padded_chunk = np.frombuffer(frame_chunk, dtype=np.int16)

            np.copyto(audio_data, padded_chunk)
            self.dbg(f"Sending audio frame: {audio_frame!r}")
            raw = audio_frame.to_ws()
            self.dbg(f"<- {raw[0:30]}")
            await self.ws.send(raw)


    @cached_property
    def chunk_size(self) -> int:
        return int(self.cfg.mode.sample_rate * (self.cfg.mode.chunk_duration_ms / 1000))

    def new_frame(self) -> AudioFrame:
        return AudioFrame.create(
            self.cfg.mode.sample_rate, self.cfg.mode.num_channels, self.chunk_size
        )