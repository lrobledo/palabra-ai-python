import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from palabra_ai.task.stat import Stat


class TestStat:
    @pytest.mark.asyncio
    async def test_boot(self):
        manager = MagicMock()
        stat = Stat(manager)
        await stat.boot()  # Should complete without error

    @pytest.mark.asyncio
    async def test_exit(self):
        manager = MagicMock()
        stat = Stat(manager)

        # Mock sleep to avoid waiting
        with patch('asyncio.sleep', new_callable=AsyncMock):
            await stat.exit()

    def test_banner_property(self):
        manager = MagicMock()
        manager.tasks = [
            MagicMock(_state=["🚀", "🟢"]),
            MagicMock(_state=["🚀"]),
            MagicMock(_state=[])
        ]

        stat = Stat(manager)
        banner = stat._banner

        assert banner == "🟢🚀⭕"

    def test_show_banner(self):
        manager = MagicMock()
        stat = Stat(manager)

        # Just verify it doesn't crash
        stat.show_banner()

    @pytest.mark.asyncio
    async def test_banner_cancelled(self):
        manager = MagicMock()
        manager.tasks = []
        stat = Stat(manager)
        stat.sub_tg = MagicMock()

        # Create a task that gets cancelled quickly
        async def cancel_soon():
            await asyncio.sleep(0.01)
            raise asyncio.CancelledError()

        with patch.object(stat, 'banner', side_effect=cancel_soon):
            task = MagicMock()
            stat.sub_tg.create_task.return_value = task

            result = stat.run_banner()
            assert result == task
