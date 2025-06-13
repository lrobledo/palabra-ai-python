import abc
import asyncio
from dataclasses import KW_ONLY, dataclass, field

import loguru
from loguru import logger as l


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
    _tg: asyncio.TaskGroup = field(default=None, init=False, repr=False)
    _task: asyncio.Task = field(default=None, init=False, repr=False)
    _name: str | None = field(default=None, init=False, repr=False)
    ready: TaskEvent = field(default_factory=TaskEvent, init=False)
    stopper: TaskEvent | None = field(default=None, init=False, repr=False)

    def __call__(
        self, tg: asyncio.TaskGroup, stopper: TaskEvent | None = None
    ) -> "Task":
        self._tg = tg
        self.stopper = stopper
        self.ready.set_owner(f"{self.__class__.__name__}.ready")
        l.debug(f"{self.name} starting...")
        self._task = tg.create_task(self.run(), name=self.name)
        return self

    @abc.abstractmethod
    async def run(self): ...

    @property
    def name(self) -> str:
        return self._name or self.__class__.__name__

    @name.setter
    def name(self, value: str) -> None:
        self._name = value

    @property
    def task(self) -> asyncio.Task:
        if not self._task:
            raise RuntimeError(f"{self.name} task not set. Call the process first")
        return self._task
