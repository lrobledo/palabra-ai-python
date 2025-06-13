import asyncio
import io
from collections.abc import Awaitable, Callable
from typing import Union

from palabra_ai.base.message import TranscriptionMessage

T_ON_TRANSCRIPTION = Union[
    Callable[[TranscriptionMessage], None],
    Callable[[TranscriptionMessage], Awaitable[None]],
]

T_IN_PCM = Union[
    "palabra_ai.base.adapter.Reader",
    asyncio.Queue,
    io.BytesIO,
]

T_OUT_PCM = Union[
    "palabra_ai.base.adapter.Writer",
    asyncio.Queue,
    io.BytesIO,
]
