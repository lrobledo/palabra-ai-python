import asyncio
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager

from loguru import logger


@asynccontextmanager
async def diet(msg: str = "", last_word: Callable | None = None):
    """
    DIE-in-Time
    Context manager to handle cancellation gracefully
    """
    if last_word:
        if isinstance(last_word, Awaitable):
            pass
        elif callable(last_word):
            last_word = last_word()
            assert isinstance(last_word, Awaitable)
        else:
            raise TypeError("last_word must be a callable or an Awaitable")
    try:
        yield
    except asyncio.CancelledError:
        logger.warning(f"!!! CANCEL: {msg}", stacklevel=3)
        try:
            await last_word
        except asyncio.CancelledError:
            logger.warning("Last word coroutine cancelled")
            raise
        raise


defer = diet
