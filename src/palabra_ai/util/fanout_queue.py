import asyncio
import logging
from typing import Any, NamedTuple

logger = logging.getLogger(__name__)


class QueueFullError(Exception):
    pass


class Subscription(NamedTuple):
    queue: asyncio.Queue
    fail_on_full: bool


class FanoutQueue:
    def __init__(self):
        self.subscribers: dict[str, Subscription] = {}
        self._lock = asyncio.Lock()

    def subscribe(
        self, subscriber: Any, maxsize: int = 0, fail_on_full: bool = True
    ) -> asyncio.Queue:
        if not isinstance(subscriber, str):
            subscriber_id = id(subscriber)
        else:
            subscriber_id = subscriber
        if subscriber_id not in self.subscribers:
            queue = asyncio.Queue(maxsize)
            self.subscribers[subscriber_id] = Subscription(queue, fail_on_full)
            return queue
        return self.subscribers[subscriber_id].queue

    def unsubscribe(self, subscriber_id: str) -> None:
        self.subscribers.pop(subscriber_id, None)

    def publish(self, message: Any) -> None:
        for subscription in self.subscribers.values():
            subscription.queue.put_nowait(message)
