import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import aiohttp
from palabra_ai.internal.rest import SessionCredentials, PalabraRESTClient
from palabra_ai.exc import ConfigurationError

class TestSessionCredentials:
    """Test SessionCredentials model"""
    
    def test_init_valid(self):
        """Test valid credentials initialization"""
        creds = SessionCredentials(
            publisher=["token123"],
            subscriber=["sub_token"],
            room_name="test_room",
            stream_url="rtc://example.com",
            control_url="ws://example.com"
        )
        
        assert creds.publisher == ["token123"]
        assert creds.subscriber == ["sub_token"]
        assert creds.room_name == "test_room"
        assert creds.stream_url == "rtc://example.com"
        assert creds.control_url == "ws://example.com"
    
    def test_init_missing_jwt_token(self):
        """Test error when JWT token missing"""
        with pytest.raises(ConfigurationError) as exc_info:
            SessionCredentials(
                publisher=[],
                subscriber=["sub_token"],
                room_name="test_room",
                stream_url="rtc://example.com",
                control_url="ws://example.com"
            )
        assert "Publisher token is missing" in str(exc_info.value)
    
    def test_init_missing_control_url(self):
        """Test error when control URL missing"""
        with pytest.raises(ConfigurationError) as exc_info:
            SessionCredentials(
                publisher=["token123"],
                subscriber=["sub_token"],
                room_name="test_room",
                stream_url="rtc://example.com",
                control_url=""
            )
        assert "Missing JWT token" in str(exc_info.value)
    
    def test_init_missing_stream_url(self):
        """Test error when stream URL missing"""
        with pytest.raises(ConfigurationError) as exc_info:
            SessionCredentials(
                publisher=["token123"],
                subscriber=["sub_token"],
                room_name="test_room",
                stream_url="",
                control_url="ws://example.com"
            )
        assert "Missing JWT token" in str(exc_info.value)
    
    def test_jwt_token_property(self):
        """Test jwt_token property"""
        creds = SessionCredentials(
            publisher=["token123", "token456"],
            subscriber=["sub_token"],
            room_name="test_room",
            stream_url="rtc://example.com",
            control_url="ws://example.com"
        )
        
        assert creds.jwt_token == "token123"
    
    def test_jwt_token_empty_publisher(self):
        """Test jwt_token with empty publisher list"""
        # Use valid initialization then test the property
        creds = SessionCredentials(
            publisher=["token123"],
            subscriber=["sub_token"],
            room_name="test_room",
            stream_url="rtc://example.com",
            control_url="ws://example.com"
        )
        
        # Manually set empty publisher to test the property
        object.__setattr__(creds, 'publisher', [])
        
        with pytest.raises(ConfigurationError) as exc_info:
            _ = creds.jwt_token
        assert "Publisher token is missing" in str(exc_info.value)
    
    def test_ws_url_property(self):
        """Test ws_url property"""
        creds = SessionCredentials(
            publisher=["token123"],
            subscriber=["sub_token"],
            room_name="test_room",
            stream_url="rtc://example.com",
            control_url="ws://example.com"
        )
        
        assert creds.ws_url == "ws://example.com"
    
    def test_ws_url_missing(self):
        """Test ws_url with missing control URL"""
        # Use valid initialization then test the property
        creds = SessionCredentials(
            publisher=["token123"],
            subscriber=["sub_token"],
            room_name="test_room",
            stream_url="rtc://example.com",
            control_url="ws://example.com"
        )
        
        # Manually set empty control_url to test the property
        object.__setattr__(creds, 'control_url', "")
        
        with pytest.raises(ConfigurationError) as exc_info:
            _ = creds.ws_url
        assert "Control (ws) URL is missing" in str(exc_info.value)
    
    def test_webrtc_url_property(self):
        """Test webrtc_url property"""
        creds = SessionCredentials(
            publisher=["token123"],
            subscriber=["sub_token"],
            room_name="test_room",
            stream_url="rtc://example.com",
            control_url="ws://example.com"
        )
        
        assert creds.webrtc_url == "rtc://example.com"
    
    def test_webrtc_url_missing(self):
        """Test webrtc_url with missing stream URL"""
        # Use valid initialization then test the property
        creds = SessionCredentials(
            publisher=["token123"],
            subscriber=["sub_token"],
            room_name="test_room",
            stream_url="rtc://example.com",
            control_url="ws://example.com"
        )
        
        # Manually set empty stream_url to test the property
        object.__setattr__(creds, 'stream_url', "")
        
        with pytest.raises(ConfigurationError) as exc_info:
            _ = creds.webrtc_url
        assert "Stream URL is missing" in str(exc_info.value)

