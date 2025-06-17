from __future__ import annotations

import asyncio
import time
from collections import Counter, deque
from dataclasses import KW_ONLY, dataclass, field

from palabra_ai.base.adapter import Reader, Writer
from palabra_ai.base.message import Message
from palabra_ai.base.task import Task, TaskEvent
from palabra_ai.config import (
    COMPLETION_WAIT_TIMEOUT,
    EMPTY_MESSAGE_THRESHOLD,
    MONITOR_TIMEOUT,
    SLEEP_INTERVAL_DEFAULT,
    Config,
)
from palabra_ai.task.buffer import Buffer
from palabra_ai.task.realtime import Realtime
from palabra_ai.task.receiver import ReceiverTranslatedAudio
from palabra_ai.task.sender import SenderSourceAudio
from palabra_ai.util.emoji import Emoji
from palabra_ai.util.logger import debug

STATS_LOG_INTERVAL = 5.0  # seconds


@dataclass
class Stats:
    start_time: float = field(default_factory=time.time)
    last_log_time: float = field(default_factory=time.time)
    translation_started: bool = False
    translation_complete: bool = False
    bytes_sent: int = 0
    bytes_received: int = 0
    reader_eof_received: bool = False
    message_history: deque[Message] = field(
        default_factory=lambda: deque(maxlen=EMPTY_MESSAGE_THRESHOLD)
    )
    message_counter: Counter[Message.Type] = field(default_factory=Counter)
    process_states: dict = field(default_factory=dict)
    # queue_levels: dict[str, int] = field(default_factory=dict)

    @property
    def elapsed(self) -> float:
        return time.time() - self.start_time

    @property
    def silent_count(self) -> int:
        return sum(
            1
            for msg in self.message_history
            if msg.type_ not in Message.IN_PROCESS_TYPES
        )

    def to_dict(self) -> dict:
        return {
            "elapsed": round(self.elapsed, 1),
            "bytes_sent": self.bytes_sent,
            "bytes_received": self.bytes_received,
            "messages": dict(self.message_counter.most_common()),
            "silent_messages": f"{self.silent_count}/{len(self.message_history)}",
            "eof": self.reader_eof_received,
            "translation_started": self.translation_started,
            "translation_complete": self.translation_complete,
            "processes": self.process_states,
        }

    def to_log_string(self) -> str:
        process_states_str = ", ".join(
            f"{name}: {state}" for name, state in self.process_states.items()
        )
        # queue_levels_str = ", ".join(
        #     f"{lang}: {level}ms" for lang, level in self.queue_levels.items()
        # )
        return (
            f"📊 [STATS] "
            f"⏱️ {self.elapsed:.1f}s | "
            f"📤 {self.bytes_sent}B | "
            f"📥 {self.bytes_received}B | "
            f"📨 {dict(self.message_counter.most_common())} | "
            f"🔇 {self.silent_count}/{len(self.message_history)} | "
            f"🏁 EOF: {'✅' if self.reader_eof_received else '❌'} | "
            f"⚙️ {process_states_str} "
            # f"📈 Queue Levels: {queue_levels_str} "
        )


