import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock
from palabra_ai.task.realtime import Realtime
from palabra_ai.config import Config


class TestRealtimeCoverage:
    @pytest.mark.asyncio
    async def test_do_with_stopper(self):
        """Test do() exits when stopper is set"""
        cfg = MagicMock(spec=Config)
        creds = MagicMock()
        rt = Realtime(cfg, creds)

        rt.stopper.set()
        await rt.do()
        # Should exit immediately without error

    @pytest.mark.asyncio
    async def test_reroute_timeout(self):
        """Test _reroute handles timeout"""
        cfg = MagicMock(spec=Config)
        creds = MagicMock()
        rt = Realtime(cfg, creds)

        from_q = asyncio.Queue()
        to_foq = MagicMock()

        # Set stopper after delay
        async def stop_soon():
            await asyncio.sleep(0.1)
            rt.stopper.set()

        await asyncio.gather(
            rt._reroute("ws", "in", from_q, [to_foq]),
            stop_soon(),
            return_exceptions=True
        )
