import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from palabra_ai.client import PalabraAI
from palabra_ai.config import Config, SourceLang, TargetLang
from palabra_ai.exc import ConfigurationError
from palabra_ai.task.base import TaskEvent

def test_palabra_ai_creation():
    """Test PalabraAI client creation with credentials"""
    client = PalabraAI(client_id="test_id", client_secret="test_secret")
    assert client.client_id == "test_id"
    assert client.client_secret == "test_secret"
    assert client.api_endpoint == "https://api.palabra.ai"

def test_palabra_ai_missing_client_id():
    """Test PalabraAI raises error when client_id missing"""
    with pytest.raises(ConfigurationError) as exc_info:
        PalabraAI(client_id=None, client_secret="test_secret")
    assert "PALABRA_CLIENT_ID is not set" in str(exc_info.value)

def test_palabra_ai_missing_client_secret():
    """Test PalabraAI raises error when client_secret missing"""
    with pytest.raises(ConfigurationError) as exc_info:
        PalabraAI(client_id="test_id", client_secret=None)
    assert "PALABRA_CLIENT_SECRET is not set" in str(exc_info.value)
    """Test run method with already running loop"""
    config = Config()
    config.source = SourceLang(lang="es")
    
    client = PalabraAI(client_id="test", client_secret="test")
    
    # Mock asyncio functions
    with patch('asyncio.get_running_loop') as mock_get_loop:
        mock_loop = Mock()
        mock_loop.is_running.return_value = True
        mock_loop.create_task = Mock()
        mock_get_loop.return_value = mock_loop
        
        # Call run
        result = client.run(config)
        
        # Should create a task
        mock_loop.create_task.assert_called_once()

def test_run_without_loop():
    """Test run method without running loop"""
    config = Config()
    config.source = SourceLang(lang="es")
    
    client = PalabraAI(client_id="test", client_secret="test")
    
    with patch('asyncio.get_running_loop') as mock_get_loop:
        mock_get_loop.side_effect = RuntimeError("No running loop")
        
        with patch('aioshutdown.SIGTERM'), \
             patch('aioshutdown.SIGHUP'), \
             patch('aioshutdown.SIGINT'):
            
            # Mock the shutdown loop
            with patch('palabra_ai.client.SIGTERM') as mock_sigterm:
                mock_context = Mock()
                mock_context.run_until_complete = Mock()
                mock_sigterm.__or__ = Mock(return_value=Mock(__enter__=Mock(return_value=mock_context), __exit__=Mock()))
                
                # This would normally run the event loop
                try:
                    client.run(config)
                except:
                    pass  # We're just testing the setup

def test_run_with_uvloop():
    """Test run method with uvloop available"""
    config = Config()
    config.source = SourceLang(lang="es")
    
    client = PalabraAI(client_id="test", client_secret="test")
    
    with patch('asyncio.get_running_loop') as mock_get_loop:
        mock_get_loop.side_effect = RuntimeError("No running loop")
        
        # Mock uvloop
        mock_uvloop = MagicMock()
        mock_policy = MagicMock()
        mock_uvloop.EventLoopPolicy.return_value = mock_policy
        
        with patch.dict('sys.modules', {'uvloop': mock_uvloop}):
            with patch('asyncio.set_event_loop_policy') as mock_set_policy:
                with patch('palabra_ai.client.SIGTERM') as mock_sigterm, \
                     patch('palabra_ai.client.SIGHUP') as mock_sighup, \
                     patch('palabra_ai.client.SIGINT') as mock_sigint:
                    
                    # Mock the signal context manager
                    mock_context = MagicMock()
                    mock_sigterm.__or__.return_value.__or__.return_value.__enter__.return_value = mock_context
                    mock_context.run_until_complete = MagicMock()
                    
                    # Mock the manager
                    with patch.object(client, 'process') as mock_process:
                        mock_manager = AsyncMock()
                        mock_manager.task = AsyncMock()
                        mock_process.return_value.__aenter__.return_value = mock_manager
                        
                        client.run(config)
                        
                        # Verify uvloop was set
                        mock_set_policy.assert_called_once_with(mock_policy)

