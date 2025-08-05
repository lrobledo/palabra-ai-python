import asyncio
import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch
import numpy as np
from palabra_ai.task.adapter.file import FileReader, FileWriter
from palabra_ai.task.base import TaskEvent
from palabra_ai.audio import AudioFrame, AudioBuffer
import tempfile
import os


class TestFileReader:
    """Test FileReader class"""
    
    def test_init_with_existing_file(self, tmp_path):
        """Test initialization with existing file"""
        test_file = tmp_path / "test.wav"
        test_file.write_bytes(b"dummy data")
        
        reader = FileReader(path=test_file)
        assert reader.path == test_file
        assert reader._pcm_data is None
        assert reader._position == 0
    
    def test_init_with_string_path(self, tmp_path):
        """Test initialization with string path"""
        test_file = tmp_path / "test.wav"
        test_file.write_bytes(b"dummy data")
        
        reader = FileReader(path=str(test_file))
        assert reader.path == test_file
    
    def test_init_with_nonexistent_file(self):
        """Test initialization with non-existent file"""
        with pytest.raises(FileNotFoundError) as exc_info:
            FileReader(path="/nonexistent/file.wav")
        
        assert "File not found" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_boot_success(self, tmp_path):
        """Test successful boot"""
        test_file = tmp_path / "test.wav"
        test_file.write_bytes(b"dummy audio data")
        
        reader = FileReader(path=test_file)
        reader.cfg = MagicMock()
        reader.cfg.mode.sample_rate = 16000
        
        mock_pcm_data = b"converted pcm data"
        
        with patch('palabra_ai.task.adapter.file.read_from_disk', new_callable=AsyncMock) as mock_read:
            with patch('palabra_ai.task.adapter.file.convert_any_to_pcm16') as mock_convert:
                with patch('palabra_ai.task.adapter.file.debug') as mock_debug:
                    mock_read.return_value = b"dummy audio data"
                    mock_convert.return_value = mock_pcm_data
                    
                    await reader.boot()
                    
                    mock_read.assert_called_once_with(test_file)
                    mock_convert.assert_called_once_with(b"dummy audio data", sample_rate=16000)
                    assert reader._pcm_data == mock_pcm_data
                    assert mock_debug.call_count >= 3
    
    @pytest.mark.asyncio
    async def test_boot_conversion_error(self, tmp_path):
        """Test boot with conversion error"""
        test_file = tmp_path / "test.wav"
        test_file.write_bytes(b"dummy audio data")
        
        reader = FileReader(path=test_file)
        reader.cfg = MagicMock()
        reader.cfg.mode.sample_rate = 16000
        
        with patch('palabra_ai.task.adapter.file.read_from_disk', new_callable=AsyncMock) as mock_read:
            with patch('palabra_ai.task.adapter.file.convert_any_to_pcm16') as mock_convert:
                with patch('palabra_ai.task.adapter.file.error') as mock_error:
                    mock_read.return_value = b"dummy audio data"
                    mock_convert.side_effect = RuntimeError("Conversion failed")
                    
                    with pytest.raises(RuntimeError):
                        await reader.boot()
                    
                    mock_error.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_read_normal(self, tmp_path):
        """Test normal read operation"""
        test_file = tmp_path / "test.wav"
        test_file.write_bytes(b"dummy")
        
        reader = FileReader(path=test_file)
        reader._pcm_data = b"test audio data"
        reader.ready = TaskEvent()
        +reader.ready
        
        # Read first chunk
        chunk = await reader.read(5)
        assert chunk == b"test "
        assert reader._position == 5
        
        # Read second chunk
        chunk = await reader.read(5)
        assert chunk == b"audio"
        assert reader._position == 10
    
    @pytest.mark.asyncio
    async def test_read_at_eof(self, tmp_path):
        """Test read at EOF"""
        test_file = tmp_path / "test.wav"
        test_file.write_bytes(b"dummy")
        
        reader = FileReader(path=test_file)
        reader._pcm_data = b"test"
        reader._position = 4  # At end
        reader.ready = TaskEvent()
        +reader.ready
        reader.eof = TaskEvent()
        
        with patch('palabra_ai.task.adapter.file.debug') as mock_debug:
            chunk = await reader.read(5)
            assert chunk is None
            assert reader.eof.is_set()
            mock_debug.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_read_partial(self, tmp_path):
        """Test reading partial data at end"""
        test_file = tmp_path / "test.wav"
        test_file.write_bytes(b"dummy")
        
        reader = FileReader(path=test_file)
        reader._pcm_data = b"test data"
        reader._position = 5  # At "data"
        reader.ready = TaskEvent()
        +reader.ready
        
        chunk = await reader.read(10)
        assert chunk == b"data"
        assert reader._position == 9
    
    @pytest.mark.asyncio
    async def test_exit_with_eof(self, tmp_path):
        """Test exit when EOF reached"""
        test_file = tmp_path / "test.wav"
        test_file.write_bytes(b"dummy")
        
        reader = FileReader(path=test_file)
        reader.eof = TaskEvent()
        +reader.eof
        reader._position = 100
        
        with patch('palabra_ai.task.adapter.file.debug') as mock_debug:
            await reader.exit()
            
            # Should log EOF reached
            assert any("reached EOF" in str(call) for call in mock_debug.call_args_list)
    
    @pytest.mark.asyncio
    async def test_exit_without_eof(self, tmp_path):
        """Test exit when EOF not reached"""
        test_file = tmp_path / "test.wav"
        test_file.write_bytes(b"dummy")
        
        reader = FileReader(path=test_file)
        reader.eof = TaskEvent()
        reader._position = 50
        
        with patch('palabra_ai.task.adapter.file.debug') as mock_debug:
            await reader.exit()
            
            # Should log stopped without EOF
            assert any("without reaching EOF" in str(call) for call in mock_debug.call_args_list)


