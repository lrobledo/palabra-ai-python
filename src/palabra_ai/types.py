# from __future__ import annotations
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, TypeAlias, Union

from palabra_ai.base.message import TranscriptionMessage

if TYPE_CHECKING:
    from palabra_ai.base.adapter import Reader, Writer

T_ON_TRANSCRIPTION = Union[
    Callable[[TranscriptionMessage], None],
    Callable[[TranscriptionMessage], Awaitable[None]],
]

T_READER: TypeAlias = "Reader"
T_WRITER: TypeAlias = "Writer"