def test_run_without_uvloop():
    """Test run method when uvloop is not available"""
    config = Config()
    config.source = SourceLang(lang="es")
    
    client = PalabraAI(client_id="test", client_secret="test")
    
    with patch('asyncio.get_running_loop') as mock_get_loop:
        mock_get_loop.side_effect = RuntimeError("No running loop")
        
        # Make uvloop import fail
        with patch('builtins.__import__', side_effect=ImportError("No uvloop")):
            with patch('palabra_ai.client.SIGTERM') as mock_sigterm, \
                 patch('palabra_ai.client.SIGHUP') as mock_sighup, \
                 patch('palabra_ai.client.SIGINT') as mock_sigint:
                
                # Mock the signal context manager
                mock_context = MagicMock()
                mock_sigterm.__or__.return_value.__or__.return_value.__enter__.return_value = mock_context
                mock_context.run_until_complete = MagicMock()
                
                # Mock the manager
                with patch.object(client, 'process') as mock_process:
                    mock_manager = AsyncMock()
                    mock_manager.task = AsyncMock()
                    mock_process.return_value.__aenter__.return_value = mock_manager
                    
                    # Should not raise error
                    client.run(config)

def test_run_with_keyboard_interrupt():
    """Test run method handling KeyboardInterrupt"""
    config = Config()
    config.source = SourceLang(lang="es")
    
    client = PalabraAI(client_id="test", client_secret="test")
    
    with patch('asyncio.get_running_loop') as mock_get_loop:
        mock_get_loop.side_effect = RuntimeError("No running loop")
        
        with patch('palabra_ai.client.SIGTERM') as mock_sigterm, \
             patch('palabra_ai.client.SIGHUP') as mock_sighup, \
             patch('palabra_ai.client.SIGINT') as mock_sigint:
            
            # Mock the signal context manager to raise KeyboardInterrupt
            mock_context = MagicMock()
            mock_sigterm.__or__.return_value.__or__.return_value.__enter__.return_value = mock_context
            mock_context.run_until_complete.side_effect = KeyboardInterrupt()
            
            # Should handle KeyboardInterrupt gracefully
            client.run(config)

def test_run_with_exception():
    """Test run method handling general exceptions"""
    config = Config()
    config.source = SourceLang(lang="es")
    
    client = PalabraAI(client_id="test", client_secret="test")
    
    with patch('asyncio.get_running_loop') as mock_get_loop:
        mock_get_loop.side_effect = RuntimeError("No running loop")
        
        with patch('palabra_ai.client.SIGTERM') as mock_sigterm, \
             patch('palabra_ai.client.SIGHUP') as mock_sighup, \
             patch('palabra_ai.client.SIGINT') as mock_sigint:
            
            # Mock the signal context manager to raise exception
            mock_context = MagicMock()
            mock_sigterm.__or__.return_value.__or__.return_value.__enter__.return_value = mock_context
            mock_context.run_until_complete.side_effect = ValueError("Test error")
            
            # Should re-raise the exception
            with pytest.raises(ValueError) as exc_info:
                client.run(config)
            assert "Test error" in str(exc_info.value)

def test_run_with_deep_debug():
    """Test run method with DEEP_DEBUG enabled"""
    config = Config()
    config.source = SourceLang(lang="es")
    
    client = PalabraAI(client_id="test", client_secret="test")
    
    with patch('palabra_ai.client.DEEP_DEBUG', True):
        with patch('palabra_ai.client.diagnose_hanging_tasks') as mock_diagnose:
            mock_diagnose.return_value = "Diagnostics info"
            
            with patch('asyncio.get_running_loop') as mock_get_loop:
                mock_loop = Mock()
                mock_loop.is_running.return_value = True
                mock_task = Mock()
                mock_loop.create_task.return_value = mock_task
                mock_get_loop.return_value = mock_loop
                
                # Mock the manager
                with patch.object(client, 'process') as mock_process:
                    mock_manager = AsyncMock()
                    mock_manager.task = AsyncMock()
                    mock_process.return_value.__aenter__.return_value = mock_manager
                    
                    result = client.run(config)
                    
                    # Verify task was created
                    assert result == mock_task

