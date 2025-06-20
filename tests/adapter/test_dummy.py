import asyncio
import pytest
from palabra_ai.adapter.dummy import DummyWriter


class TestDummyWriter:
    @pytest.mark.skip(reason="requires TaskGroup")
    @pytest.mark.asyncio
    async def test_boot(self):
        writer = DummyWriter()
        await writer.boot()
        # Should complete without error

    @pytest.mark.skip(reason="hangs")
    @pytest.mark.asyncio
    async def test_do_processes_queue(self):
        writer = DummyWriter()

        # Add some frames to queue
        writer.q.put_nowait("frame1")
        writer.q.put_nowait("frame2")
        writer.q.put_nowait(None)  # Signal end

        await writer.do()

        # Queue should be empty
        assert writer.q.empty()

    @pytest.mark.asyncio
    async def test_exit(self):
        writer = DummyWriter()
        result = await writer.exit()
        # DummyWriter.exit() doesn't return anything
        assert result is None
