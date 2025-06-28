import asyncio
import uuid
from contextlib import asynccontextmanager
from typing import Any, NamedTuple, Optional, AsyncIterator, AsyncGenerator, TypeVar, Generic

from palabra_ai.util.logger import debug

T = TypeVar('T')


class Subscription(NamedTuple):
    subscription_id: str
    queue: asyncio.Queue[Optional[T]]


class FanoutQueue(Generic[T]):
    def __init__(self):
        self.subscribers: dict[str, Subscription] = {}
        self._closed = False

    def _get_id(self, subscriber: Any) -> str:
        if not isinstance(subscriber, str):
            return str(id(subscriber))
        return subscriber

    def is_subscribed(self, subscriber: Any) -> bool:
        """Check if subscriber is currently subscribed"""
        subscriber_id = self._get_id(subscriber)
        return subscriber_id in self.subscribers

    def subscribe(self, subscriber: Any, maxsize: int = 0) -> asyncio.Queue[Optional[T]]:
        if self._closed:
            raise RuntimeError("FanoutQueue is closed")

        subscriber_id = self._get_id(subscriber)
        if subscriber_id not in self.subscribers:
            queue: asyncio.Queue[Optional[T]] = asyncio.Queue(maxsize)
            self.subscribers[subscriber_id] = Subscription(
                subscription_id=subscriber_id,
                queue=queue
            )
            return queue
        return self.subscribers[subscriber_id].queue

    def unsubscribe(self, subscriber: Any) -> None:
        subscriber_id = self._get_id(subscriber)
        subscription = self.subscribers.pop(subscriber_id, None)
        if subscription is None:
            return

        # Always send None to signal termination
        subscription.queue.put_nowait(None)

    def publish(self, message: Optional[T]) -> None:
        """Publish message to all subscribers. Can be None."""
        if self._closed:
            raise RuntimeError("FanoutQueue is closed")

        for subscription in self.subscribers.values():
            try:
                subscription.queue.put_nowait(message)
            except asyncio.QueueFull:
                debug(f"Queue full for subscriber {subscription.subscription_id}, skipping message")

    def close(self) -> None:
        """Close the FanoutQueue and unsubscribe all subscribers"""
        if self._closed:
            return

        self._closed = True
        debug("Closing FanoutQueue")

        # Copy list to avoid modification during iteration
        subscriber_ids = list(self.subscribers.keys())
        for subscriber_id in subscriber_ids:
            self.unsubscribe(subscriber_id)

        debug(f"Closed FanoutQueue, unsubscribed {len(subscriber_ids)} subscribers")

    @asynccontextmanager
    async def receiver(self, subscriber_id: Optional[str] = None, timeout: Optional[float] = None) -> AsyncIterator[
        AsyncGenerator[T, None]]:
        """Context manager for subscribing and receiving messages

        Args:
            subscriber_id: Optional custom ID for the subscriber
            timeout: Optional timeout for waiting on messages (prevents hanging)
        """

        if subscriber_id is None:
            subscriber_id = str(uuid.uuid4())

        async def message_generator(subscription: Subscription) -> AsyncGenerator[T, None]:
            """Inner generator for messages"""
            while True:
                try:
                    if timeout is not None:
                        # Use timeout to prevent hanging
                        msg: Optional[T] = await asyncio.wait_for(
                            subscription.queue.get(),
                            timeout=timeout
                        )
                    else:
                        msg = await subscription.queue.get()

                    # If None received, just exit
                    if msg is None:
                        break

                    yield msg

                except asyncio.TimeoutError:
                    # Timeout reached, check if we should continue
                    if self._closed or not self.is_subscribed(subscriber_id):
                        debug(f"Subscriber {subscriber_id} stopping due to timeout and closed/unsubscribed state")
                        break
                    # Otherwise continue waiting

        debug(f"Starting subscriber {subscriber_id}")

        # Subscribe
        q = self.subscribe(subscriber_id, maxsize=0)
        subscription = self.subscribers[subscriber_id]
        generator = message_generator(subscription)

        try:
            yield generator
        finally:
            debug(f"Cleaning up subscriber {subscriber_id}")

            # CORRECT ORDER:
            # 1. First unsubscribe (sends None to queue)
            self.unsubscribe(subscriber_id)

            # 2. Then close generator
            await generator.aclose()

            debug(f"Cleanup done for subscriber {subscriber_id}")

