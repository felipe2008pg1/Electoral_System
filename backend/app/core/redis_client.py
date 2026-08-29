from redis.asyncio import ConnectionPool, Redis
from app.core.config import get_settings

settings = get_settings()

_pool = ConnectionPool.from_url(settings.redis_url, max_connections=50, decode_responses=True)

async def get_redis() -> Redis:
    return Redis(connection_pool=_pool)