"""Shared cache generations; callers own scopes and invalidation policy."""

from app.infrastructure.redis import RedisClient


def generation_key(context: str, scope_id: str) -> str:
    return f"cinelog:cache-generation:{context}:{scope_id}"


async def get_generation(client: RedisClient, context: str, scope_id: str) -> int:
    value = await client.hget(generation_key(context, scope_id), "value")
    return int(value) if value is not None else 0


async def bump_generation(client: RedisClient, context: str, scope_id: str) -> int:
    return await client.hincrby(generation_key(context, scope_id), "value")
