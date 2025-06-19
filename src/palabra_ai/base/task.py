import abc
import asyncio
from dataclasses import KW_ONLY, dataclass, field

import loguru

from palabra_ai.util.emoji import Emoji
from palabra_ai.util.logger import debug, error


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
        try:
            async with self.sub_tg:
                debug(f"{self.name} starting...")
                self._state.append("🌀")
                await self._boot()
                self._state.append("🟢")
                +self.ready  # noqa
                debug(f"{self.name} ready, doing...")
                self._state.append("💫")
                await self.do()
                self._state.append("🎉")
                debug(f"{self.name} done, exiting...")
        except asyncio.CancelledError:
            self._state.append("🚫")
            debug(f"{self.name} cancelled, exiting...")
            raise
        except Exception as e:
            self._state.append("💥")
            error(f"{self.name} failed with error: {e}")
            raise
        finally:
            self._state.append("👋")
            result = await self._exit()
            self._state.append("🔴")
            debug(f"{self.name} exited successfully")
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
        +self.stopper  # noqa
        return await self.exit()

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
