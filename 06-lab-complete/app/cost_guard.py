"""
Cost guard (tiêu chí 8) — cộng dồn chi phí LLM vào Redis, vượt budget → 402.

Key Redis có ngày / tháng trong tên  (cost:<user>:2026-11-25,  cost:<user>:2026-11)
→ sang ngày / tháng mới tự ra key mới = budget tự reset, không cần cron job.
TTL đặt một lần (nx=True) để Redis tự dọn key cũ.

Luồng: check_budget() TRƯỚC khi gọi LLM (đã tiêu ≥ budget → 402, không tốn tiền gọi LLM),
record_cost() SAU khi gọi LLM với số token thật. Cộng bằng INCRBYFLOAT nên nguyên tử, nhiều
worker cùng cộng không bị mất số. Giới hạn của cách này: request cuối cùng có thể làm tổng
vượt budget một chút (chi phí chỉ biết sau khi gọi), request kế tiếp mới bị chặn.
"""
from datetime import datetime, timezone

import redis
from fastapi import HTTPException

from app.config import settings
from app.redis_client import r

DAY_TTL = 2 * 24 * 3600
MONTH_TTL = 32 * 24 * 3600


def _keys(user: str) -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    return f"cost:{user}:{now:%Y-%m-%d}", f"cost:{user}:{now:%Y-%m}"


def estimate_tokens(text: str) -> int:
    """Ước lượng thô ~1.3 token / từ. Với LLM thật nên lấy số từ trường `usage` của response."""
    return max(1, round(len(text.split()) * 1.3))


def check_budget(user: str) -> None:
    """Gọi TRƯỚC khi gọi LLM. Hết budget ngày (hoặc tháng) → 402."""
    day_key, month_key = _keys(user)
    try:
        spent_day, spent_month = (float(v or 0) for v in r.mget(day_key, month_key))
    except redis.RedisError:
        raise HTTPException(status_code=503, detail="Cost guard unavailable (Redis)")

    if spent_day >= settings.daily_budget_usd:
        raise HTTPException(status_code=402, detail={
            "error": "Daily budget exceeded", "period": "day",
            "spent_usd": round(spent_day, 6), "budget_usd": settings.daily_budget_usd})
    monthly = settings.monthly_budget_usd
    if monthly is not None and spent_month >= monthly:
        raise HTTPException(status_code=402, detail={
            "error": "Monthly budget exceeded", "period": "month",
            "spent_usd": round(spent_month, 6), "budget_usd": monthly})


def record_cost(user: str, input_tokens: int, output_tokens: int) -> float:
    """Gọi SAU khi gọi LLM. Cộng chi phí request vào tổng ngày + tháng, trả về chi phí request."""
    cost = (input_tokens / 1000 * settings.price_input_per_1k
            + output_tokens / 1000 * settings.price_output_per_1k)
    day_key, month_key = _keys(user)
    try:
        pipe = r.pipeline(transaction=True)
        pipe.incrbyfloat(day_key, cost)
        pipe.expire(day_key, DAY_TTL, nx=True)
        pipe.incrbyfloat(month_key, cost)
        pipe.expire(month_key, MONTH_TTL, nx=True)
        pipe.execute()
    except redis.RedisError:
        raise HTTPException(status_code=503, detail="Cost guard unavailable (Redis)")
    return round(cost, 8)
