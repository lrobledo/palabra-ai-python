# Suppress Pydantic deprecation warning in tests
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning, message=".*class-based `config`.*")

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Configure pytest-asyncio
pytest_plugins = ['pytest_asyncio']


@pytest.fixture
def mock_av():
    """Mock av library."""
    with patch("palabra_ai.internal.audio.av") as mock:
        # Mock AudioFormat
        mock.AudioFormat.return_value = MagicMock()

        # Mock AudioResampler
        resampled_frame = MagicMock()
        resampled_frame.samples = 1024
        mock.AudioResampler.return_value.resample.return_value = [resampled_frame]

        # Mock filter
        mock.filter.Graph.return_value.configure = MagicMock()

        # Mock AVError
        mock.AVError = Exception

        yield mock


@pytest.fixture
def mock_sounddevice():
    """Mock sounddevice."""
    with patch("palabra_ai.internal.device.sd") as mock:
        # Create proper device list
        devices = [
            {"name": "test", "max_input_channels": 2, "max_output_channels": 2, "index": 0}
        ]

        # Mock query_devices to return a proper list
        mock.query_devices.return_value = devices

        # Mock query_hostapis
        mock.query_hostapis.return_value = [{"name": "test", "devices": [0]}]

        # Create stream mock
        stream = MagicMock()
        stream.latency = 0.01
        stream.active = True
        mock.RawInputStream.return_value.__enter__.return_value = stream
        mock.RawOutputStream.return_value.__enter__.return_value = stream

        yield mock


@pytest.fixture
def mock_livekit():
    """Mock livekit rtc."""
    with patch("palabra_ai.internal.webrtc.rtc") as mock:
        # Mock audio components
        mock.AudioSource.return_value = MagicMock()
        mock.LocalAudioTrack.create_audio_track.return_value = MagicMock()
        mock.AudioFrame.create.return_value = MagicMock(data=b"\x00" * 1024)

        # Mock Room class entirely
        mock_room_instance = AsyncMock()
        mock_room_instance.connect = AsyncMock()
        mock_room_instance.disconnect = AsyncMock()
        mock_room_instance.local_participant = MagicMock()
        mock_room_instance.local_participant.publish_track = AsyncMock(return_value=MagicMock(sid="test"))
        mock_room_instance.remote_participants = {}
        mock_room_instance.name = ""
        mock_room_instance._room = None

        # Make Room return our mock instance
        mock.Room = MagicMock(return_value=mock_room_instance)

        # Mock RoomOptions
        mock.RoomOptions = MagicMock

        yield mock


@pytest.fixture
def mock_websockets():
    """Mock websockets."""
    with patch("palabra_ai.internal.ws.websockets") as mock:
        ws = AsyncMock()
        ws.send = AsyncMock()
        ws.recv = AsyncMock(return_value='{"message_type": "test", "data": "{}"}')
        ws.close = AsyncMock()
        ws.open = True
        mock.connect.return_value.__aenter__.return_value = ws

        # Mock exceptions
        mock.exceptions.WebSocketException = Exception

        yield mock


@pytest.fixture
def mock_aiohttp():
    """Mock aiohttp for REST client."""
    with patch("palabra_ai.internal.rest.aiohttp") as mock:
        resp = AsyncMock()
        resp.raise_for_status = MagicMock()
        resp.json = AsyncMock(return_value={
            "ok": True,
            "data": {
                "publisher": ["token1"],
                "subscriber": ["token2"],
                "room_name": "test",
                "stream_url": "wss://test",
                "control_url": "wss://control"
            }
        })

        session = AsyncMock()
        session.post = AsyncMock(return_value=resp)
        session.close = AsyncMock()
        mock.ClientSession.return_value = session
        yield mock


@pytest.fixture
async def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# Utility fixtures for common test objects
@pytest.fixture
def audio_bytes():
    """Sample PCM16 audio data."""
    return b"\x00\x01" * 512  # 1024 bytes


@pytest.fixture
def mock_queue():
    """Async queue with common setup."""
    q = asyncio.Queue()
    q.put_nowait(b"test_data")
    return q
