import asyncio
import pytest
from palabra_ai.util.fanout_queue import FanoutQueue


class TestFanoutQueueCoverage:
    def test_subscribe_existing_subscriber(self):
        """Test subscribing twice returns the same queue"""
        foq = FanoutQueue()
        subscriber = "test_subscriber"

        # First subscription
        q1 = foq.subscribe(subscriber)

        # Second subscription - should return same queue (line 25)
        q2 = foq.subscribe(subscriber)

        assert q1 is q2
        assert len(foq.subscribers) == 1

    def test_unsubscribe_existing(self):
        """Test unsubscribing an existing subscriber"""
        foq = FanoutQueue()
        subscriber = "test_subscriber"

        # Subscribe first
        foq.subscribe(subscriber)
        assert len(foq.subscribers) == 1

        # Unsubscribe (lines 28-29)
        foq.unsubscribe(subscriber)
        assert len(foq.subscribers) == 0

    def test_unsubscribe_non_existing(self):
        """Test unsubscribing a non-existing subscriber"""
        foq = FanoutQueue()

        # Unsubscribe non-existing - should not raise error
        foq.unsubscribe("non_existing")
        assert len(foq.subscribers) == 0
