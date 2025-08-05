import asyncio
import io
import pytest
from palabra_ai.task.adapter.buffer import BufferReader, BufferWriter
from palabra_ai.task.base import TaskEvent
from unittest.mock import MagicMock, AsyncMock, patch


class TestBufferReader:
    """Test BufferReader class"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.test_data = b"test audio data with more content for testing"
        self.buffer = io.BytesIO(self.test_data)
        self.reader = BufferReader(buffer=self.buffer)
    
    def test_init(self):
        """Test initialization"""
        assert self.reader._position == 0
        assert self.reader._buffer_size == len(self.test_data)
        # Buffer position should be restored
        assert self.buffer.tell() == 0
    
    def test_init_with_buffer_position(self):
        """Test initialization with buffer at non-zero position"""
        self.buffer.seek(10)
        reader = BufferReader(buffer=self.buffer)
        assert reader._position == 0
        assert reader._buffer_size == len(self.test_data)
        # Buffer position should be restored
        assert self.buffer.tell() == 10
    
    @pytest.mark.asyncio
    async def test_boot(self):
        """Test boot method"""
        with patch('palabra_ai.task.adapter.buffer.debug') as mock_debug:
            await self.reader.boot()
            mock_debug.assert_called_once_with(f"{self.reader.name} contains {len(self.test_data)} bytes")
    
    @pytest.mark.asyncio
    async def test_exit_normal(self):
        """Test exit method when EOF reached"""
        +self.reader.eof  # Set EOF
        with patch('palabra_ai.task.adapter.buffer.debug') as mock_debug:
            await self.reader.exit()
            mock_debug.assert_called_once_with(f"{self.reader.name} exiting")
    
    @pytest.mark.asyncio
    async def test_exit_without_eof(self):
        """Test exit method when EOF not reached"""
        # self.reader.eof is already False by default
        with patch('palabra_ai.task.adapter.buffer.debug') as mock_debug:
            with patch('palabra_ai.task.adapter.buffer.warning') as mock_warning:
                await self.reader.exit()
                mock_debug.assert_called_once()
                mock_warning.assert_called_once_with(f"{self.reader.name} stopped without reaching EOF")
    
    @pytest.mark.asyncio
    async def test_read_normal(self):
        """Test normal read operation"""
        self.reader.ready = TaskEvent()
        +self.reader.ready  # Set it
        
        # Read first chunk
        chunk = await self.reader.read(5)
        assert chunk == b"test "
        assert self.reader._position == 5
        
        # Read second chunk
        chunk = await self.reader.read(10)
        assert chunk == b"audio data"
        assert self.reader._position == 15
    
    @pytest.mark.asyncio
    async def test_read_eof(self):
        """Test read at EOF"""
        self.reader.ready = TaskEvent()
        +self.reader.ready  # Set it
        self.reader._position = len(self.test_data)
        
        with patch('palabra_ai.task.adapter.buffer.debug') as mock_debug:
            chunk = await self.reader.read(5)
            assert chunk is None
            assert self.reader.eof.is_set()
            mock_debug.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_read_partial_at_end(self):
        """Test reading partial data at end of buffer"""
        self.reader.ready = TaskEvent()
        +self.reader.ready  # Set it
        self.reader._position = len(self.test_data) - 5
        
        chunk = await self.reader.read(10)
        assert chunk == b"sting"
        assert self.reader._position == len(self.test_data)
    
    @pytest.mark.asyncio
    async def test_read_large_chunk(self):
        """Test reading larger chunk than available"""
        self.reader.ready = TaskEvent()
        +self.reader.ready  # Set it
        
        chunk = await self.reader.read(1000)
        assert chunk == self.test_data
        assert self.reader._position == len(self.test_data)
    
    @pytest.mark.asyncio
    async def test_multiple_reads_until_eof(self):
        """Test multiple reads until EOF"""
        self.reader.ready = TaskEvent()
        +self.reader.ready  # Set it
        
        chunks = []
        while True:
            chunk = await self.reader.read(10)
            if chunk is None:
                break
            chunks.append(chunk)
        
        assert b"".join(chunks) == self.test_data
        assert self.reader.eof.is_set()


class TestBufferWriter:
    """Test BufferWriter class"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.buffer = io.BytesIO()
        self.writer = BufferWriter(buffer=self.buffer)
        self.writer.ab = MagicMock()
    
    @pytest.mark.asyncio
    async def test_boot(self):
        """Test boot method"""
        # Mock parent boot
        with patch('palabra_ai.task.adapter.base.BufferedWriter.boot', new_callable=AsyncMock) as mock_parent_boot:
            await self.writer.boot()
            
            mock_parent_boot.assert_called_once()
            self.writer.ab.replace_buffer.assert_called_once_with(self.buffer)
    
    @pytest.mark.asyncio
    async def test_exit(self):
        """Test exit method (no-op)"""
        await self.writer.exit()
        # Should complete without error
    
    def test_buffer_writer_inherits_from_buffered_writer(self):
        """Test that BufferWriter inherits from BufferedWriter"""
        from palabra_ai.task.adapter.base import BufferedWriter
        assert issubclass(BufferWriter, BufferedWriter)
    
    def test_buffer_writer_dataclass(self):
        """Test that BufferWriter is a dataclass"""
        from dataclasses import is_dataclass
        assert is_dataclass(BufferWriter)
    
    def test_buffer_writer_accepts_buffer(self):
        """Test that BufferWriter accepts buffer parameter"""
        buffer = io.BytesIO()
        writer = BufferWriter(buffer=buffer)
        assert writer.buffer is buffer