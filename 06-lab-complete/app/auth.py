"""
API Key authentication (tiêu chí 6).

  • Client gửi header  X-API-Key: <key>
  • Key phải trùng biến môi trường AGENT_API_KEY
  • Thiếu hoặc sai key → HTTP 401 (không phải 403 hay 422)
"""
import hashlib
import secrets

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from app.config import settings

# auto_error=False: tự trả 401 thay vì để FastAPI trả 403 khi thiếu header
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def key_fingerprint(api_key: str) -> str:
    """Định danh ngắn của key để dùng làm key Redis / log — không bao giờ lưu key thật."""
    return hashlib.sha256(api_key.encode()).hexdigest()[:16]


def verify_api_key(api_key: str | None = Security(api_key_header)) -> str:
    """Dependency cho /ask. Trả về fingerprint của key hợp lệ."""
    expected = settings.agent_api_key
    # compare_digest: so sánh thời gian không đổi, tránh đoán key qua timing
    if not api_key or not expected or not secrets.compare_digest(api_key, expected):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid API key. Send header: X-API-Key: <key>",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return key_fingerprint(api_key)