class TestPalabraRESTClient:
    """Test PalabraRESTClient class"""
    
    def test_init(self):
        """Test client initialization"""
        client = PalabraRESTClient("client_id", "client_secret")
        
        assert client.client_id == "client_id"
        assert client.client_secret == "client_secret"
        assert client.base_url == "https://api.palabra.ai"
        assert client.timeout == 5
    
    def test_init_custom_params(self):
        """Test client initialization with custom parameters"""
        client = PalabraRESTClient(
            "client_id", 
            "client_secret", 
            timeout=10,
            base_url="https://custom.api.com"
        )
        
        assert client.timeout == 10
        assert client.base_url == "https://custom.api.com"
    
    @pytest.mark.asyncio
    async def test_create_session_success(self):
        """Test successful session creation"""
        client = PalabraRESTClient("client_id", "client_secret")
        
        # Mock response data
        response_data = {
            "ok": True,
            "data": {
                "publisher": ["token123"],
                "subscriber": ["sub_token"],
                "room_name": "test_room",
                "stream_url": "rtc://example.com",
                "control_url": "ws://example.com"
            }
        }
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value = mock_session
            
            mock_response = AsyncMock()
            mock_response.raise_for_status.return_value = None
            mock_response.json.return_value = response_data
            mock_session.post.return_value = mock_response
            
            with patch('ssl.create_default_context'), \
                 patch('aiohttp.TCPConnector'):
                
                result = await client.create_session()
                
                assert isinstance(result, SessionCredentials)
                assert result.publisher == ["token123"]
                assert result.room_name == "test_room"
                
                # Verify session was closed
                mock_session.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_session_custom_counts(self):
        """Test session creation with custom publisher/subscriber counts"""
        client = PalabraRESTClient("client_id", "client_secret")
        
        response_data = {
            "ok": True,
            "data": {
                "publisher": ["token123"],
                "subscriber": ["sub_token"],
                "room_name": "test_room",
                "stream_url": "rtc://example.com",
                "control_url": "ws://example.com"
            }
        }
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value = mock_session
            
            mock_response = AsyncMock()
            mock_response.raise_for_status.return_value = None
            mock_response.json.return_value = response_data
            mock_session.post.return_value = mock_response
            
            with patch('ssl.create_default_context'), \
                 patch('aiohttp.TCPConnector'):
                
                result = await client.create_session(publisher_count=2, subscriber_count=3)
                
                # Verify request was made with correct parameters
                mock_session.post.assert_called_once()
                call_args = mock_session.post.call_args
                assert call_args[1]["json"]["data"]["publisher_count"] == 2
                assert call_args[1]["json"]["data"]["subscriber_count"] == 3
    
    @pytest.mark.asyncio
    async def test_create_session_cancelled(self):
        """Test session creation cancelled"""
        client = PalabraRESTClient("client_id", "client_secret")
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value = mock_session
            mock_session.post.side_effect = asyncio.CancelledError()
            
            with patch('ssl.create_default_context'), \
                 patch('aiohttp.TCPConnector'), \
                 patch('palabra_ai.internal.rest.warning') as mock_warning:
                
                with pytest.raises(asyncio.CancelledError):
                    await client.create_session()
                
                mock_warning.assert_called_once_with("PalabraRESTClient create_session cancelled")
                mock_session.close.assert_called_once()
    
    @pytest.mark.skip(reason="Complex SSL error mocking, focus on simpler coverage first")
    @pytest.mark.asyncio
    async def test_create_session_ssl_error_macos(self):
        """Test SSL certificate error on macOS"""
        pass
    
    @pytest.mark.skip(reason="Complex SSL error mocking, focus on simpler coverage first")
    @pytest.mark.asyncio
    async def test_create_session_ssl_error_other_os(self):
        """Test SSL certificate error on non-macOS"""
        pass
    
    @pytest.mark.asyncio
    async def test_create_session_general_error(self):
        """Test general exception during session creation"""
        client = PalabraRESTClient("client_id", "client_secret")
        
        test_error = Exception("Test error")
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value = mock_session
            mock_session.post.side_effect = test_error
            
            with patch('ssl.create_default_context'), \
                 patch('aiohttp.TCPConnector'), \
                 patch('palabra_ai.internal.rest.error') as mock_error:
                
                with pytest.raises(Exception):
                    await client.create_session()
                
                mock_error.assert_called_with("Error creating session: Test error")
                mock_session.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_session_request_failed(self):
        """Test when API request fails"""
        client = PalabraRESTClient("client_id", "client_secret")
        
        response_data = {
            "ok": False,
            "error": "Invalid credentials"
        }
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value = mock_session
            
            mock_response = AsyncMock()
            mock_response.raise_for_status.return_value = None
            mock_response.json.return_value = response_data
            mock_session.post.return_value = mock_response
            
            with patch('ssl.create_default_context'), \
                 patch('aiohttp.TCPConnector'):
                
                with pytest.raises(AssertionError) as exc_info:
                    await client.create_session()
                
                assert "Request has failed" in str(exc_info.value)
                mock_session.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_session_http_error(self):
        """Test HTTP error response"""
        client = PalabraRESTClient("client_id", "client_secret")
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value = mock_session
            
            # Create a proper mock request info
            mock_request_info = MagicMock()
            mock_request_info.real_url = "https://api.palabra.ai/session-storage/sessions"
            
            # Mock the response that causes HTTP error
            http_error = aiohttp.ClientResponseError(
                request_info=mock_request_info, history=(), status=401, message="Unauthorized"
            )
            mock_session.post.side_effect = http_error
            
            with patch('ssl.create_default_context'), \
                 patch('aiohttp.TCPConnector'), \
                 patch('palabra_ai.internal.rest.error') as mock_error:
                
                with pytest.raises(aiohttp.ClientResponseError):
                    await client.create_session()
                
                mock_session.close.assert_called_once()