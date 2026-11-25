"""
Config — 12-Factor: mọi cấu hình đọc từ biến môi trường (tiêu chí 9).

Giá trị mặc định chỉ để chạy local cho tiện. Secret (AGENT_API_KEY) KHÔNG có mặc định:
thiếu thì mọi request /ask bị 401, thay vì chạy với một key đoán được.
Danh sách đầy đủ các biến nằm trong .env.example.
"""
import os
from dataclasses import dataclass, field


def _env_float(name: str, default: str) -> float:
    return float(os.getenv(name, default))


def _env_optional_float(name: str):
    value = os.getenv(name, "").strip()
    return float(value) if value else None


@dataclass
class Settings:
    port: int = field(default_factory=lambda: int(os.getenv("PORT", "8000")))
    environment: str = field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO").upper())
    app_version: str = field(default_factory=lambda: os.getenv("APP_VERSION", "1.0.0"))

    agent_api_key: str = field(default_factory=lambda: os.getenv("AGENT_API_KEY", ""))
    redis_url: str = field(default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379/0"))

    rate_limit_per_minute: int = field(default_factory=lambda: int(os.getenv("RATE_LIMIT_PER_MINUTE", "10")))
    daily_budget_usd: float = field(default_factory=lambda: _env_float("DAILY_BUDGET_USD", "1.0"))
    # Không đặt thì không giới hạn theo tháng
    monthly_budget_usd: float | None = field(default_factory=lambda: _env_optional_float("MONTHLY_BUDGET_USD"))

    # Giá USD / 1K token — để trong env để đổi giá / đổi model / tự định giá model local
    # mà không phải sửa code và build lại image
    price_input_per_1k: float = field(default_factory=lambda: _env_float("PRICE_INPUT_PER_1K", "0.00015"))
    price_output_per_1k: float = field(default_factory=lambda: _env_float("PRICE_OUTPUT_PER_1K", "0.0006"))


settings = Settings()
