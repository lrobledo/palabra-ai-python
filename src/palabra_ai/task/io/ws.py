from dataclasses import dataclass
from dataclasses import field
from dataclasses import KW_ONLY
from typing import Optional

from palabra_ai.base.enum import Channel
from palabra_ai.base.enum import Direction
from palabra_ai.base.message import Dbg
from palabra_ai.task.io.base import Io
from websockets.asyncio.client import connect as ws_connect, ClientConnection

from palabra_ai.util.orjson import to_json


@dataclass
class WsIo(Io):
    _: KW_ONLY
    ws: Optional[ClientConnection] = field(default=None, init=False)
    _ws_cm: Optional[object] = field(default=None, init=False)

    @property
    def dsn(self) -> str:
        return f"{self.credentials.ws_url}?token={self.credentials.jwt_token}"



    async def push_in_msg(self, msg: "Message"):
        dbg = Dbg(Channel.WS, Direction.IN)
        msg._dbg = dbg
        self.dbg(f"Pushing message: {msg!r}")
        self.in_msg_foq.publish(msg)

    async def in_msg_sender(self):
        async with self.in_msg_foq.receiver(self, self.stopper) as msgs:
            async for msg in msgs:
                if msg is None or self.stopper:
                    self.dbg("stopping in_msg_sender due to None or stopper")
                    return
                await self.ws.send(to_json(msg))

    async def ws_receiver(self):
        from palabra_ai.base.message import Message
        async for raw_msg in self.ws:
            if self.stopper or raw_msg is None:
                self.dbg("Stopping ws_receiver due to stopper or None message")
                return
            self.dbg(f"Received raw message: {raw_msg[:1000]}")

            msg = Message.decode(raw_msg)
            msg._dbg = Dbg(Channel.WS, Direction.OUT)
            self.out_msg_foq.publish(msg)


    async def boot(self):
        """Start WebSocket connection"""
        # Create context manager and enter it
        self._ws_cm = ws_connect(self.dsn)
        self.ws = await self._ws_cm.__aenter__()

        # Verify connection is ready
        await self.ws.ping()
        self.sub_tg.create_task(self.ws_receiver(), name="WsIo:receiver")
        self.sub_tg.create_task(self.in_msg_sender(), name=f"WsIo:in_msg_sender")
        await self.set_task()
        breakpoint()

    async def do(self):
        """Main work loop with already connected WebSocket"""

        out_task = self.tg.create_task(self.out_task(), name="Ws:out")
        in_task = self.tg.create_task(self.in_task(), name="Ws:in")

        await asyncio.gather(out_task, in_task)

    async def exit(self):
        """Clean up WebSocket connection"""
        if self._ws_cm and self.ws:
            await self._ws_cm.__aexit__(None, None, None)
        self.ws = None