@dataclass
class Manager(Task):
    """Manages the translation process and monitors progress."""

    cfg: Config
    rt: Realtime
    sender: SenderSourceAudio
    receiver: ReceiverTranslatedAudio
    writer: Writer
    buffer_manager: Buffer
    reader: Reader
    input_stopper: TaskEvent
    _: KW_ONLY
    stat: Stats = field(default_factory=Stats, init=False)
    _debug_mode: bool = field(default=True, init=False)

    async def run(self):
        await self._wait_subtasks()
        +self.ready  # noqa

        async with asyncio.TaskGroup() as tg:
            monitor = tg.create_task(self._monitor_loop())
            eof = tg.create_task(self._check_eof_loop())

            await self._wait_for_completion()
            await self._handle_completion()

            monitor.cancel()
            eof.cancel()

    async def _wait_subtasks(self):
        await asyncio.gather(self.rt.ready, self.sender.ready, self.receiver.ready)

    async def _monitor_loop(self):
        queue = self.rt.out_foq.subscribe("manager", maxsize=0)

        while not self.stopper:
            try:
                rt_msg = await asyncio.wait_for(queue.get(), timeout=MONITOR_TIMEOUT)
                queue.task_done()
            except TimeoutError:
                await self._log_stats()
                continue

            msg = rt_msg.msg

            debug(f"📨 Monitor received: {msg}...")

            self.stat.message_history.append(msg)
            self.stat.message_counter[msg.type_] += 1

            match msg.type_:
                case type_ if type_ in Message.IN_PROCESS_TYPES:
                    self.stat.translation_started = True
                    debug(repr(msg))

                case Message.Type._QUEUE_LEVEL:
                    queue_level = msg.current_queue_level_ms
                    if queue_level > 0:
                        # self.stat.queue_levels[msg.language.code] = queue_level
                        self.stat.translation_started = True

            if self._is_complete():
                debug("🏁 Translation complete conditions met")
                self.stat.translation_complete = True

            await self._log_stats()

    def _is_complete(self) -> bool:
        eof_received = self.stat.reader_eof_received
        translation_started = self.stat.translation_started
        has_threshold_messages_count = (
            len(self.stat.message_history) >= EMPTY_MESSAGE_THRESHOLD
        )
        all_messages_are_empty = all(
            msg.type_ not in Message.IN_PROCESS_TYPES
            for msg in self.stat.message_history
        )
        complete_conditions = {
            "eof": eof_received,
            "started": translation_started,
            f"has_{EMPTY_MESSAGE_THRESHOLD}": has_threshold_messages_count,
            f"empty_{EMPTY_MESSAGE_THRESHOLD}": all_messages_are_empty,
        }
        debug(", ".join(f"{k}:{Emoji.bool(v)}" for k, v in complete_conditions.items()))
        return all(complete_conditions.values())

    async def _check_eof_loop(self):
        await self.reader.eof
        self.stat.reader_eof_received = True
        debug("🏁 Reader EOF detected")

    async def _wait_for_completion(self):
        while not self.stat.translation_complete:
            await asyncio.sleep(SLEEP_INTERVAL_DEFAULT)

    async def _handle_completion(self):
        debug("🎬 Translation complete, stopping input processes...")
        +self.input_stopper  # noqa

        await asyncio.sleep(COMPLETION_WAIT_TIMEOUT)

        while not self.writer._task.done():
            await asyncio.sleep(SLEEP_INTERVAL_DEFAULT)

        debug("🎉 All processes completed")

    async def _log_stats(self):
        if (
            not self._debug_mode
            or time.time() - self.stat.last_log_time < STATS_LOG_INTERVAL
        ):
            return

        self.stat.process_states = await self._get_process_states()
        debug(self.stat.to_log_string())
        self.stat.last_log_time = time.time()

    async def _get_process_states(self) -> dict:
        process_names = {
            "FileReader",
            "FileWriter",
            "Realtime",
            "Buffer",
            "Manager",
            "ReceiverTranslatedAudio",
            "SenderSourceAudio",
        }

        return {
            task.get_name(): (
                "🏃 running"
                if not task.done()
                else "❌ cancelled"
                if task.cancelled()
                else "✅ done"
                if not task.exception()
                else "💥 error"
            )
            for task in asyncio.all_tasks()
            if any(pname in task.get_name() for pname in process_names)
        }

    @property
    def is_translation_complete(self) -> bool:
        return self.stat.translation_complete

    def update_bytes_sent(self, bytes_count: int):
        self.stat.bytes_sent += bytes_count

    def update_bytes_received(self, bytes_count: int):
        self.stat.bytes_received += bytes_count
