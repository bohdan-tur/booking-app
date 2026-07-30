import hashlib

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import settings
from app.core.logger import logger

RATE_LIMIT_WINDOW_SECONDS = 60

_INCREMENT_SCRIPT = """
local count = redis.call("INCR", KEYS[1])
if count == 1 then
    redis.call("EXPIRE", KEYS[1], ARGV[1])
end
local ttl = redis.call("TTL", KEYS[1])
return {count, ttl}
"""

_redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)


class RateLimitExceeded(Exception):
    def __init__(self, retry_after: int):
        self.retry_after = retry_after
        super().__init__("Rate limit exceeded")


def _rate_limit_key(bucket: str, identifier: str) -> str:
    identifier_hash = hashlib.sha256(identifier.encode("utf-8")).hexdigest()
    return f"rate-limit:{bucket}:{identifier_hash}"


async def enforce_rate_limit(
    bucket: str,
    identifier: str,
    limit: int,
    *,
    window_seconds: int = RATE_LIMIT_WINDOW_SECONDS,
) -> None:
    key = _rate_limit_key(bucket, identifier)

    try:
        request_count, retry_after = await _redis_client.eval(
            _INCREMENT_SCRIPT,
            1,
            key,
            window_seconds,
        )
    except RedisError:
        logger.warning("Rate limiter is unavailable for bucket %s", bucket)
        return

    if int(request_count) > limit:
        raise RateLimitExceeded(retry_after=max(int(retry_after), 1))


async def close_rate_limiter() -> None:
    await _redis_client.aclose()
