from unittest.mock import AsyncMock

import pytest
from redis.exceptions import RedisError

from app.services import rate_limit_service
from app.services.rate_limit_service import RateLimitExceeded


def test_rate_limit_key_does_not_contain_raw_identifier():
    identifier = "user@example.com"

    key = rate_limit_service._rate_limit_key("login-account", identifier)

    assert key.startswith("rate-limit:login-account:")
    assert identifier not in key


async def test_request_within_limit_is_allowed(monkeypatch):
    redis_client = AsyncMock()
    redis_client.eval.return_value = [5, 12]
    monkeypatch.setattr(rate_limit_service, "_redis_client", redis_client)

    await rate_limit_service.enforce_rate_limit(
        "login-ip",
        "127.0.0.1",
        5,
    )

    redis_client.eval.assert_awaited_once()


async def test_exceeded_limit_uses_actual_redis_ttl(monkeypatch):
    redis_client = AsyncMock()
    redis_client.eval.return_value = [6, 5]
    monkeypatch.setattr(rate_limit_service, "_redis_client", redis_client)

    with pytest.raises(RateLimitExceeded) as error:
        await rate_limit_service.enforce_rate_limit(
            "login-ip",
            "127.0.0.1",
            5,
        )

    assert error.value.retry_after == 5


async def test_retry_after_is_at_least_one_second(monkeypatch):
    redis_client = AsyncMock()
    redis_client.eval.return_value = [6, 0]
    monkeypatch.setattr(rate_limit_service, "_redis_client", redis_client)

    with pytest.raises(RateLimitExceeded) as error:
        await rate_limit_service.enforce_rate_limit(
            "login-ip",
            "127.0.0.1",
            5,
        )

    assert error.value.retry_after == 1


async def test_redis_failure_does_not_block_request(monkeypatch):
    redis_client = AsyncMock()
    redis_client.eval.side_effect = RedisError("Redis unavailable")
    monkeypatch.setattr(rate_limit_service, "_redis_client", redis_client)

    await rate_limit_service.enforce_rate_limit(
        "login-ip",
        "127.0.0.1",
        5,
    )


async def test_close_rate_limiter_closes_redis_client(monkeypatch):
    redis_client = AsyncMock()
    monkeypatch.setattr(rate_limit_service, "_redis_client", redis_client)

    await rate_limit_service.close_rate_limiter()

    redis_client.aclose.assert_awaited_once_with()
