import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock
from palabra_ai.task.sender import SenderSourceAudio, BYTES_PER_SAMPLE
from palabra_ai.config import Config
from palabra_ai.internal.webrtc import AudioTrackSettings


class TestSenderCoverage:
    @pytest.mark.asyncio
    async def test_bytes_per_sample_constant(self):
        """Test BYTES_PER_SAMPLE constant is available"""
        assert BYTES_PER_SAMPLE == 2

    @pytest.mark.asyncio
    async def test_do_with_stopper(self):
        """Test do() exits when stopper is set"""
        cfg = MagicMock(spec=Config)
        rt = MagicMock()
        reader = MagicMock()
        reader.read = AsyncMock(side_effect=[b"data"])

        sender = SenderSourceAudio(cfg, rt, reader, {}, AudioTrackSettings())
        sender._track = MagicMock()
        sender._track.push = AsyncMock()
        sender.stopper.set()  # Set stopper

        await sender.do()

        # Should exit without reading
        reader.read.assert_not_called()
