import asyncio
from unittest.mock import MagicMock

import pytest
from livekit import rtc


@pytest.fixture
def mock_audio_frame():
    """Mock rtc.AudioFrame."""
    frame = MagicMock(spec=rtc.AudioFrame)
    frame.data = MagicMock()
    frame.data.tobytes.return_value = b"\x00" * 1024
    frame.num_channels = 1
    frame.sample_rate = 48000
    return frame


@pytest.fixture
def credentials():
    """Mock session credentials."""
    from palabra_ai.internal.rest import SessionCredentials
    return SessionCredentials(
        publisher=["pub_token"],
        subscriber=["sub_token"],
        room_name="test_room",
        stream_url="wss://stream.test",
        control_url="wss://control.test"
    )


@pytest.fixture
def track_settings():
    """Mock AudioTrackSettings."""
    from palabra_ai.internal.webrtc import AudioTrackSettings
    return AudioTrackSettings(sample_rate=48000, num_channels=1)
