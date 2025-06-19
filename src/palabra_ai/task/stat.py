import asyncio
import time
from dataclasses import KW_ONLY, dataclass

from palabra_ai.base.task import Task
from palabra_ai.config import (
    DEEP_DEBUG,
    SHUTDOWN_TIMEOUT,
    SLEEP_INTERVAL_DEFAULT,
    SLEEP_INTERVAL_LONG,
)
from palabra_ai.util.dbg_hang_coro import diagnose_hanging_tasks
from palabra_ai.util.logger import debug


@dataclass
class Stat(Task):
    manager: "palabra_ai.manager.Manager"
    _: KW_ONLY

    async def boot(self):
        pass

    async def do(self):
        show_every = 30 if DEEP_DEBUG else 150
        i = 0
        last_state = ""
        while not self.stopper:
            new_state = self.stat_palabra_tasks
            if new_state != last_state or i % show_every == 0:
                debug(self.stat)
                last_state = new_state
            i += 1
            await asyncio.sleep(SLEEP_INTERVAL_DEFAULT)
        await asyncio.sleep(SLEEP_INTERVAL_LONG)
        debug(self.stat)

    async def exit(self):
        debug(self.stat)

        moment = time.time()

        while time.time() - moment < SHUTDOWN_TIMEOUT:
            try:
                await asyncio.sleep(SLEEP_INTERVAL_LONG)
            except asyncio.CancelledError:
                pass
            debug(self.stat)

    @property
    def stat_palabra_tasks(self):
        return "\n".join(
            (
                "\nPalabra tasks:",
                "\n".join([str(t) for t in self.manager.tasks]),
            )
        )

    @property
    def stat_asyncio_tasks(self):
        return "\n".join(
            (
                "\nAsyncio tasks:\n",
                " | ".join(sorted([t.get_name() for t in asyncio.all_tasks()])),
            )
        )

    @property
    def stat(self):
        deep = diagnose_hanging_tasks() if self.manager.cfg.deep_debug else ""
        return f"{deep}\n{self.stat_palabra_tasks}\n{self.stat_asyncio_tasks}"
