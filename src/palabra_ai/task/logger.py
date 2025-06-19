from __future__ import annotations

import asyncio
import time
from dataclasses import KW_ONLY, dataclass, field

import palabra_ai
from palabra_ai.base.task import Task
from palabra_ai.config import SLEEP_INTERVAL_DEFAULT, Config
from palabra_ai.task.realtime import Realtime, RtMsg
from palabra_ai.util.logger import debug
from palabra_ai.util.orjson import to_json
from palabra_ai.util.sysinfo import get_system_info


@dataclass
class Logger(Task):
    """Logs all WebSocket and WebRTC messages to files."""

    cfg: Config
    rt: Realtime
    _: KW_ONLY
    _messages: list[RtMsg] = field(default_factory=list, init=False)
    _start_ts: float = field(default_factory=time.time, init=False)
    _rt_in_q: asyncio.Queue | None = field(default=None, init=False)
    _rt_out_q: asyncio.Queue | None = field(default=None, init=False)
    _in_task: asyncio.Task | None = field(default=None, init=False)
    _out_task: asyncio.Task | None = field(default=None, init=False)

    def __post_init__(self):
        self._rt_in_q = self.rt.in_foq.subscribe(self, maxsize=0)
        self._rt_out_q = self.rt.out_foq.subscribe(self, maxsize=0)

    async def boot(self):
        self._in_task = self.sub_tg.create_task(
            self._consume(self._rt_in_q), name="Logger:rt_in"
        )
        self._out_task = self.sub_tg.create_task(
            self._consume(self._rt_out_q), name="Logger:rt_out"
        )
        debug(f"Logger started, writing to {self.cfg.log_file}")
        await self.rt.ready

    async def do(self):
        # Wait for stopper
        while not self.stopper:
            await asyncio.sleep(SLEEP_INTERVAL_DEFAULT)

    async def exit(self):
        debug("Finalizing Logger...")

        logs = []
        try:
            with open(self.cfg.log_file) as f:
                logs = f.readlines()
        except BaseException as e:
            logs = ["Can't collect logs", str(e)]

        try:
            sysinfo = get_system_info()
        except BaseException as e:
            sysinfo = {"error": str(e)}

        json_data = {
            "version": getattr(palabra_ai, "__version__", "n/a"),
            "sysinfo": sysinfo,
            "messages": self._messages,
            "start_ts": self._start_ts,
            "cfg": self.cfg,
            "log_file": str(self.cfg.log_file),
            "trace_file": str(self.cfg.trace_file),
            "debug": self.cfg.debug,
            "logs": logs,
        }

        with open(self.cfg.trace_file, "wb") as f:
            f.write(to_json(json_data))

        debug(f"Saved {len(self._messages)} messages to {self.cfg.trace_file}")

        self.rt.in_foq.unsubscribe(self)
        self.rt.out_foq.unsubscribe(self)

    async def _consume(self, q: asyncio.Queue):
        """Process WebSocket messages."""
        try:
            while True:
                rt_msg = await q.get()
                self._messages.append(rt_msg)
                q.task_done()
        except asyncio.CancelledError:
            debug(f"Consumer for {q} cancelled")
            raise
