import asyncio
import logging

from app.core.connection_manager import manager
from app.core.constants import RESULTS_CHANNEL
from app.core.redis_client import get_redis

logger = logging.getLogger("electoral_system.broadcaster")


async def run_broadcaster(stop_event: asyncio.Event) -> None:
    """Subscribes to Redis Pub/Sub and forwards results updates to all connected
    WebSocket clients. Runs as a background task in the API process — the worker
    process (separate container) publishes here after committing a vote."""
    redis = await get_redis()
    pubsub = redis.pubsub()
    await pubsub.subscribe(RESULTS_CHANNEL)
    logger.info("Subscribed to %s", RESULTS_CHANNEL)

    try:
        while not stop_event.is_set():
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message is None:
                continue
            await manager.broadcast(message["data"])
    finally:
        await pubsub.unsubscribe(RESULTS_CHANNEL)
        await pubsub.close()