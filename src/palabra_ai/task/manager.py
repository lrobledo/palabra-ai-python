from __future__ import annotations

import asyncio
from dataclasses import KW_ONLY, dataclass, field

from palabra_ai.base.adapter import Reader, Writer
from palabra_ai.base.task import Task, TaskEvent
from palabra_ai.config import (
    BOOT_TIMEOUT,
    SAFE_PUBLICATION_END_DELAY,
    SHUTDOWN_TIMEOUT,
    SINGLE_TARGET_SUPPORTED_COUNT,
    SLEEP_INTERVAL_DEFAULT,
    SLEEP_INTERVAL_LONG,
    Config,
)
from palabra_ai.exc import ConfigurationError
from palabra_ai.internal.rest import SessionCredentials
from palabra_ai.internal.webrtc import AudioTrackSettings
from palabra_ai.task.logger import Logger
from palabra_ai.task.monitor import RtMonitor
from palabra_ai.task.realtime import Realtime
from palabra_ai.task.receiver import ReceiverTranslatedAudio
from palabra_ai.task.sender import SenderSourceAudio
from palabra_ai.task.transcription import Transcription
from palabra_ai.util.logger import debug, info


@dataclass
class Manager(Task):
    """Manages the translation process and monitors progress."""

    cfg: Config
    credentials: SessionCredentials
    _: KW_ONLY
    reader: Reader = field(init=False)
    writer: Writer = field(init=False)
    track_settings: AudioTrackSettings = field(default_factory=AudioTrackSettings)
    rt: Realtime = field(init=False)
    sender: SenderSourceAudio = field(init=False)
    receiver: ReceiverTranslatedAudio = field(init=False)
    logger: Logger | None = field(init=False)
    rtmon: RtMonitor = field(init=False)
    transcription: Transcription = field(init=False)

    tasks: list[Task] = field(default_factory=list, init=False)

    _debug_mode: bool = field(default=True, init=False)
    _transcriptions_shown: set = field(default_factory=set, init=False)
    _state_stopper: TaskEvent = field(default_factory=TaskEvent, init=False)

    def __post_init__(self):
        if len(self.cfg.targets) != SINGLE_TARGET_SUPPORTED_COUNT:
            raise ConfigurationError("Only single target language supported")

        self.reader = self.cfg.source.reader
        if not isinstance(self.reader, Reader):
            raise ConfigurationError("src.reader must be Reader")

        target = self.cfg.targets[0]
        self.writer = target.writer
        if not isinstance(self.writer, Writer):
            raise ConfigurationError("target.writer must be Writer")

        if hasattr(self.writer, "set_track_settings"):
            self.writer.set_track_settings(self.track_settings)
        if hasattr(self.reader, "set_track_settings"):
            self.reader.set_track_settings(self.track_settings)

        self.rt = Realtime(self.cfg, self.credentials)
        if self.cfg.log_file:
            self.logger = Logger(self.cfg, self.rt)
            self.tasks.append(self.logger)

        self.transcription = Transcription(self.cfg, self.rt)

        self.receiver = ReceiverTranslatedAudio(
            self.cfg,
            self.writer,
            self.rt,
            target.lang.code,
        )

        self.sender = SenderSourceAudio(
            self.cfg,
            self.rt,
            self.reader,
            self.cfg.to_dict(),
            self.track_settings,
        )

        self.rtmon = RtMonitor(self.cfg, self.rt)

        self.tasks.extend(
            [
                self,
                self.rtmon,
                self.rt,
                self.reader,
                self.writer,
                self.receiver,
                self.sender,
                self.transcription,
            ]
        )

    def asyncio_tasks_states(self):
        states = {}
        for task in asyncio.all_tasks():
            if task.cancelled():
                v = "❌"
            elif task.done():
                v = "✅"
            else:
                v = "🏃"
            states[task.get_name()] = v
        return states

    @property
    def stat_palabra_tasks(self):
        return "\n".join(
            (
                "\nPalabra tasks:",
                "\n".join([str(t) for t in self.tasks]),
            )
        )

    @property
    def stat_asyncio_tasks(self):
        return "\n".join(
            (
                "\nAsyncio tasks:\n",
                " | ".join(
                    sorted([t.get_name() for t in asyncio.all_tasks()])
                )
            )
        )

    @property
    def stat(self):
        return f"{self.stat_palabra_tasks}\n{self.stat_asyncio_tasks}"

    async def tasks_state_monitor(self):
        last_state = ""
        i = 0
        while not self._state_stopper:
            new_state = self.stat_palabra_tasks
            if new_state != last_state or i % 30 == 0:
                debug(self.stat)
                last_state = new_state
            i += 1
            await asyncio.sleep(SLEEP_INTERVAL_DEFAULT)
        await asyncio.sleep(SLEEP_INTERVAL_LONG)
        debug(self.stat)

    async def start_tasks(self):
        debug(f"🔧 {self.name} run listening...")
        self.rtmon(self.sub_tg)
        self.rt(self.sub_tg)
        self.transcription(self.sub_tg)
        self.writer(self.sub_tg)
        self.receiver(self.sub_tg)
        self.sender(self.sub_tg)
        await self.rt.ready
        await self.rtmon.ready
        await self.writer.ready
        await self.receiver.ready
        await self.sender.ready
        await self.transcription.ready
        debug(f"🔧 {self.name} listening ready!")

        debug(f"🔧 {self.name} run reader...")
        self.reader(self.sub_tg)
        await self.reader.ready
        debug(f"🔧 {self.name} reader ready!")

    async def boot(self):
        debug(f"🔧 {self.name}...")

        if self.cfg.debug:
            self.root_tg.create_task(
                self.tasks_state_monitor(), name="Manager:task_info"
            )

        try:
            await asyncio.wait_for(self.start_tasks(), timeout=BOOT_TIMEOUT)
        except TimeoutError:
            raise ConfigurationError(
                f"Timeout {BOOT_TIMEOUT}s while starting tasks. "
                "Check your configuration and network connection."
            )

    async def do(self):
        while not self.stopper and not self.eof:
            await asyncio.sleep(SLEEP_INTERVAL_DEFAULT)
            if any([t.eof for t in self.tasks]) or any([t.stopper for t in self.tasks]):
                debug(f"🔚 {self.name} received EOF or stopper, exiting...")
                info("🏁 done!")
                +self.stopper  # noqa
        await self.graceful_exit()

    async def exit(self):
        try:
            await self.stop_writer()
        except asyncio.CancelledError:
            debug(f"🔧 {self.name} writer shutdown cancelled")
        debug(f"🔧 {self.name} exiting...")
        +self._state_stopper  # noqa
        +self.stopper  # noqa

    async def shutdown_task(self, task):
        +task.stopper  # noqa
        debug(f"🔧 {self.name} shutting down task: {task.name}...")
        try:
            await asyncio.wait_for(self.reader._task, timeout=SHUTDOWN_TIMEOUT)
        except TimeoutError:
            debug(f"🔧 {self.name} task {task.name} shutdown timeout!")
            task._task.cancel()
        except Exception as e:
            debug(f"🔧 {self.name} task {task.name} shutdown error: {e}")
            task._task.cancel()

    async def graceful_exit(self):
        try:
            await self.shutdown_task(self.reader)
            await self.shutdown_task(self.sender)
            await asyncio.sleep(SAFE_PUBLICATION_END_DELAY)
            await self.shutdown_task(self.receiver)
            await self.shutdown_task(self.rtmon)
            await self.shutdown_task(self.transcription)
            await self.shutdown_task(self.rt)
        except asyncio.CancelledError:
            pass
        finally:
            await self.stop_writer()

    async def stop_writer(self):
        +self.writer.stopper  # noqa
        debug(f"🔧 {self.name} waiting for writer to finish...")
        while not self.writer._task.done():
            try:
                await self.writer._task
            except asyncio.CancelledError:
                self.writer._task.uncancel()
        debug(f"🔧 {self.name} writer finished!")
