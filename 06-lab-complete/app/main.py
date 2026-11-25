"""
Production AI Agent — Part 6 Final Project

Chạy:   uvicorn app.main:app --workers 2
Chấm:   python check_production_ready.py
"""
import json
import logging
import sys
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.auth import verify_api_key
from app.config import settings
from app.cost_guard import check_budget, estimate_tokens, record_cost
from app.rate_limiter import check_rate_limit
from app.redis_client import r, redis_healthy
from utils.mock_llm import ask as llm_ask


# ─────────────────────────────────────────────────────────
# Structured logging (tiêu chí 10): mỗi dòng log = 1 JSON object
# ─────────────────────────────────────────────────────────
class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(timespec="milliseconds"),
            "lvl": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        entry.update(getattr(record, "fields", {}))
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False, default=str)


def _setup_logger() -> logging.Logger:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    log = logging.getLogger("agent")
    log.handlers = [handler]
    log.setLevel(settings.log_level)
    log.propagate = False      # không lẫn với format text của root / uvicorn
    return log


logger = _setup_logger()


def log_event(event: str, level: int = logging.INFO, **fields):
    logger.log(level, event, extra={"fields": fields})


# ─────────────────────────────────────────────────────────
# Lifespan + graceful shutdown (tiêu chí 11)
#
# Không tự đăng ký signal handler: uvicorn đã bắt SIGTERM → ngừng nhận kết nối mới →
# chờ request đang chạy xong → chạy phần sau `yield` → thoát exit code 0.
# Ở đây chỉ đánh dấu not-ready (để /ready trả 503, load balancer ngừng gửi traffic)
# và đóng kết nối Redis.
# ─────────────────────────────────────────────────────────
STATE = {"ready": False, "in_flight": 0}
START_TIME = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    log_event("startup", environment=settings.environment, version=settings.app_version,
              port=settings.port, redis_ok=redis_healthy())
    STATE["ready"] = True
    yield
    STATE["ready"] = False
    log_event("shutdown", in_flight=STATE["in_flight"])
    try:
        r.close()
    except Exception:
        pass
    log_event("shutdown_complete")


app = FastAPI(title="Production AI Agent", version=settings.app_version, lifespan=lifespan)


@app.middleware("http")
async def access_log(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
    started = time.perf_counter()
    STATE["in_flight"] += 1
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        response.headers["X-Request-ID"] = request_id
        return response
    except Exception:
        logger.exception("unhandled_error", extra={"fields": {"request_id": request_id}})
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})
    finally:
        STATE["in_flight"] -= 1
        if request.url.path not in ("/health", "/ready"):   # probe gọi liên tục, không ghi log
            log_event("request", method=request.method, path=request.url.path, status=status,
                      ms=round((time.perf_counter() - started) * 1000, 1), request_id=request_id)


# ─────────────────────────────────────────────────────────
# Health / readiness (tiêu chí 4, 5)
# ─────────────────────────────────────────────────────────
@app.get("/health")
def health():
    """Liveness: luôn 200 khi process còn chạy — KHÔNG phụ thuộc Redis,
    nếu không Redis chết sẽ làm platform restart agent liên tục mà chẳng sửa được gì."""
    return {
        "status": "ok",
        "version": settings.app_version,
        "environment": settings.environment,
        "uptime_seconds": round(time.time() - START_TIME, 1),
    }


@app.get("/ready")
def ready():
    """Readiness: 200 khi nhận được traffic; 503 khi đang tắt hoặc Redis không kết nối được."""
    if not STATE["ready"]:
        return JSONResponse(status_code=503, content={"ready": False, "reason": "shutting down"})
    if not redis_healthy():
        return JSONResponse(status_code=503, content={"ready": False, "reason": "redis unavailable"})
    return {"ready": True, "redis": "ok"}


# ─────────────────────────────────────────────────────────
# Business endpoint
# ─────────────────────────────────────────────────────────
class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    user_id: str | None = Field(default=None, max_length=64)


@app.post("/ask")
def ask(body: AskRequest, key_id: str = Depends(verify_api_key)):
    # def (không async): mock LLM dùng time.sleep blocking → chạy trong threadpool,
    # không chặn event loop (bài học Exercise 5.2)
    check_rate_limit(key_id)                       # 429
    user = body.user_id or key_id
    check_budget(user)                             # 402 — trước khi tốn tiền gọi LLM

    answer = llm_ask(body.question)

    input_tokens, output_tokens = estimate_tokens(body.question), estimate_tokens(answer)
    cost = record_cost(user, input_tokens, output_tokens)
    log_event("llm_call", key_id=key_id, user=user, input_tokens=input_tokens,
              output_tokens=output_tokens, cost_usd=cost)
    return {
        "question": body.question,
        "answer": answer,
        "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens, "cost_usd": cost},
    }
