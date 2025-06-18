import asyncio
from asyncio import QueueFull

import pytest

from palabra_ai.util.fanout_queue import FanoutQueue, QueueFullError


class TestFanoutQueue:
    @pytest.mark.asyncio
    async def test_subscribe_and_publish(self):
        fanout = FanoutQueue()

        # Create subscribers
        sub1 = fanout.subscribe("sub1", maxsize=10)
        sub2 = fanout.subscribe("sub2", maxsize=10)

        # Publish message
        fanout.publish("test_message")

        # Both should receive
        msg1 = await sub1.get()
        msg2 = await sub2.get()

        assert msg1 == "test_message"
        assert msg2 == "test_message"

    @pytest.mark.asyncio
    async def test_unsubscribe(self):
        fanout = FanoutQueue()

        sub = fanout.subscribe("test", maxsize=10)
        assert "test" in fanout.subscribers

        fanout.unsubscribe("test")
        assert "test" not in fanout.subscribers

    @pytest.mark.asyncio
    async def test_publish_to_full_queue_with_fail(self):
        fanout = FanoutQueue()

        # Create subscriber with fail_on_full=True
        sub = fanout.subscribe("test", maxsize=1, fail_on_full=True)

        # Fill the queue
        fanout.publish("msg1")

        # This should raise QueueFull
        with pytest.raises(QueueFull):
            fanout.publish("msg2")

    def test_subscribers_property(self):
        fanout = FanoutQueue()

        # Initially empty
        assert len(fanout.subscribers) == 0

        # Add subscribers
        fanout.subscribe("sub1", maxsize=10)
        fanout.subscribe("sub2", maxsize=10)

        assert len(fanout.subscribers) == 2
        assert "sub1" in fanout.subscribers
        assert "sub2" in fanout.subscribers
