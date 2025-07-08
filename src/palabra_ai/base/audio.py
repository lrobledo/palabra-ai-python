import numpy as np
from livekit.rtc import AudioFrame as RtcAudioFrame

class AudioFrame:
    """Lightweight AudioFrame replacement with __slots__ for performance"""
    __slots__ = ('data', 'sample_rate', 'num_channels', 'samples_per_channel')

    def __init__(self, data: np.ndarray | bytes, sample_rate: int = 48000,
                 num_channels: int = 1, samples_per_channel: int | None = None):
        if isinstance(data, bytes):
            # Convert bytes to numpy array
            self.data = np.frombuffer(data, dtype=np.int16)
        else:
            self.data = data

        self.sample_rate = sample_rate
        self.num_channels = num_channels

        if samples_per_channel is None:
            self.samples_per_channel = len(self.data) // num_channels
        else:
            self.samples_per_channel = samples_per_channel


    def __repr__(self):
        return f"AudioFrame(samples={self.samples_per_channel}, rate={self.sample_rate}, ch={self.num_channels})"


    @classmethod
    def from_rtc(cls, frame: RtcAudioFrame) -> "AudioFrame":
        """Create AudioFrame from LiveKit's RtcAudioFrame"""
        return cls(
            data=frame.data,
            sample_rate=frame.sample_rate,
            num_channels=frame.num_channels,
            samples_per_channel=frame.samples_per_channel
        )

    @classmethod
    def from_ws(cls, raw_msg: dict, sample_rate: int, num_channels: int) -> "AudioFrame":
        raise NotImplementedError()

    def to_rtc(self) -> RtcAudioFrame:
        return RtcAudioFrame(
            data=self.data,
            sample_rate=self.sample_rate,
            num_channels=self.num_channels,
            samples_per_channel=self.samples_per_channel
        )

    def to_ws(self) -> dict:
        raise NotImplementedError("WebSocket serialization not implemented yet")