class TestFileWriter:
    """Test FileWriter class"""
    
    def test_init_with_path(self, tmp_path):
        """Test initialization with path"""
        output_file = tmp_path / "output" / "test.wav"
        
        writer = FileWriter(path=output_file)
        assert writer.path == output_file
        assert writer.delete_on_error is False
        # Parent directory should be created
        assert output_file.parent.exists()
    
    def test_init_with_delete_on_error(self, tmp_path):
        """Test initialization with delete_on_error flag"""
        output_file = tmp_path / "test.wav"
        
        writer = FileWriter(path=output_file, delete_on_error=True)
        assert writer.delete_on_error is True
    
    @pytest.mark.asyncio
    async def test_exit_success(self, tmp_path):
        """Test successful exit with data"""
        output_file = tmp_path / "test.wav"
        
        writer = FileWriter(path=output_file)
        writer.ab = MagicMock()
        writer.ab.to_wav_bytes.return_value = b"WAV file data"
        
        with patch('palabra_ai.task.adapter.file.write_to_disk', new_callable=AsyncMock) as mock_write:
            with patch('palabra_ai.task.adapter.file.debug') as mock_debug:
                result = await writer.exit()
                
                assert result == b"WAV file data"
                writer.ab.to_wav_bytes.assert_called_once()
                mock_write.assert_called_once_with(output_file, b"WAV file data")
                assert mock_debug.call_count >= 3
    
    @pytest.mark.asyncio
    async def test_exit_no_data(self, tmp_path):
        """Test exit with no data"""
        output_file = tmp_path / "test.wav"
        
        writer = FileWriter(path=output_file)
        writer.ab = MagicMock()
        writer.ab.to_wav_bytes.return_value = b""
        
        with patch('palabra_ai.task.adapter.file.warning') as mock_warning:
            with patch('palabra_ai.task.adapter.file.debug'):
                result = await writer.exit()
                
                assert result == b""
                mock_warning.assert_called_once_with("No WAV data generated")
    
    @pytest.mark.asyncio
    async def test_exit_cancelled(self, tmp_path):
        """Test exit when cancelled"""
        output_file = tmp_path / "test.wav"
        output_file.write_bytes(b"existing data")
        
        writer = FileWriter(path=output_file, delete_on_error=True)
        writer.ab = MagicMock()
        writer.ab.to_wav_bytes.side_effect = asyncio.CancelledError()
        
        with patch('palabra_ai.task.adapter.file.warning') as mock_warning:
            with pytest.raises(asyncio.CancelledError):
                await writer.exit()
            
            mock_warning.assert_called_once()
            # File should be deleted
            assert not output_file.exists()
    
    @pytest.mark.asyncio
    async def test_exit_error(self, tmp_path):
        """Test exit with error"""
        output_file = tmp_path / "test.wav"
        output_file.write_bytes(b"existing data")
        
        writer = FileWriter(path=output_file, delete_on_error=True)
        writer.ab = MagicMock()
        writer.ab.to_wav_bytes.side_effect = RuntimeError("WAV conversion failed")
        
        with patch('palabra_ai.task.adapter.file.error') as mock_error:
            with pytest.raises(RuntimeError):
                await writer.exit()
            
            mock_error.assert_called()
            # File should be deleted
            assert not output_file.exists()
    
    def test_delete_on_error_success(self, tmp_path):
        """Test _delete_on_error when file exists"""
        output_file = tmp_path / "test.wav"
        output_file.write_bytes(b"data")
        
        writer = FileWriter(path=output_file, delete_on_error=True)
        
        writer._delete_on_error()
        
        assert not output_file.exists()
    
    def test_delete_on_error_no_file(self, tmp_path):
        """Test _delete_on_error when file doesn't exist"""
        output_file = tmp_path / "nonexistent.wav"
        
        writer = FileWriter(path=output_file, delete_on_error=True)
        
        # Should not raise error
        writer._delete_on_error()
    
    def test_delete_on_error_disabled(self, tmp_path):
        """Test _delete_on_error when delete_on_error is False"""
        output_file = tmp_path / "test.wav"
        output_file.write_bytes(b"data")
        
        writer = FileWriter(path=output_file, delete_on_error=False)
        
        writer._delete_on_error()
        
        # File should still exist
        assert output_file.exists()
    
    def test_delete_on_error_permission_error(self, tmp_path):
        """Test _delete_on_error with permission error"""
        output_file = tmp_path / "test.wav"
        output_file.write_bytes(b"data")
        
        writer = FileWriter(path=output_file, delete_on_error=True)
        
        with patch.object(Path, 'unlink', side_effect=PermissionError("No permission")):
            with patch('palabra_ai.task.adapter.file.error') as mock_error:
                with pytest.raises(PermissionError):
                    writer._delete_on_error()
                
                mock_error.assert_called_once()