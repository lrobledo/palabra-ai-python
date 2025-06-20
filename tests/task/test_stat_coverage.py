import asyncio
import pytest
from unittest.mock import MagicMock, patch
from palabra_ai.task.stat import Stat


class TestStatCoverage:
    @pytest.mark.asyncio
    async def test_do_state_change(self):
        """Test do() when state changes"""
        manager = MagicMock()
        manager.tasks = [
            MagicMock(_state=["🚀"]),
            MagicMock(_state=[])
        ]

        stat = Stat(manager)

        # Change state during execution
        async def change_state():
            await asyncio.sleep(0.05)
            manager.tasks[0]._state.append("🟢")
            await asyncio.sleep(0.05)
            stat.stopper.set()

        with patch('palabra_ai.config.DEEP_DEBUG', False):
            await asyncio.gather(
                stat.do(),
                change_state(),
                return_exceptions=True
            )

    @pytest.mark.asyncio
    async def test_do_deep_debug(self):
        """Test do() with DEEP_DEBUG enabled"""
        manager = MagicMock()
        manager.tasks = []
        manager.cfg = MagicMock()
        manager.cfg.deep_debug = True

        stat = Stat(manager)

        async def stop_soon():
            await asyncio.sleep(0.1)
            stat.stopper.set()

        with patch('palabra_ai.config.DEEP_DEBUG', True):
            await asyncio.gather(
                stat.do(),
                stop_soon(),
                return_exceptions=True
            )