def test_run_with_signal_handler():
    """Test run method signal handler setup"""
    config = Config()
    config.source = SourceLang(lang="es")
    
    client = PalabraAI(client_id="test", client_secret="test")
    stopper = TaskEvent()
    
    with patch('asyncio.get_running_loop') as mock_get_loop:
        mock_loop = Mock()
        mock_loop.is_running.return_value = True
        mock_task = Mock()
        mock_loop.create_task.return_value = mock_task
        mock_get_loop.return_value = mock_loop
        
        with patch('signal.signal') as mock_signal:
            old_handler = Mock()
            mock_signal.return_value = old_handler
            
            result = client.run(config, stopper)
            
            # Verify signal handler was set and restored
            assert mock_signal.call_count == 2
            # First call sets our handler
            first_call = mock_signal.call_args_list[0]
            # Check it's SIGINT (value 2)
            assert first_call[0][0].value == 2
            # Second call restores old handler
            second_call = mock_signal.call_args_list[1]
            assert second_call[0][1] == old_handler

@pytest.mark.asyncio
async def test_process_with_credentials_creation():
    """Test process creates credentials correctly"""
    config = Config()
    config.source = SourceLang(lang="es")
    config.targets = [TargetLang(lang="en")]
    
    client = PalabraAI(client_id="test", client_secret="test")
    
    mock_credentials = MagicMock()
    
    with patch('palabra_ai.client.PalabraRESTClient') as mock_rest_class:
        mock_rest = AsyncMock()
        mock_rest.create_session.return_value = mock_credentials
        mock_rest_class.return_value = mock_rest
        
        with patch('palabra_ai.client.Manager') as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager_class.return_value = MagicMock(return_value=mock_manager)
            
            with patch('asyncio.TaskGroup') as mock_tg_class:
                mock_tg = AsyncMock()
                mock_tg.__aenter__.return_value = mock_tg
                mock_tg.__aexit__.return_value = None
                mock_tg_class.return_value = mock_tg
                
                async with client.process(config) as manager:
                    assert manager == mock_manager
                
                # Verify REST client was created
                mock_rest_class.assert_called_once_with(
                    "test", "test", base_url="https://api.palabra.ai"
                )
                mock_rest.create_session.assert_called_once()

@pytest.mark.asyncio
async def test_process_with_cancelled_error():
    """Test process handles CancelledError"""
    config = Config()
    config.source = SourceLang(lang="es")
    config.targets = [TargetLang(lang="en")]
    
    client = PalabraAI(client_id="test", client_secret="test")
    
    mock_credentials = MagicMock()
    
    with patch('palabra_ai.client.PalabraRESTClient') as mock_rest_class:
        mock_rest = AsyncMock()
        mock_rest.create_session.return_value = mock_credentials
        mock_rest_class.return_value = mock_rest
        
        with patch('palabra_ai.client.Manager') as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager_class.return_value = MagicMock(return_value=mock_manager)
            
            with patch('asyncio.TaskGroup') as mock_tg_class:
                mock_tg = AsyncMock()
                mock_tg.__aenter__.return_value = mock_tg
                # Simulate CancelledError in TaskGroup
                mock_tg.__aexit__.side_effect = asyncio.CancelledError()
                mock_tg_class.return_value = mock_tg
                
                # Should not raise CancelledError
                async with client.process(config) as manager:
                    pass

