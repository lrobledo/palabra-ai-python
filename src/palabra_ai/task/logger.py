from __future__ import annotations

import asyncio
import time
from dataclasses import KW_ONLY, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import palabra_ai
from palabra_ai.base.task import Task
from palabra_ai.config import Config
from palabra_ai.task.realtime import Realtime, RtMsg
from palabra_ai.util.logger import ALL_LOGS, debug, error
from palabra_ai.util.orjson import to_json


@dataclass
class Logger(Task):
    """Logs all WebSocket and WebRTC messages to files."""

    cfg: Config
    rt: Realtime
    config_dict: dict[str, Any]
    _: KW_ONLY
    _txt_file: Any = field(default=None, init=False)
    _messages: list[RtMsg] = field(default_factory=list, init=False)
    _start_ts: float = field(default_factory=time.time, init=False)
    _rt_in_q: asyncio.Queue | None = field(default=None, init=False)
    _rt_out_q: asyncio.Queue | None = field(default=None, init=False)
    _log_file: Path | str = field(default="", init=False)

    def __post_init__(self):
        self._log_file = Path(self.cfg.log_file)
        self._rt_in_q = self.rt.in_foq.subscribe("logger", maxsize=0)
        self._rt_out_q = self.rt.out_foq.subscribe("logger", maxsize=0)
        try:
            self._txt_file = open(self._log_file.with_suffix(".txt"), "a")
        except Exception as e:
            error(f"Failed to open log file: {e}")
            raise

    async def run(self):
        await self.rt.ready
        debug(f"Logger started, writing to {self._log_file}")

        try:
            async with asyncio.TaskGroup() as tg:
                in_task = tg.create_task(self._consume(self._rt_in_q))
                out_task = tg.create_task(self._consume(self._rt_out_q))

                +self.ready  # noqa

                # Wait for stopper
                while not self.stopper:
                    await asyncio.sleep(0.1)

                in_task.cancel()
                out_task.cancel()

        finally:
            await self._finalize()

    async def _consume(self, q: asyncio.Queue):
        """Process WebSocket messages."""
        try:
            while True:
                rt_msg = await q.get()
                await self._write_message(rt_msg)
                q.task_done()
        except asyncio.CancelledError:
            debug(f"Consumer for {q} cancelled")
            raise

    async def _write_message(self, rt_msg: RtMsg):
        """Write message to txt file and store for json."""
        self._messages.append(rt_msg)

        # Write known_raw data to txt file
        if self._txt_file:
            dt = datetime.fromtimestamp(rt_msg.ts, tz=UTC).strftime(
                "%Y-%m-%d %H:%M:%S.%f"
            )[:-3]
            raw_str = (
                f"{dt} | {rt_msg.ch.value:<7} | {rt_msg.dir.value:<4} | {rt_msg.msg}"
            )
            self._txt_file.write(raw_str + "\n")
            self._txt_file.flush()

    async def _finalize(self):
        """Write JSON file and close resources."""
        debug("Finalizing Logger...")

        if self._txt_file:
            self._txt_file.close()

        if self._log_file:
            json_data = {
                "version": palabra_ai.__version__,
                "messages": self._messages,
                "start_ts": self._start_ts,
                "cfg": self.config_dict,
                "logs": ALL_LOGS,
            }

            json_path = self._log_file.with_suffix(".json")
            with open(json_path, "wb") as f:
                f.write(to_json(json_data))

            debug(f"Saved {len(self._messages)} messages to {json_path}")
