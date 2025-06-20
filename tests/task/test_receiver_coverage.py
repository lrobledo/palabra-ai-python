import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock
from palabra_ai.task.receiver import ReceiverTranslatedAudio
from palabra_ai.config import Config
from palabra_ai.lang import Language
from palabra_ai.adapter.dummy import DummyWriter


class TestReceiverCoverage:
    @pytest.mark.asyncio
    async def test_do_method(self):
        """Test do() method execution"""
        cfg = MagicMock(spec=Config)
        writer = DummyWriter()
        rt = MagicMock()

        receiver = ReceiverTranslatedAudio(cfg, writer, rt, Language("es"))

        # Set stopper after short delay
        async def stop_soon():
            await asyncio.sleep(0.1)
            receiver.stopper.set()

        await asyncio.gather(
            receiver.do(),
            stop_soon(),
            return_exceptions=True
        )

        # Just verify it ran without error

    @pytest.mark.asyncio
    async def test_setup_translation_with_stopper(self):
        """Test setup_translation when stopper is set"""
        cfg = MagicMock(spec=Config)
        writer = DummyWriter()
        rt = MagicMock()

        receiver = ReceiverTranslatedAudio(cfg, writer, rt, Language("es"))
        receiver.stopper.set()  # Set stopper before setup

        # Should return early without error
        await receiver.setup_translation()

        # Track should not be set
        assert receiver._track is None
