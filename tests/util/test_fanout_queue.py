import asyncio
import pytest
from palabra_ai.util.fanout_queue import FanoutQueue


class TestFanoutQueue:
    def test_publish_with_none(self):
        foq = FanoutQueue()
        subscriber = "test"
        q = foq.subscribe(subscriber)

        # Publish None should put None in queue
        foq.publish(None)
        assert q.get_nowait() is None
