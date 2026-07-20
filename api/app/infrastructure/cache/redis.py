"""Async Redis client lifecycle."""

from redis.asyncio import Redis

from app.shared.config import get_settings

_client: Redis | None = None


def get_redis() -> Redis:
    global _client
    if _client is None:
        _client = Redis.from_url(get_settings().redis_url, decode_responses=True)
    return _client


async def check_redis() -> None:
    if not await get_redis().ping():
        raise ConnectionError("Redis ping returned false")


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
    _client = None
