import asyncio
import pytest
from unittest.mock import MagicMock, patch
from palabra_ai.task.monitor import RtMonitor
from palabra_ai.config import Config


class TestRtMonitorCoverage:
    @pytest.mark.asyncio
    async def test_do_timeout(self):
        """Test handling TimeoutError in do() method"""
        cfg = MagicMock(spec=Config)
        rt = MagicMock()
        q = asyncio.Queue()
        rt.out_foq.subscribe.return_value = q

        monitor = RtMonitor(cfg, rt)

        # Set stopper after a short delay to exit the loop
        async def set_stopper():
            await asyncio.sleep(0.15)
            monitor.stopper.set()

        # Run both concurrently
        await asyncio.gather(
            monitor.do(),
            set_stopper(),
            return_exceptions=True
        )

        # The timeout branch should have been hit at least once
