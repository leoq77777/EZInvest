"""Shared dependencies for dependency injection."""

from functools import lru_cache

from app.config import Settings, get_settings


def get_config() -> Settings:
    return get_settings()


@lru_cache
def get_redis_client():
    import redis.asyncio as aioredis

    settings = get_settings()
    return aioredis.from_url(settings.redis_url, decode_responses=True)
