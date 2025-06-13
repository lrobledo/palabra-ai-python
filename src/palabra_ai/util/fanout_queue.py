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

    async def publish(self, message: Any) -> dict[str, str]:
        try:
            async with self._lock:
                subscribers = list(self.subscribers.items())
        except asyncio.CancelledError:
            logger.warning("FanoutQueue publish cancelled during lock acquisition")
            raise

        results = {}
        for sub_id, subscription in subscribers:
            try:
                subscription.queue.put_nowait(message)
                results[sub_id] = "ok"
            except asyncio.QueueFull:
                if subscription.fail_on_full:
                    raise QueueFullError(
                        f"Queue full for subscriber '{sub_id}' (size: {subscription.queue.maxsize})"
                    ) from None
                logger.warning(
                    f"Dropping message for subscriber '{sub_id}': "
                    f"queue full (size: {subscription.queue.maxsize})"
                )
                results[sub_id] = f"dropped (queue full: {subscription.queue.maxsize})"

        return results
