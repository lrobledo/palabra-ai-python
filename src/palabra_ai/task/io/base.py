import abc
import time
from asyncio import get_running_loop, sleep
from dataclasses import KW_ONLY, dataclass, field
from functools import cached_property
from typing import Callable
from typing import TYPE_CHECKING

import numpy as np

from palabra_ai.base.audio import AudioFrame
from palabra_ai.base.enum import Channel, Direction
from palabra_ai.base.message import (
    CurrentTaskMessage,
    Dbg,
    EndTaskMessage,
    GetTaskMessage,
    SetTaskMessage,
)
from palabra_ai.base.task import Task
from palabra_ai.constant import BOOT_TIMEOUT, SLEEP_INTERVAL_LONG
from palabra_ai.util.fanout_queue import FanoutQueue
from palabra_ai.util.logger import debug
from palabra_ai.util.orjson import to_json

if TYPE_CHECKING:
    from palabra_ai.base.adapter import Reader, Writer
    from palabra_ai.base.message import Message
    from palabra_ai.config import Config
    from palabra_ai.internal.rest import SessionCredentials


@dataclass
class Io(Task):
    cfg: "Config"
    credentials: "SessionCredentials"
    reader: "Reader"
    writer: "Writer"
    _: KW_ONLY
    in_msg_foq: FanoutQueue["Message"] = field(default_factory=FanoutQueue, init=False)
    out_msg_foq: FanoutQueue["Message"] = field(default_factory=FanoutQueue, init=False)
    _buffer_callback: Callable | None  = field(default=None, init=False)

    @property
    @abc.abstractmethod
    def channel(self) -> Channel:
        """Return the channel type for this IO."""
        ...

    @abc.abstractmethod
    async def send_frame(self, frame) -> None:
        """Send an audio frame through the transport."""
        ...

    @abc.abstractmethod
    async def send_message(self, msg_data: bytes) -> None:
        """Send a message through the transport."""
        ...

    async def push_in_msg(self, msg: "Message") -> None:
        """Push an incoming message with debug tracking."""
        dbg = Dbg(self.channel, Direction.IN)
        msg._dbg = dbg
        debug(f"Pushing message: {msg!r}")
        self.in_msg_foq.publish(msg)

    @cached_property
    def chunk_size(self) -> int:
        """Calculate chunk size from sample rate and duration."""
        return int(self.cfg.mode.sample_rate * (self.cfg.mode.chunk_duration_ms / 1000))

    @cached_property
    def reader_chunk_size(self) -> int:
        """Calculate reader chunk size in bytes."""
        return int(
            self.cfg.mode.sample_rate * (self.cfg.mode.chunk_duration_ms / 1000) * 2
        )

    async def in_msg_sender(self):
        """Send messages from the input queue through the transport."""
        async with self.in_msg_foq.receiver(self, self.stopper) as msgs:
            async for msg in msgs:
                if msg is None or self.stopper:
                    debug("stopping in_msg_sender due to None or stopper")
                    return
                raw = to_json(msg)
                debug(f"<- {raw[0:30]}")
                await self.send_message(raw)

    async def do(self):
        """Main processing loop - read audio chunks and push them."""
        await self.reader.ready
        while not self.stopper and not self.eof:
            chunk = await self.reader.read(self.reader_chunk_size)

            if chunk is None:
                debug(f"T{self.name}: Audio EOF reached")
                +self.eof  # noqa
                await self.push_in_msg(EndTaskMessage())
                break

            if not chunk:
                continue

            await self.push(chunk)
            await self.do_post_chunk()

    async def do_post_chunk(self):
        """Hook for subclasses to add post-chunk processing."""
        await sleep(self.cfg.mode.chunk_duration_ms / 1000)

    def new_frame(self) -> "AudioFrame":
        return AudioFrame.create(
            self.cfg.mode.sample_rate, self.cfg.mode.num_channels, self.chunk_size
        )

    async def push(self, audio_bytes: bytes) -> None:
        """Process and send audio chunks."""
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
            await self.send_frame(audio_frame)

    async def _exit(self):
        await self.writer.q.put(None)
        return await super()._exit()

    async def set_task(self):
        debug("Setting task configuration...")
        await sleep(SLEEP_INTERVAL_LONG)
        async with self.out_msg_foq.receiver(self, self.stopper) as msgs_out:
            await self.push_in_msg(SetTaskMessage.from_config(self.cfg))
            start_ts = time.time()
            await sleep(SLEEP_INTERVAL_LONG)
            while start_ts + BOOT_TIMEOUT > time.time():
                await self.push_in_msg(GetTaskMessage())
                msg = await anext(msgs_out)
                if isinstance(msg, CurrentTaskMessage):
                    debug(f"Received current task: {msg.data}")
                    return
                debug(f"Received unexpected message: {msg}")
                await sleep(SLEEP_INTERVAL_LONG)
        debug("Timeout waiting for task configuration")
        raise TimeoutError("Timeout waiting for task configuration")
