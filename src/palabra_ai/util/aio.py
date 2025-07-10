from asyncio import wait_for

from palabra_ai.constant import BOOT_TIMEOUT, SHUTDOWN_TIMEOUT


async def boot(fn):
    return await wait_for(fn, timeout=BOOT_TIMEOUT)


async def shutdown(fn):
    return await wait_for(fn, timeout=SHUTDOWN_TIMEOUT)
