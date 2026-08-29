import asyncio
import logging

from fastapi import WebSocket

logger = logging.getLogger("electoral_system.ws")

MAX_CONNECTIONS = 1000  # basic resource-exhaustion guard


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> bool:
        async with self._lock:
            if len(self._connections) >= MAX_CONNECTIONS:
                return False
            self._connections.add(websocket)
            return True

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(websocket)

    async def broadcast(self, message: str) -> None:
        async with self._lock:
            targets = list(self._connections)
        for ws in targets:
            try:
                await ws.send_text(message)
            except Exception:
                logger.warning("Dropping unresponsive websocket client")
                await self.disconnect(ws)


manager = ConnectionManager()