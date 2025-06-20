import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch, mock_open
from palabra_ai.task.logger import Logger
from palabra_ai.config import Config
from pathlib import Path


class TestLoggerCoverage:
    @pytest.mark.asyncio
    async def test_consume_none_message(self):
        """Test _consume receiving None message"""
        cfg = MagicMock(spec=Config)
        cfg.log_file = Path("/tmp/test.log")
        cfg.trace_file = Path("/tmp/test.json")

        rt = MagicMock()
        rt.in_foq.subscribe.return_value = asyncio.Queue()
        rt.out_foq.subscribe.return_value = asyncio.Queue()

        logger = Logger(cfg, rt)

        q = asyncio.Queue()
        await q.put(None)

        # Should exit on None
        await logger._consume(q)

    @pytest.mark.asyncio
    async def test_consume_cancelled(self):
        """Test _consume when cancelled"""
        cfg = MagicMock(spec=Config)
        cfg.log_file = Path("/tmp/test.log")
        cfg.trace_file = Path("/tmp/test.json")

        rt = MagicMock()
        rt.in_foq.subscribe.return_value = asyncio.Queue()
        rt.out_foq.subscribe.return_value = asyncio.Queue()

        logger = Logger(cfg, rt)
        logger.stopper.set()

        q = asyncio.Queue()

        # Should exit when stopper is set
        await logger._consume(q)

    @pytest.mark.asyncio
    async def test_exit_with_file_read_error(self):
        """Test exit when log file read fails"""
        cfg = MagicMock(spec=Config)
        cfg.log_file = Path("/nonexistent/test.log")
        cfg.trace_file = Path("/tmp/test.json")
        cfg.debug = False

        rt = MagicMock()
        rt.in_foq.subscribe.return_value = asyncio.Queue()
        rt.out_foq.subscribe.return_value = asyncio.Queue()
        rt.in_foq.unsubscribe = MagicMock()
        rt.out_foq.unsubscribe = MagicMock()

        logger = Logger(cfg, rt)

        # Create proper async tasks instead of AsyncMock
        async def dummy_task():
            try:
                await asyncio.sleep(100)  # Sleep forever unless cancelled
            except asyncio.CancelledError:
                pass  # Expected when exit() cancels tasks

        logger._in_task = asyncio.create_task(dummy_task())
        logger._out_task = asyncio.create_task(dummy_task())

        # Create a proper mock for file operations
        m_open = mock_open()

        # Configure side effects for two open calls
        def open_side_effect(filename, *args, **kwargs):
            filename = str(filename)  # Convert Path to string
            if 'test.log' in filename:
                raise FileNotFoundError("Log file not found")
            else:
                return m_open(filename, *args, **kwargs)

        with patch('builtins.open', side_effect=open_side_effect):
            with patch('palabra_ai.util.sysinfo.get_system_info', return_value={"test": "info"}):
                with patch('palabra_ai.__version__', '1.0.0'):
                    await logger.exit()

        # Should handle error gracefully
        rt.in_foq.unsubscribe.assert_called_once()
        rt.out_foq.unsubscribe.assert_called_once()
