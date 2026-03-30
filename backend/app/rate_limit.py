from __future__ import annotations

import logging
import time

from fastapi import HTTPException

from app import database
from app.config import get_settings


logger = logging.getLogger(__name__)

try:
    import redis  # type: ignore
except ImportError:  # pragma: no cover
    redis = None


class RateLimiter:
    def __init__(self) -> None:
        settings = get_settings()
        self._redis_client = None
        if settings.redis_url and redis is not None:
            self._redis_client = redis.from_url(settings.redis_url, decode_responses=True)
        elif settings.redis_url:
            logger.warning("REDIS_URL is set but redis package is unavailable; falling back to sqlite-backed rate limiting.")

    def enforce(self, *, route_key: str, actor_key: str, limit: int, window_seconds: int) -> None:
        if self._redis_client is not None:
            self._enforce_with_redis(route_key=route_key, actor_key=actor_key, limit=limit, window_seconds=window_seconds)
            return
        self._enforce_with_sqlite(route_key=route_key, actor_key=actor_key, limit=limit, window_seconds=window_seconds)

    def _enforce_with_redis(self, *, route_key: str, actor_key: str, limit: int, window_seconds: int) -> None:
        window_start = int(time.time() // window_seconds)
        key = f"rl:{route_key}:{actor_key}:{window_start}"
        pipeline = self._redis_client.pipeline()
        pipeline.incr(key)
        pipeline.expire(key, window_seconds)
        current_count, _ = pipeline.execute()
        if int(current_count) > limit:
            self._raise_limit_error()

    def _enforce_with_sqlite(self, *, route_key: str, actor_key: str, limit: int, window_seconds: int) -> None:
        current_window = int(time.time() // window_seconds)
        bucket_key = f"{route_key}:{actor_key}"
        existing = database.get_rate_limit_window(bucket_key)

        if existing is None or existing[0] != current_window:
            database.reset_rate_limit_window(bucket_key=bucket_key, window_started_at=current_window)

        allowed, _ = database.advance_rate_limit_window(
            bucket_key=bucket_key,
            window_started_at=current_window,
            limit=limit,
        )
        if not allowed:
            self._raise_limit_error()

    def _raise_limit_error(self) -> None:
        raise HTTPException(
            status_code=429,
            detail={
                "code": "rate_limited",
                "message": "Too many requests. Please try again shortly.",
            },
        )