import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from app.core.config import get_settings
from app.core.connection_manager import manager

router = APIRouter(tags=["results"])
logger = logging.getLogger("electoral_system.ws")
settings = get_settings()


@router.websocket("/ws/results")
async def results_stream(websocket: WebSocket) -> None:
    origin = websocket.headers.get("origin")
    await websocket.accept()

    if settings.allowed_origins and origin not in settings.allowed_origins:
        logger.warning("Rejected websocket from disallowed origin: %s", origin)
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    accepted = await manager.connect(websocket)
    if not accepted:
        await websocket.close(code=1013)  # Try Again Later
        return

    try:
        while True:
            # Client never sends data on this channel; this only detects disconnects.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(websocket)