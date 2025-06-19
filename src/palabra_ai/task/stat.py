import asyncio
import time
from dataclasses import dataclass
from dataclasses import field
from dataclasses import KW_ONLY

from palabra_ai.base.task import Task
from palabra_ai.config import LOGGER_SHUTDOWN_TIMEOUT
from palabra_ai.config import SAFE_PUBLICATION_END_DELAY
from palabra_ai.config import SHUTDOWN_TIMEOUT
from palabra_ai.config import SLEEP_INTERVAL_DEFAULT
from palabra_ai.config import SLEEP_INTERVAL_LONG
from palabra_ai.util.dbg_hang_coro import diagnose_hanging_tasks
from palabra_ai.util.logger import debug


@dataclass
class Stat(Task):
    manager: "palabra_ai.manager.Manager"
    _: KW_ONLY

    async def boot(self):
        pass

    async def do(self):
        i = 0
        last_state = ""
        while not self.stopper:
            new_state = self.stat_palabra_tasks
            if new_state != last_state or i % 30 == 0:
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
        return f"{self.stat_palabra_tasks}\n{self.stat_asyncio_tasks}\n\n{diagnose_hanging_tasks()}"
