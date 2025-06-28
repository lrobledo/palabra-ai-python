import asyncio
from typing import Any

from palabra_ai.util.logger import debug


async def receive(q, timeout: int | float | None = None) -> dict[str, Any] | None:
    if timeout is None:
        try:
            return await q.get()
        except asyncio.CancelledError:
            debug("WebSocketClient receive cancelled")
            raise
    try:
        return await asyncio.wait_for(q.get(), timeout=timeout)
    except TimeoutError:
        return None
    except asyncio.CancelledError:
        debug("WebSocketClient receive with timeout cancelled")
        raise


def mark_received(q):
    q.task_done()
