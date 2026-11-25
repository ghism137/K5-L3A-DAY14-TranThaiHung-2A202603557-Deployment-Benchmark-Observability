# Deployment Information

## Public URL
https://agent-production-5dafbd72.up.railway.app

## Platform
Railway: project `k5-day14-agent`, environment `production`
- Service `agent`: build từ [06-lab-complete/Dockerfile](06-lab-complete/Dockerfile) theo [06-lab-complete/railway.toml](06-lab-complete/railway.toml) (builder `DOCKERFILE`, `healthcheckPath = "/health"`)
- Service `Redis`: database Railway, agent kết nối qua mạng nội bộ `redis.railway.internal`

## Test Commands

Đặt biến trước khi chạy (key lấy từ Railway Variables, không ghi vào file):
```bash
BASE=https://agent-production-5dafbd72.up.railway.app
AGENT_API_KEY=<key trên Railway>
```

### Health Check
```bash
curl $BASE/health
# Expected: {"status":"ok","version":"1.0.0","environment":"production","uptime_seconds":...}

curl $BASE/ready
# Expected: {"ready":true,"redis":"ok"}
```

### API Test (with authentication)
```bash
# Không có key → 401
curl -X POST $BASE/ask \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test", "question": "Hello"}'
# {"detail":"Missing or invalid API key. Send header: X-API-Key: <key>"}

# Có key → 200
curl -X POST $BASE/ask \
  -H "X-API-Key: $AGENT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test", "question": "Hello"}'
# {"question":"Hello","answer":"...","usage":{"input_tokens":1,"output_tokens":17,"cost_usd":1.035e-05}}
```

### Rate limit (10 request / 60 giây cho mỗi key)
```bash
for i in $(seq 1 15); do
  curl -s -o /dev/null -w "%{http_code} " -X POST $BASE/ask \
    -H "X-API-Key: $AGENT_API_KEY" -H "Content-Type: application/json" \
    -d '{"user_id":"test","question":"test"}'
done
# Kết quả thật (sau 1 request ở bước trên): 200 200 200 200 200 200 200 200 200 429 429 429 429 429 429
```

### Kết quả kiểm tra (2026-11-25)
| Lệnh | Mong đợi | Thực tế |
|---|---|---|
| `GET /health` | 200 | 200 |
| `GET /ready` | 200 | 200 |
| `POST /ask` không key | 401 | 401 |
| `POST /ask` có key | 200 | 200 |
| 15 request liên tiếp | có 429 | 9×200 rồi 429 (cộng 1 request ở bước trước = đúng 10 request/phút), `Retry-After: 30–32` |
| `check_production_ready.py --public-url $BASE` | PASS 12/12 | PASS 12/12, 42/42 checks |

## Environment Variables Set
- `PORT`: Railway tự cấp (8080); app đọc qua `${PORT:-8000}` trong `CMD`
- `REDIS_URL`: `${{Redis.REDIS_URL}}` (tham chiếu service Redis)
- `AGENT_API_KEY`: key ngẫu nhiên, chỉ lưu trong Railway Variables
- `LOG_LEVEL=INFO`
- `ENVIRONMENT=production`
- `RATE_LIMIT_PER_MINUTE=10`
- `DAILY_BUDGET_USD=1.0`
- `MONTHLY_BUDGET_USD=10`

## Screenshots
- [Deployment dashboard](screenshots/dashboard.png)
- [Service running](screenshots/running.png)
- [Test results](screenshots/test.png)
