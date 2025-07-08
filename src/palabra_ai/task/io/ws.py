from dataclasses import dataclass
from dataclasses import field
from dataclasses import KW_ONLY
from typing import Optional

from palabra_ai.task.io.base import Io
from websockets.asyncio.client import connect as ws_connect, ClientConnection


@dataclass
class WsIo(Io):
    _: KW_ONLY
    ws: Optional[ClientConnection] = field(default=None, init=False)
    _ws_cm: Optional[object] = field(default=None, init=False)

    @property
    def dsn(self) -> str:
        return f"{self.credentials.ws_url}?token={self.credentials.jwt_token}"

    async def boot(self):
        """Start WebSocket connection"""
        # Create context manager and enter it
        self._ws_cm = ws_connect(self.dsn)
        self.ws = await self._ws_cm.__aenter__()

        # Verify connection is ready
        await self.ws.ping()

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