import time
from asyncio import CancelledError
from asyncio import sleep
from asyncio import wait_for
from dataclasses import dataclass
from dataclasses import field
from dataclasses import KW_ONLY
from functools import cached_property
from functools import partial
from typing import Any
from typing import TYPE_CHECKING


from palabra_ai.base.audio import AudioFrame
from palabra_ai.base.message import CurrentTaskMessage
from palabra_ai.base.message import GetTaskMessage
from palabra_ai.base.message import SetTaskMessage
from palabra_ai.constant import BOOT_TIMEOUT
from palabra_ai.constant import SHUTDOWN_TIMEOUT
from palabra_ai.constant import SLEEP_INTERVAL_LONG
from palabra_ai.constant import SLEEP_INTERVAL_MEDIUM
from palabra_ai.constant import SLEEP_INTERVAL_SHORT
from palabra_ai.constant import TRACK_RETRY_MAX_ATTEMPTS
from palabra_ai.task.io.base import Io



import asyncio
import uuid
from dataclasses import dataclass

import numpy as np
from livekit import rtc

from palabra_ai.base.enum import Channel
from palabra_ai.base.enum import Direction
from palabra_ai.base.message import Dbg
from palabra_ai.base.message import Message
from palabra_ai.base.task import Task
from palabra_ai.util.aio import boot
from palabra_ai.util.aio import shutdown
from palabra_ai.util.fanout_queue import FanoutQueue
from palabra_ai.util.logger import debug, error
from palabra_ai.util.logger import info
from palabra_ai.util.orjson import to_json

PALABRA_PEER_PREFIX = "palabra_translator_"
PALABRA_TRACK_PREFIX = "translation_"

if TYPE_CHECKING:
    from palabra_ai.lang import Language



