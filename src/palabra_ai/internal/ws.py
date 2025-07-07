import asyncio
import json
import typing as tp
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass

from websockets.asyncio.client import connect as ws_connect
from websockets.exceptions import ConnectionClosed

from palabra_ai.base.enum import Channel
from palabra_ai.base.enum import Direction
from palabra_ai.base.message import Dbg
from palabra_ai.base.message import EndTaskMessage
from palabra_ai.base.message import Message
from palabra_ai.constant import WS_TIMEOUT
from palabra_ai.util.fanout_queue import FanoutQueue
from palabra_ai.util.logger import debug, error

@dataclass
class Ws:
    def __init__(
        self,
        tg: asyncio.TaskGroup,
        uri: str,
        token: str,
    ):
        from palabra_ai.base.task_event import TaskEvent
        self.tg = tg
        self._uri = f"{uri}?token={token}"
        self._websocket = None
        self._keep_running = True
        self.in_foq = FanoutQueue()
        self.out_foq = FanoutQueue()
        self._task = None
        self.ready = TaskEvent()

    async def connect(self):
        self._task = self.tg.create_task(self.join(), name="Ws:join")
        await self.ready

    async def join(self):
        while self._keep_running:
            try:
                async with ws_connect(self._uri) as websocket:
                    self._websocket = websocket


                    out_task = self.tg.create_task(self.out_task(), name="Ws:out")
                    in_task = self.tg.create_task(self.in_task(), name="Ws:in")

                    +self.ready # noqa

                    done, pending = await asyncio.wait(
                        [out_task, in_task],
                        return_when=asyncio.FIRST_EXCEPTION,
                    )

                    for task in pending:
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            debug("Task cancelled")
                            self._keep_running = False
            except asyncio.CancelledError:
                debug("Ws join cancelled")
                self._keep_running = False
                raise
            except ConnectionClosed as e:
                if not self._keep_running:
                    debug(f"Connection closed during shutdown: {e}")
                else:
                    error(f"Connection closed with error: {e}")
            except Exception as e:
                error(f"Connection error: {e}")
            finally:
                if self._keep_running:
                    debug(f"Reconnecting to {self._uri}")
                    try:
                        await asyncio.sleep(1)
                    except asyncio.CancelledError:
                        debug("Ws reconnect sleep cancelled")
                        self._keep_running = False
                        raise
                else:
                    debug("WebSocket client shutting down gracefully")
                    break

    async def in_task(self):
        async with self.in_foq.receiver(str(id(self))+"_ws_in") as to_ws_msgs:
            async for to_ws_msg in to_ws_msgs:
                try:
                    await self._websocket.send(to_ws_msg.model_dump())
                    if not self._keep_running or not self._websocket:
                        debug(f"Ws.in_task() stopped")
                        break
                except asyncio.CancelledError:
                    debug("Ws.in_task() cancelled")
                    raise
                except Exception as e:
                    error(f"Ws.in_task() error: {e}")
                    break

    async def out_task(self):
        raw_msg = "n/a"
        while self._keep_running and self._websocket:
            try:
                async for raw_msg in self._websocket:
                    debug(f"Ws.out: {raw_msg}")
                    dbg = Dbg(Channel.WS, Direction.OUT)
                    msg = Message.decode(raw_msg, dbg=dbg)
                    self.out_foq.publish(msg)
            except asyncio.CancelledError:
                debug("Ws.out_task() cancelled")
                raise
            except Exception as e:
                error(f"Ws.out_task() error: [{type(e)} {e}], {raw_msg}")
                raise

    def send(self, msg: Message):
        return self.in_foq.publish(msg)

    async def close(self, wait_sec: int = 3) -> None:
        if not self._keep_running:
            return

        self._keep_running = False

        try:
            self.send(EndTaskMessage(force=True))
            await asyncio.sleep(wait_sec)
        except asyncio.CancelledError:
            debug("Ws close cancelled during send/wait")

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        if self._websocket:
            try:
                await self._websocket.close()
            except asyncio.CancelledError:
                debug("Ws websocket close cancelled")
                # Don't retry on cancel
            except Exception as e:
                error(f"Error closing websocket: {e}")
