import abc
import time
from asyncio import sleep
from dataclasses import dataclass
from dataclasses import field
from dataclasses import KW_ONLY
from enum import StrEnum
from typing import Optional
from typing import TYPE_CHECKING

from palabra_ai.base.message import CurrentTaskMessage
from palabra_ai.base.message import GetTaskMessage
from palabra_ai.base.message import SetTaskMessage
from palabra_ai.base.task import Task
from palabra_ai.constant import BOOT_TIMEOUT
from palabra_ai.constant import SLEEP_INTERVAL_LONG
from palabra_ai.util.fanout_queue import FanoutQueue


if TYPE_CHECKING:
    from palabra_ai.config import Config
    from palabra_ai.task.manager import Manager
    from palabra_ai.internal.rest import SessionCredentials
    from palabra_ai.base.message import Message
    from palabra_ai.base.audio import AudioFrame
    from palabra_ai.base.adapter import Reader, Writer





@dataclass
class Io(Task):
    cfg: "Config"
    credentials: "SessionCredentials"
    reader: "Reader"
    writer: "Writer"
    _: KW_ONLY
    in_msg_foq: FanoutQueue["Message"] = field(default_factory=FanoutQueue, init=False)
    out_msg_foq: FanoutQueue["Message"] = field(default_factory=FanoutQueue, init=False)
    _buffer_callback: Optional[callable] = field(default=None, init=False)

    @abc.abstractmethod
    async def push_in_msg(self, msg: "Message") -> None:
        """Push an incoming message to the input fanout queue."""
        ...

    async def set_task(self):
        self.dbg("Setting task configuration...")
        await sleep(SLEEP_INTERVAL_LONG)
        async with self.out_msg_foq.receiver(self, self.stopper) as msgs_out:
            await self.push_in_msg(SetTaskMessage.from_config(self.cfg))
            start_ts = time.time()
            await sleep(SLEEP_INTERVAL_LONG)
            while start_ts + BOOT_TIMEOUT > time.time():
                await self.push_in_msg(GetTaskMessage())
                msg = await anext(msgs_out)
                if isinstance(msg, CurrentTaskMessage):
                    self.dbg(f"Received current task: {msg.data}")
                    return
                self.dbg(f"Received unexpected message: {msg}")
                await sleep(SLEEP_INTERVAL_LONG)
        self.dbg("Timeout waiting for task configuration")
        raise TimeoutError("Timeout waiting for task configuration")