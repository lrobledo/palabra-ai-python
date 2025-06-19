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
from palabra_ai.config import LOGGER_SHUTDOWN_TIMEOUT
from palabra_ai.exc import ConfigurationError
from palabra_ai.internal.rest import SessionCredentials
from palabra_ai.internal.webrtc import AudioTrackSettings
from palabra_ai.task.logger import Logger
from palabra_ai.task.monitor import RtMonitor
from palabra_ai.task.realtime import Realtime
from palabra_ai.task.receiver import ReceiverTranslatedAudio
from palabra_ai.task.sender import SenderSourceAudio
from palabra_ai.task.stat import Stat
from palabra_ai.task.transcription import Transcription
from palabra_ai.util.logger import debug, info
from palabra_ai.util.logger import warning


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
    logger: Logger | None = field(default=None, init=False)
    rtmon: RtMonitor = field(init=False)
    transcription: Transcription = field(init=False)
    stat: Stat = field(init=False)

    tasks: list[Task] = field(default_factory=list, init=False)

    _debug_mode: bool = field(default=True, init=False)
    _transcriptions_shown: set = field(default_factory=set, init=False)

    def __post_init__(self):
        self.stat = Stat(self)


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



    async def start_system(self):
        if self.logger:
            self.logger(self.root_tg)
            await self.logger.ready

        self.stat(self.root_tg)
        await self.stat.ready

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
        debug(f"🔧 {self.name}.boot()...")

        try:
            await asyncio.wait_for(self.start_system(), timeout=BOOT_TIMEOUT)
        except TimeoutError as e:
            raise ConfigurationError(
                f"Timeout {BOOT_TIMEOUT}s while starting tasks. "
                f"Check your configuration and network connection."
            ) from e



    async def do(self):
        while not self.stopper:
            try:
                await asyncio.sleep(SLEEP_INTERVAL_DEFAULT)
            except asyncio.CancelledError:
                info(f"☠️ {self.name}.do() cancelled, breaking!")
                break
            except Exception as e:
                warning(f"☠️ {self.name}.do() error: {e}, breaking!")
                break
            if any(t.eof for t in self.tasks) or any(t.stopper for t in self.tasks):
                debug(f"🔚 {self.name}.do() received EOF or stopper, exiting...")
                info("🏁 done!")
                break
        +self.stopper # noqa
        await self.graceful_exit()

    async def _exit(self):
        while not self._task.done():
            warning(f"🔧 {self.name}._exit(), waiting for it to finish...")
            try:
                return await self.exit()
            except asyncio.CancelledError:
                warning(f"🔧 {self.name}._exit() exit cancelled, trying again...")

    async def exit(self):
        debug(f"🔧 {self.name}.exit() begin")
        try:
            await self.writer_mercy()
        except asyncio.CancelledError:
            debug(f"🔧 {self.name}.exit() writer shutdown cancelled")
        except Exception as e:
            warning(f"🔧 {self.name}.exit() writer shutdown error: {e}")
        finally:
            debug(f"🔧 {self.name}.exit() exiting...")
            +self.stopper  # noqa
            +self.stat.stopper # noqa
            if self.logger:
                +self.logger.stopper  # noqa

    async def shutdown_task(self, task, timeout=SHUTDOWN_TIMEOUT):
        +task.stopper  # noqa
        debug(f"🔧 {self.name}.shutdown_task() shutting down task: {task.name}...")
        try:
            await asyncio.wait_for(self._task, timeout=timeout)
        except TimeoutError:
            warning(f"🔧 {self.name}.shutdown_task() {task.name} shutdown timeout!")
            task._task.cancel()
        except Exception as e:
            warning(f"🔧 {self.name}.shutdown_task() {task.name} shutdown error: {e}")
            task._task.cancel()
        finally:
            debug(f"🔧 {self.name}.shutdown_task() {task.name} end.")

    async def graceful_exit(self):
        debug(f"🔧 {self.name}.graceful_exit() starting...")
        try:
            await asyncio.gather(
                self.shutdown_task(self.reader),
                self.shutdown_task(self.sender),
                return_exceptions=True,
            )
        except asyncio.CancelledError:
            debug(f"🔧 {self.name}.graceful_exit() reader and sender shutdown cancelled")

        debug(f"🔧 {self.name}.graceful_exit() waiting {SAFE_PUBLICATION_END_DELAY=}...")
        try:
            await asyncio.sleep(SAFE_PUBLICATION_END_DELAY)
        except asyncio.CancelledError:
            debug(f"🔧 {self.name}.graceful_exit() sleep cancelled")
        debug(f"🔧 {self.name}.graceful_exit() {SAFE_PUBLICATION_END_DELAY=} waited!")
        debug(f"🔧 {self.name}.graceful_exit() gathering... ")
        try:
            await asyncio.gather(
                self.shutdown_task(self.receiver),
                self.shutdown_task(self.rtmon),
                self.shutdown_task(self.transcription),
                self.shutdown_task(self.rt),
                return_exceptions=True,
            )
        except asyncio.CancelledError:
            debug(f"🔧 {self.name}.graceful_exit() receiver, rtmon, transcription and rt shutdown cancelled")
        debug(f"🔧 {self.name}.graceful_exit() gathered!")




    async def writer_mercy(self):
        +self.writer.stopper  # noqa
        debug(f"🔧 {self.name}.writer_mercy() waiting for writer to finish...")
        while not self.writer._task.done():
            try:
                warning(f"🔧 {self.name}.writer_mercy() waiting for writer task to finish...")
                await asyncio.wait_for(self.writer._task, timeout=SHUTDOWN_TIMEOUT)
            except asyncio.CancelledError:
                warning(f"🔧 {self.name}.writer_mercy() uncancelled")
                self.writer._task.uncancel()
            except asyncio.TimeoutError:
                warning(f"🔧 {self.name}.writer_mercy() writer shutdown timeout!")
                # self.writer._task.cancel()
        debug(f"🔧 {self.name}.writer_mercy() writer finished!")
