from dataclasses import dataclass
from dataclasses import field
from dataclasses import KW_ONLY

from palabra_ai.base.task import Task
from palabra_ai.util.fanout_queue import FanoutQueue


@dataclass
class Io(Task):
    _: KW_ONLY
    in_foq: FanoutQueue = field(default_factory=FanoutQueue, init=False)
    out_foq: FanoutQueue = field(default_factory=FanoutQueue, init=False)
