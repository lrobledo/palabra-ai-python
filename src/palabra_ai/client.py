from __future__ import annotations

import asyncio
import contextlib
import os
import signal
from collections.abc import AsyncIterator
from dataclasses import dataclass

from aioshutdown import SIGHUP, SIGINT, SIGTERM

from palabra_ai.base.task import TaskEvent
from palabra_ai.config import Config
from palabra_ai.exc import ConfigurationError
from palabra_ai.internal.rest import PalabraRESTClient
from palabra_ai.task.manager import Manager
from palabra_ai.util.logger import debug, error, info


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

    def run(self, config: Config, stopper: TaskEvent | None = None) -> None:
        async def _run():
            # asyncio.create_task(_dbg_tasks())
            async with self.process(config, stopper) as manager:
                await manager.task

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            task = loop.create_task(_run(), name="PalabraAI")

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
                import uvloop

                asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
            except ImportError:
                pass

            try:
                with SIGTERM | SIGHUP | SIGINT as shutdown_loop:
                    shutdown_loop.run_until_complete(_run())
            except KeyboardInterrupt:
                debug("Received keyboard interrupt (Ctrl+C)")
            finally:
                debug("Shutdown complete")

    @contextlib.asynccontextmanager
    async def process(
        self, cfg: Config, stopper: TaskEvent | None = None
    ) -> AsyncIterator[Manager]:
        info("Starting translation process...")
        if stopper is None:
            stopper = TaskEvent()

        credentials = await PalabraRESTClient(
            self.api_key,
            self.api_secret,
            base_url=self.api_endpoint,
        ).create_session()

        try:
            async with asyncio.TaskGroup() as tg:
                manager = Manager(cfg, credentials, stopper=stopper)(tg)
                yield manager

            info("Translation completed successfully")

        except* Exception as eg:
            for e in eg.exceptions:
                if not isinstance(e, asyncio.CancelledError):
                    error(f"Translation failed: {e}")
            raise

        # # Create separate stoppers for different groups
        # input_stopper = TaskEvent()  # For reader, sender, receiver
        # writer_stopper = TaskEvent()  # For writer only
        # input_stopper.set_owner("input_stopper")
        # writer_stopper.set_owner("writer_stopper")
