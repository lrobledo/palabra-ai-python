from __future__ import annotations

import asyncio

from loguru import logger

from palabra_ai.config import SLEEP_INTERVAL_DEFAULT


async def handle_cancellation(coro, warning_msg: str):
    """Handle cancellation with logging."""
    try:
        return await coro
    except asyncio.CancelledError:
        logger.warning(warning_msg)
        raise


async def run_until_stopped(process) -> None:
    """Run process until stopped by stopper signal."""
    while not process.stopper:
        await asyncio.sleep(SLEEP_INTERVAL_DEFAULT)
    logger.debug(f"{process.__class__.__name__} stopping by stopper signal")
