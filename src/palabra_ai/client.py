from __future__ import annotations

import asyncio
import contextlib
import os
import signal
from collections.abc import AsyncIterator
from dataclasses import dataclass

from aioshutdown import SIGHUP, SIGINT, SIGTERM
from loguru import logger

from palabra_ai.base.adapter import Reader, Writer
from palabra_ai.base.task import TaskEvent
from palabra_ai.config import Config
from palabra_ai.exc import ConfigurationError
from palabra_ai.internal.rest import PalabraRESTClient
from palabra_ai.internal.webrtc import AudioTrackSettings
from palabra_ai.task.buffer import Buffer
from palabra_ai.task.logger import Logger
from palabra_ai.task.manager import Manager
from palabra_ai.task.realtime import Realtime
from palabra_ai.task.receiver import ReceiverTranslatedAudio
from palabra_ai.task.sender import SenderSourceAudio
from palabra_ai.task.transcription import Transcription

SINGLE_TARGET_SUPPORTED_COUNT = 1


@dataclass
class PalabraAI:
    api_key: str | None = None
    api_secret: str | None = None
    api_endpoint: str = "https://api.palabra.ai"

    def __post_init__(self):
        self.api_key = self.api_key or os.getenv("PALABRA_API_KEY")
        if not self.api_key:
            raise ConfigurationError("PALABRA_API_KEY is not set")

        self.api_secret = self.api_secret or os.getenv("PALABRA_API_SECRET")
        if not self.api_secret:
            raise ConfigurationError("PALABRA_API_SECRET is not set")

    def run(self, config: Config) -> None:
        async def _run():
            async with self.process(config) as handle:
                await handle.task

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            task = loop.create_task(_run())

            def handle_interrupt(sig, frame):
                task.cancel()
                raise KeyboardInterrupt()

            old_handler = signal.signal(signal.SIGINT, handle_interrupt)
            try:
                return task
            finally:
                signal.signal(signal.SIGINT, old_handler)
        else:
            try:
                with SIGTERM | SIGHUP | SIGINT as shutdown_loop:
                    shutdown_loop.run_until_complete(_run())
            except KeyboardInterrupt:
                logger.debug("Received keyboard interrupt (Ctrl+C)")
            finally:
                logger.debug("Shutdown complete")

    @contextlib.asynccontextmanager
    async def process(self, cfg: Config) -> AsyncIterator[Manager]:
        logger.info("Starting translation process...")

        credentials = await PalabraRESTClient(
            self.api_key,
            self.api_secret,
            base_url=self.api_endpoint,
        ).create_session()

        if len(cfg.targets) != SINGLE_TARGET_SUPPORTED_COUNT:
            raise ConfigurationError("Only single target language supported")

        reader = cfg.source._in_pcm
        if not isinstance(reader, Reader):
            raise ConfigurationError("src._in_pcm must be Reader")

        target = cfg.targets[0]
        writer = target._out_pcm
        if not isinstance(writer, Writer):
            raise ConfigurationError("target._out_pcm must be Writer")

        if hasattr(reader, "set_track_settings"):
            reader.set_track_settings(AudioTrackSettings())
        if hasattr(writer, "set_track_settings"):
            writer.set_track_settings(AudioTrackSettings())

        # Create separate stoppers for different groups
        input_stopper = TaskEvent()  # For reader, sender, receiver
        writer_stopper = TaskEvent()  # For writer only
        input_stopper.set_owner("input_stopper")
        writer_stopper.set_owner("writer_stopper")

        try:
            async with asyncio.TaskGroup() as tg:
                logger.debug("Starting processes...")

                reader(tg, input_stopper)
                writer(tg, writer_stopper)

                realtime = Realtime(cfg, credentials)

                if cfg.log_file:
                    Logger(cfg, realtime, cfg.to_dict())(tg, writer_stopper)
                realtime(tg, input_stopper)

                buffer_mgr = Buffer(cfg, writer)(tg, writer_stopper)

                manager = Manager(
                    cfg, realtime, None, None, writer, buffer_mgr, reader, input_stopper
                )(tg, input_stopper)

                receiver = ReceiverTranslatedAudio(
                    cfg,
                    realtime,
                    buffer_mgr,
                    manager,
                    target.lang.bcp47,
                    reader,
                    writer_stopper,
                )(tg, input_stopper)

                sender = SenderSourceAudio(
                    cfg,
                    realtime,
                    reader,
                    cfg.to_dict(),
                    AudioTrackSettings(),
                    manager,
                    receiver,
                )(tg, input_stopper)

                # Update manager references
                manager.sender = sender
                manager.receiver = receiver

                # Start TranscriptionMessage if any callbacks are configured
                if cfg.source._on_transcription or any(
                    t._on_transcription for t in cfg.targets
                ):
                    transcription_task = Transcription(
                        cfg,
                        realtime,
                        cfg.source,
                        cfg.targets,
                        suppress_callback_errors=os.getenv(
                            "PALABRA_SUPPRESS_CALLBACK_ERRORS", "true"
                        ).lower()
                        == "true",
                    )
                    transcription_task(tg, input_stopper)

                yield manager

            logger.info("Translation completed successfully")

        except* Exception as eg:
            for e in eg.exceptions:
                if not isinstance(e, asyncio.CancelledError):
                    logger.error(f"Translation failed: {e}")
            if writer:
                await writer.cancel()
            raise
