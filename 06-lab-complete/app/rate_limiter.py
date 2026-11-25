"""
Rate limiting (tiêu chí 7) — sliding window 60 giây, state trong Redis.

Mỗi API key có một sorted set  ratelimit:<fingerprint>,  member = 1 request, score = thời điểm.
Vì state nằm trong Redis nên mọi worker / instance dùng chung, restart agent vẫn còn.

Thứ tự lệnh: ZREMRANGEBYSCORE → ZADD → ZCARD → EXPIRE, gói trong MULTI (transaction) nên chạy
nguyên tử. Thêm request TRƯỚC rồi mới đếm: 2 request đến cùng lúc không thể cùng "lọt" như cách
đếm-rồi-mới-thêm. Bị chặn thì xoá lại request vừa thêm để request bị từ chối không chiếm chỗ.
"""
import math
import time
import uuid

import redis
from fastapi import HTTPException

from app.config import settings
from app.redis_client import r

WINDOW_SECONDS = 60


def check_rate_limit(key: str) -> None:
    """key: fingerprint của API key. Vượt giới hạn → 429 + Retry-After."""
    limit = settings.rate_limit_per_minute
    redis_key = f"ratelimit:{key}"
    now = time.time()
    member = f"{now:.6f}-{uuid.uuid4().hex[:8]}"

    try:
        pipe = r.pipeline(transaction=True)
        pipe.zremrangebyscore(redis_key, 0, now - WINDOW_SECONDS)
        pipe.zadd(redis_key, {member: now})
        pipe.zcard(redis_key)
        pipe.expire(redis_key, WINDOW_SECONDS + 1)
        _, _, count, _ = pipe.execute()

        if count <= limit:
            return

        r.zrem(redis_key, member)
        oldest = r.zrange(redis_key, 0, 0, withscores=True)
    except redis.RedisError:
        # Không có Redis thì không đếm được → từ chối an toàn thay vì cho qua không giới hạn
        raise HTTPException(status_code=503, detail="Rate limiter unavailable (Redis)")

    retry_after = WINDOW_SECONDS
    if oldest:
        retry_after = max(1, math.ceil(oldest[0][1] + WINDOW_SECONDS - now))
    raise HTTPException(
        status_code=429,
        detail={"error": "Rate limit exceeded", "limit": limit, "window_seconds": WINDOW_SECONDS,
                "retry_after_seconds": retry_after},
        headers={
            "Retry-After": str(retry_after),
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": "0",
        },
    )