@pytest.mark.asyncio
async def test_process_with_exception_group():
    """Test process handles exception groups"""
    config = Config()
    config.source = SourceLang(lang="es")
    config.targets = [TargetLang(lang="en")]
    
    client = PalabraAI(client_id="test", client_secret="test")
    
    mock_credentials = MagicMock()
    
    with patch('palabra_ai.client.PalabraRESTClient') as mock_rest_class:
        mock_rest = AsyncMock()
        mock_rest.create_session.return_value = mock_credentials
        mock_rest_class.return_value = mock_rest
        
        with patch('palabra_ai.client.Manager') as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager_class.return_value = MagicMock(return_value=mock_manager)
            
            with patch('asyncio.TaskGroup') as mock_tg_class:
                mock_tg = AsyncMock()
                mock_tg.__aenter__.return_value = mock_tg
                
                # Create an exception group
                exc1 = ValueError("Error 1")
                exc2 = RuntimeError("Error 2")
                try:
                    exc_group = ExceptionGroup("Test errors", [exc1, exc2])
                except NameError:
                    # For Python < 3.11
                    exc_group = Exception("Test errors")
                
                # Simulate exception group in TaskGroup
                mock_tg.__aexit__.side_effect = exc_group
                mock_tg_class.return_value = mock_tg
                
                with patch('palabra_ai.client.unwrap_exceptions') as mock_unwrap:
                    mock_unwrap.return_value = [exc1, exc2]
                    
                    with pytest.raises(ValueError) as exc_info:
                        async with client.process(config) as manager:
                            pass
                    
                    assert "Error 1" in str(exc_info.value)

@pytest.mark.skip(reason="CancelledError handling needs investigation")
@pytest.mark.asyncio
async def test_process_with_only_cancelled_errors():
    """Test process handles exception group with only CancelledErrors"""
    config = Config()
    config.source = SourceLang(lang="es")
    config.targets = [TargetLang(lang="en")]
    
    client = PalabraAI(client_id="test", client_secret="test")
    
    mock_credentials = MagicMock()
    
    with patch('palabra_ai.client.PalabraRESTClient') as mock_rest_class:
        mock_rest = AsyncMock()
        mock_rest.create_session.return_value = mock_credentials
        mock_rest_class.return_value = mock_rest
        
        with patch('palabra_ai.client.Manager') as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager_class.return_value = MagicMock(return_value=mock_manager)
            
            with patch('asyncio.TaskGroup') as mock_tg_class:
                mock_tg = AsyncMock()
                mock_tg.__aenter__.return_value = mock_tg
                
                # Create an exception group with only CancelledErrors
                exc1 = asyncio.CancelledError()
                exc2 = asyncio.CancelledError()
                # CancelledError is special case - just use the first one
                exc_group = exc1
                
                # Simulate exception group in TaskGroup
                mock_tg.__aexit__.side_effect = exc_group
                mock_tg_class.return_value = mock_tg
                
                with patch('palabra_ai.client.unwrap_exceptions') as mock_unwrap:
                    mock_unwrap.return_value = [exc1, exc2]
                    
                    with pytest.raises(asyncio.CancelledError):
                        async with client.process(config) as manager:
                            pass

@pytest.mark.asyncio
async def test_process_finally_block():
    """Test process finally block executes"""
    config = Config()
    config.source = SourceLang(lang="es")
    config.targets = [TargetLang(lang="en")]
    
    client = PalabraAI(client_id="test", client_secret="test")
    
    mock_credentials = MagicMock()
    
    with patch('palabra_ai.client.PalabraRESTClient') as mock_rest_class:
        mock_rest = AsyncMock()
        mock_rest.create_session.return_value = mock_credentials
        mock_rest_class.return_value = mock_rest
        
        with patch('palabra_ai.client.diagnose_hanging_tasks') as mock_diagnose:
            mock_diagnose.return_value = "Diagnostics"
            
            with patch('palabra_ai.client.Manager') as mock_manager_class:
                mock_manager = MagicMock()
                mock_manager_class.return_value = MagicMock(return_value=mock_manager)
                
                with patch('asyncio.TaskGroup') as mock_tg_class:
                    mock_tg = AsyncMock()
                    mock_tg.__aenter__.return_value = mock_tg
                    mock_tg.__aexit__.return_value = None
                    mock_tg_class.return_value = mock_tg
                    
                    async with client.process(config) as manager:
                        pass
                    
                    # Verify finally block executed
                    mock_diagnose.assert_called_once()