import abc
import asyncio
from dataclasses import KW_ONLY, dataclass, field

import loguru

from palabra_ai.config import SHUTDOWN_TIMEOUT
from palabra_ai.util.emoji import Emoji
from palabra_ai.util.logger import debug, error
from palabra_ai.util.logger import warning


class TaskEvent(asyncio.Event):
    _owner: str = ""

    def __init__(self, *args, **kwargs):
        self._log = loguru.logger
        super().__init__(*args, **kwargs)

    def set_owner(self, owner: str):
        self._owner = owner

    def log(self):
        status = "[+] " if self.is_set() else "[-] "
        self._log.debug(f"{status}{self._owner}")

    def __pos__(self):
        self.set()
        self.log()
        return self

    def __neg__(self):
        self.clear()
        self.log()
        return self

    def __bool__(self):
        return self.is_set()

    def __await__(self):
        if self.is_set():
            return self._immediate_return().__await__()
        return self.wait().__await__()

    async def _immediate_return(self):
        return

    def __repr__(self):
        return f"TaskEvent({self.is_set()})"


@dataclass
class Task(abc.ABC):
    _: KW_ONLY
    root_tg: asyncio.TaskGroup = field(default=None, init=False, repr=False)
    sub_tg: asyncio.TaskGroup = field(
        default_factory=asyncio.TaskGroup, init=False, repr=False
    )
    _task: asyncio.Task = field(default=None, init=False, repr=False)
    _name: str | None = field(default=None, init=False, repr=False)
    ready: TaskEvent = field(default_factory=TaskEvent, init=False)
    eof: TaskEvent = field(default_factory=TaskEvent, init=False)
    stopper: TaskEvent = field(default_factory=TaskEvent)
    _state: list[str] = field(default_factory=list, init=False, repr=False)

    # def __init__(self, *args, **kwargs):
    #     super().__init__(*args, **kwargs)

    def __call__(self, tg: asyncio.TaskGroup) -> "Task":
        self.root_tg = tg
        self.ready.set_owner(f"{self.name}.ready")
        self.eof.set_owner(f"{self.name}.eof")
        self.stopper.set_owner(f"{self.name}.stopper")
        self._task = tg.create_task(self.run(), name=self.name)
        return self

    async def run(self):
        self._state.append("🚀")
        async with self.sub_tg:
            try:

                debug(f"{self.name}.run() starting...")
                self._state.append("🌀")
                await self._boot()
                self._state.append("🟢")
                +self.ready  # noqa
                debug(f"{self.name}.run() ready, doing...")
                self._state.append("💫")
                await self.do()
                self._state.append("🎉")
                debug(f"{self.name}.run() done, exiting...")
                +self.stopper # noqa
                # self.sub_tg._abort()
            except asyncio.CancelledError:
                self._state.append("🚫")
                debug(f"{self.name}.run() cancelled, exiting...")
                # raise
            except Exception as e:
                self._state.append("💥")
                error(f"{self.name}.run() failed with error: {e}, exiting...")
                # raise
            finally:
                +self.stopper # noqa
                self._state.append("👋")
                debug(f"{self.name}.run() trying to exit...")
                result = await self._exit()
                self._state.append("🔴")
                debug(f"{self.name}.run() exited successfully!")
                self.sub_tg._abort()
            return result

    async def _boot(self):
        return await self.boot()

    @abc.abstractmethod
    async def boot(self):
        raise NotImplementedError()

    @abc.abstractmethod
    async def do(self):
        raise NotImplementedError()

    @abc.abstractmethod
    async def exit(self):
        raise NotImplementedError()

    async def _exit(self):
        try:
            return await asyncio.wait_for(self.exit(), timeout=SHUTDOWN_TIMEOUT)
        except asyncio.TimeoutError:
            error(f"{self.name}.exit() timed out after {SHUTDOWN_TIMEOUT}s")
            self._task.cancel()
            warning(f"{self.name}.exit() last chance...")
            await self._task
            warning(f"{self.name}.exit() last chance used!")

    @property
    def name(self) -> str:
        return f"[T]{self._name or self.__class__.__name__}"

    @name.setter
    def name(self, value: str) -> None:
        self._name = value

    @property
    def task(self) -> asyncio.Task:
        if not self._task:
            raise RuntimeError(f"{self.name} task not set. Call the process first")
        return self._task

    def __str__(self):
        ready = Emoji.bool(self.ready)
        stopper = Emoji.bool(self.stopper)
        eof = Emoji.bool(self.eof)
        states = " ".join(self._state) if self._state else "⭕"
        return f"{self.name:>28}(ready={ready}, stopper={stopper}, eof={eof}, states={states})"