@dataclass
class WebrtcIo(Io):
    _: KW_ONLY
    in_track_name: str | None = None
    track_source: rtc.TrackSource = rtc.TrackSource.SOURCE_MICROPHONE
    in_track_options: rtc.TrackPublishOptions = field(default_factory=partial(rtc.TrackPublishOptions, dtx=False, red=False))
    in_audio_source: rtc.AudioSource | None = None
    room: rtc.Room | None = None
    room_options: rtc.RoomOptions = field(default_factory=rtc.RoomOptions)
    loop: asyncio.AbstractEventLoop | None = None
    out_tracks: dict[str, rtc.RemoteAudioTrack] = field(default_factory=dict, init=False)
    out_track_publications: dict[str,rtc.RemoteTrackPublication] = field(default_factory=dict, init=False)
    in_track: rtc.LocalAudioTrack | None = None
    peer: rtc.RemoteParticipant | None = None

    def __post_init__(self):
        self.room = rtc.Room()

    async def peer_appears(self) -> rtc.RemoteParticipant:
        self.dbg(f"Waiting for Palabra peer to appear...")
        name = PALABRA_PEER_PREFIX.lower()
        try:
            while True:
                for peer in self.room.remote_participants.values():
                    if str(peer.identity).lower().startswith(name):
                        self.dbg(f"Found Palabra peer: {peer.identity}")
                        return peer
                await asyncio.sleep(SLEEP_INTERVAL_SHORT)
        except (TimeoutError, CancelledError):
            self.dbg(f"Didn't wait Palabra peer {name!r} to appear")
            raise

    async def track_appears(self, lang: "Language") -> rtc.RemoteTrackPublication:
        self.dbg(f"Waiting for translation track for {lang!r} to appear...")
        name = f"{PALABRA_TRACK_PREFIX}{lang.code}".lower()
        try:
            while True:
                for tpub in self.peer.track_publications.values():
                    if all(
                            [
                                str(tpub.name).lower().startswith(name),
                                tpub.kind == rtc.TrackKind.KIND_AUDIO,
                                tpub.track is not None,
                            ]
                    ):
                        self.dbg(f"Found translation track: {tpub.name}")
                        return tpub
                await asyncio.sleep(SLEEP_INTERVAL_SHORT)
        except (TimeoutError, CancelledError):
            self.dbg(f"Didn't wait track {name!r} to appear")
            raise

    async def out_audio(self, lang: "Language"):
        self.dbg(f"Starting audio stream for {lang!r}...")
        stream = rtc.AudioStream(self.out_tracks[lang.code])
        try:
            async for frame_ev in stream:
                frame_ev: rtc.AudioFrameEvent
                self.writer.q.put_nowait(AudioFrame.from_rtc(frame_ev.frame))
                await asyncio.sleep(0)
                if self.stopper or self.eof:
                    self.dbg(f"Stopping audio stream for {lang!r} due to stopper")
                    return
        finally:
            self.dbg(f"Closing audio stream for {lang!r}...")
            self.writer.q.put_nowait(None)
            await shutdown(stream.aclose())
            self.dbg(f"Closed audio stream for {lang!r}")

    def on_data_received(self, data: rtc.DataPacket):
        dbg = Dbg(Channel.WEBRTC, Direction.OUT)
        self.dbg(f"Received packet: {data}"[:100])
        msg = Message.decode(data.data)
        msg._dbg = dbg
        self.out_msg_foq.publish(msg)

    async def push_in_msg(self, msg: Message):
        dbg = Dbg(Channel.WEBRTC, Direction.IN)
        msg._dbg = dbg
        self.dbg(f"Pushing message: {msg}")
        self.in_msg_foq.publish(msg)

    async def in_msg_sender(self):
        async with self.in_msg_foq.receiver(self, self.stopper) as msgs:
            async for msg in msgs:
                if msg is None or self.stopper:
                    self.dbg("stopping in_msg_sender due to None or stopper")
                    return
                await self.room.local_participant.publish_data(
                    to_json(msg), reliable=True
                )

    async def boot(self):
        await self.room.connect(
            self.credentials.webrtc_url,
            self.credentials.jwt_token,
            self.room_options
        )
        self.room.on("data_received", self.on_data_received)
        lang = self.cfg.targets[0].lang # TODO: many langs
        self.peer = await self.peer_appears()
        self.sub_tg.create_task(self.in_msg_sender(), name=f"Io:in_msg_sender")

        await self.set_task()

        self.in_track_name = self.in_track_name or f"{uuid.uuid4()}_{lang.code}"
        # noinspection PyTypeChecker
        self.in_track_options.source = self.track_source
        self.in_audio_source = rtc.AudioSource(self.cfg.mode.sample_rate, self.cfg.mode.num_channels)
        self.in_track = rtc.LocalAudioTrack.create_audio_track(
            self.in_track_name, self.in_audio_source
        )
        await self.room.local_participant.publish_track(
            self.in_track, self.in_track_options
        )

        pub = await self.track_appears(lang)
        self.out_track_publications[lang.code] = pub
        self.out_tracks[lang.code] = pub.track
        self.sub_tg.create_task(self.out_audio(lang), name=f"Io:out_audio({lang!r})")


    async def push(self, audio_bytes: bytes) -> None:
        samples_per_channel = self.chunk_size
        total_samples = len(audio_bytes) // 2
        audio_frame = self.new_frame()
        audio_data = np.frombuffer(audio_frame.data, dtype=np.int16)

        for i in range(0, total_samples, samples_per_channel):
            if asyncio.get_running_loop().is_closed():
                break
            frame_chunk = audio_bytes[i * 2 : (i + samples_per_channel) * 2]

            if len(frame_chunk) < samples_per_channel * 2:
                padded_chunk = np.zeros(samples_per_channel, dtype=np.int16)
                frame_chunk = np.frombuffer(frame_chunk, dtype=np.int16)
                padded_chunk[: len(frame_chunk)] = frame_chunk
            else:
                padded_chunk = np.frombuffer(frame_chunk, dtype=np.int16)

            np.copyto(audio_data, padded_chunk)

            await self.in_audio_source.capture_frame(audio_frame)
            await asyncio.sleep(0.01)

    @cached_property
    def chunk_size(self) -> int:
        return int(self.cfg.mode.sample_rate * (self.cfg.mode.chunk_duration_ms / 1000))

    def new_frame(self) -> rtc.AudioFrame:
        return rtc.AudioFrame.create(
            self.cfg.mode.sample_rate, self.cfg.mode.num_channels, self.chunk_size
        )

    async def do(self):
        await self.reader.ready
        while not self.stopper and not self.eof:
            chunk = await self.reader.read()

            if chunk is None:
                debug(f"T{self.name}: Audio EOF reached")
                +self.eof  # noqa
                break

            if not chunk:
                continue

            # self.bytes_sent += len(chunk)
            await self.push(chunk)

    async def exit(self):
        if self.in_track:
            await shutdown(self.room.local_participant.unpublish_track(
                self.in_track.sid
            ))






