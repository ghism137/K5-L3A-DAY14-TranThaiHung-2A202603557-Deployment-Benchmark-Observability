# Day 14 Lab — Mission Answers
---

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns tìm được trong `01-localhost-vs-production/develop/app.py`

1. **Hardcode secret** (dòng 17–18): `OPENAI_API_KEY` và `DATABASE_URL` (có cả mật khẩu DB) viết thẳng trong code → commit lên GitHub là lộ, nằm mãi trong lịch sử git.
2. **Không có config management** (dòng 21–22): `DEBUG = True`, `MAX_TOKENS = 500` cố định → muốn đổi giữa dev/staging/production phải sửa code và build lại.
3. **Dùng `print()` thay vì logging, và log ra secret** (dòng 33–38): in cả API key, câu hỏi và câu trả lời của người dùng ra stdout → lộ secret + dữ liệu người dùng qua trang Logs của platform; không có level, không có timestamp, không phải JSON nên không lọc/tìm kiếm được khi có nhiều request.
4. **Không có health check endpoint** (dòng 42): platform không có cách hỏi "app còn sống/sẵn sàng không" → app treo không được restart, deploy bản lỗi vẫn nhận traffic, load balancer không biết instance nào hỏng.
5. **Port cố định** (dòng 52): `port=8000` → Railway/Render cấp port qua biến `PORT`, app nghe sai port nên không nhận được request.
6. **`host="localhost"`** (dòng 51): chỉ nhận kết nối từ chính máy đó → chạy trong Docker/cloud thì bên ngoài không vào được; phải dùng `0.0.0.0`.
7. **`reload=True` trong production** (dòng 53): tốn tài nguyên theo dõi file, không chạy được nhiều worker, có thể restart cắt ngang request.
8. **Không xử lý shutdown**: không bắt SIGTERM → khi platform tắt/redeploy, request đang xử lý bị cắt đột ngột.
9. **Không validate input**: `question` không kiểm tra rỗng.

### Exercise 1.2: Chạy bản develop

Lệnh:
```bash
cd 01-localhost-vs-production/develop
pip install -r requirements.txt
python app.py
curl -X POST "http://localhost:8000/ask?question=Hello"
```

Output:
```text
HTTP/1.1 200 OK
date: Wed, 25 Nov 2026 09:10:46 GMT
server: uvicorn
content-length: 95
content-type: application/json

{"answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}
```

Quan sát ở terminal server:
```text
[DEBUG] Got question: Hello
[DEBUG] Using key: sk-hardcoded-fake-key-never-do-this
[DEBUG] Response: Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé.
INFO:     127.0.0.1:58085 - "POST /ask?question=Hello HTTP/1.1" 200 OK
```


### Exercise 1.3: Bảng so sánh develop vs production


| Feature | Develop | Production | Tại sao quan trọng? |
|---------|---------|------------|---------------------|
| Config | Hardcode trong code (dòng 17–22) | Đọc từ env qua `config.py` (`os.getenv`), có `.env.example` | Đổi môi trường không cần sửa code; secret không nằm trong git |
| Secret | Key viết thẳng + in ra log | Lấy từ env, không log secret | Tránh lộ key qua git và qua log |
| Health check | Không có | `GET /health` (liveness) + `GET /ready` (readiness) | Platform biết khi nào restart, khi nào ngừng gửi traffic |
| Logging | `print()`, văn bản tự do | `logging` dạng JSON, có level, chỉ log độ dài câu hỏi | Máy lọc/tìm được; không lộ dữ liệu người dùng; tắt được log DEBUG |
| Shutdown | Đột ngột | Graceful: `lifespan` + bắt SIGTERM, set `is_ready=False` rồi dọn dẹp | Không cắt ngang request khi redeploy/scale |
| Host | `localhost` | `0.0.0.0` (từ env `HOST`) | Nhận được kết nối từ ngoài container |
| Port | Cố định 8000 | `PORT` từ env, mặc định 8000 | Platform cloud tự cấp port |
| Reload | Luôn bật | Chỉ bật khi `DEBUG=true` | Production không cần, tốn tài nguyên |
| Validate config | Không | `validate()` — thiếu `AGENT_API_KEY` ở production thì dừng ngay (fail fast) | Phát hiện cấu hình sai lúc khởi động, không phải lúc người dùng gọi |
| Input | Query param, không kiểm tra | JSON body, rỗng → 422 | Báo lỗi rõ ràng cho client |

---

## Part 2: Docker

### Exercise 2.1: Trả lời câu hỏi về `02-docker/develop/Dockerfile`
1. Base image: FROM python:3.11
2. Working directory: WORKDIR /app
3. Tại sao COPY requirements.txt trước: requirement phải được cài trước những thứ khác, nên cấu hình trước tiên
4. CMD vs ENTRYPOINT: CMD ["python", "app.py"]

### Exercise 2.2: Build và run container

File: [02-docker/develop/Dockerfile](02-docker/develop/Dockerfile) — build **từ gốc repo** (vì `COPY` dùng đường dẫn tính từ gốc, build context `.` phải là gốc repo).

Lệnh:
```bash
docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .
docker run -d --rm --name k5-dev -p 8000:8000 my-agent:develop
curl -i -X POST "http://localhost:8000/ask?question=What%20is%20Docker"
curl -i http://localhost:8000/health
```

Output:
```text
HTTP/1.1 200 OK
date: Wed, 25 Nov 2026 09:02:24 GMT
server: uvicorn
content-length: 103
content-type: application/json

{"answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!"}

HTTP/1.1 200 OK
date: Wed, 25 Nov 2026 09:02:24 GMT
server: uvicorn
content-length: 53
content-type: application/json

{"status":"ok","uptime_seconds":4.1,"container":true}
```

`docker ps`:
```text
k5-dev my-agent:develop Up 6 seconds 0.0.0.0:8000->8000/tcp, [::]:8000->8000/tcp
```

### Exercise 2.3: Multi-stage build và kích thước image

File: [02-docker/production/Dockerfile](02-docker/production/Dockerfile)

- **Stage 1 — `builder`** (dòng 16–29): từ `python:3.11-slim`, cài `gcc`, `libpq-dev` (công cụ để biên dịch thư viện), rồi `pip install --user` các package vào `/root/.local`. Stage này **không** dùng để deploy.
- **Stage 2 — `runtime`** (dòng 36–72): bắt đầu lại từ `python:3.11-slim` sạch, chỉ `COPY --from=builder` thư mục package đã cài (dòng 45), copy `main.py` + `utils/mock_llm.py`, tạo user non-root `appuser` (dòng 40, 58), có `HEALTHCHECK` (dòng 68), chạy `uvicorn ... --workers 2`.
- **Tại sao nhỏ hơn:** image cuối chỉ chứa stage `runtime`. `gcc`, `libpq-dev`, cache apt/pip của stage `builder` bị bỏ lại. Thêm nữa, base `python:3.11-slim` nhỏ hơn nhiều so với `python:3.11` bản đầy đủ của develop.

Lệnh:
```bash
docker build -f 02-docker/production/Dockerfile -t my-agent:advanced .
docker images my-agent
```

Output:
```text
IMAGE               ID             DISK USAGE   CONTENT SIZE   EXTRA
my-agent:advanced   8c06bb469279        240MB         57.4MB
my-agent:develop    0caa159af1c1       1.67GB          426MB
```

Số chính xác (`docker image inspect --format '{{.Size}}'`): develop = 1 667 779 866 byte, advanced = 239 815 376 byte.

- Develop: **≈ 1 668 MB** (1.67 GB)
- Production: **≈ 240 MB**
- Chênh lệch: (1668 − 240) / 1668 × 100 ≈ **85.6 %** nhỏ hơn (develop gấp ~7 lần)

### Exercise 2.4: Docker Compose stack

File: [02-docker/production/docker-compose.yml](02-docker/production/docker-compose.yml), [02-docker/production/nginx/nginx.conf](02-docker/production/nginx/nginx.conf)

Sơ đồ:
```text
                 Máy host (localhost)
                        │  cổng 80 / 443
                        ▼
              ┌───────────────────┐
              │  nginx (alpine)   │  reverse proxy + load balancer
              │  rate limit 10r/s │  thêm security headers
              └─────────┬─────────┘
   network "internal"   │  proxy_pass http://agent:8000
   (bridge, không mở    ▼
    ra ngoài)   ┌───────────────────┐
              │  agent (FastAPI)   │  build từ 02-docker/production/Dockerfile
              │  cổng 8000 nội bộ  │  healthcheck /health
              └──────┬──────┬──────┘
   redis://redis:6379│      │ http://qdrant:6333
                     ▼      ▼
              ┌────────┐ ┌──────────┐
              │ redis  │ │  qdrant  │
              │ cache, │ │ vector DB│
              │ rate   │ │ cho RAG  │
              │ limit  │ │          │
              └────────┘ └──────────┘
             volume redis_data   volume qdrant_data
```

- Chỉ **nginx** mở cổng ra máy host (`80:80`, `443:443`). agent, redis, qdrant chỉ nằm trong network `internal`.
- Các service gọi nhau bằng **tên service** (Docker DNS): `agent:8000`, `redis:6379`, `qdrant:6333`.
- `depends_on` + `condition: service_healthy`: agent chỉ khởi động sau khi redis và qdrant đã healthy.

Lệnh:
```bash
cd 02-docker/production
touch .env.local
docker compose -p k5-day14-docker up -d --build
docker compose -p k5-day14-docker ps
curl -i http://localhost/health
curl -i -X POST http://localhost/ask -H "Content-Type: application/json" -d '{"question": "Explain microservices"}'
docker compose -p k5-day14-docker down -v
```

Services được start (`docker compose ps`):
```text
SERVICE   IMAGE                   STATUS                    PORTS
agent     k5-day14-docker-agent   Up 18 seconds (healthy)   8000/tcp
nginx     nginx:alpine            Up 18 seconds             0.0.0.0:80->80/tcp, [::]:80->80/tcp, 0.0.0.0:443->443/tcp, [::]:443->443/tcp
qdrant    qdrant/qdrant:v1.9.0    Up 30 seconds (healthy)   6333-6334/tcp
redis     redis:7-alpine          Up 29 seconds (healthy)   6379/tcp
```

Kết quả test qua Nginx:
```text
HTTP/1.1 200 OK
Server: nginx
Content-Type: application/json
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
X-XSS-Protection: 1; mode=block

{"status":"ok","uptime_seconds":15.3,"version":"2.0.0","timestamp":"2026-11-25T09:03:58.491060"}

HTTP/1.1 200 OK
Server: nginx
Content-Type: application/json
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
X-XSS-Protection: 1; mode=block

{"answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}
```

Nhận xét: header `Server: nginx` và các security header chứng minh request đi **qua Nginx** rồi mới tới agent, không gọi thẳng agent.

---

## Part 3: Cloud Deployment

### Exercise 3.1 / 3.2: Deploy agent Part 6

Theo CHECKPOINTS (CP6), tôi deploy chính agent Part 6 (`06-lab-complete/`, đã `PASS 12/12`) lên **Railway**. Chi tiết trong [DEPLOYMENT.md](DEPLOYMENT.md).

- Nền tảng: **Railway**. Project `k5-day14-agent` gồm 2 service: `agent` (build từ `Dockerfile` theo `railway.toml`) và `Redis` (database Railway).
- URL: **https://agent-production-5dafbd72.up.railway.app**
- Các bước (CLI, chạy trong `06-lab-complete/`):
  ```bash
  railway init --name k5-day14-agent
  railway link -p <project-id>
  railway add -d redis
  railway add -s agent -v "AGENT_API_KEY=<key ngẫu nhiên>" -v 'REDIS_URL=${{Redis.REDIS_URL}}' \
      -v ENVIRONMENT=production -v LOG_LEVEL=INFO -v RATE_LIMIT_PER_MINUTE=10 \
      -v DAILY_BUDGET_USD=1.0 -v MONTHLY_BUDGET_USD=10
  railway up --service agent --ci
  railway domain --service agent
  ```
- Biến môi trường đặt trên nền tảng: `AGENT_API_KEY` (key ngẫu nhiên `secrets.token_urlsafe(32)`, không nằm trong code/git), `REDIS_URL` (tham chiếu `${{Redis.REDIS_URL}}` → `redis://default:***@redis.railway.internal:6379`, mạng nội bộ), `ENVIRONMENT=production`, `LOG_LEVEL=INFO`, `RATE_LIMIT_PER_MINUTE=10`, `DAILY_BUDGET_USD=1.0`, `MONTHLY_BUDGET_USD=10`. `PORT` do Railway tự cấp (log cho thấy `port=8080`).
- Log khởi động trên Railway (JSON):
  ```text
  INFO:     Uvicorn running on http://0.0.0.0:8080 (Press CTRL+C to quit)
  ... logger="agent" event="startup" environment="production" version="1.0.0" port=8080 redis_ok=true
  ```
- Kết quả 4 lệnh tự kiểm CP6 (`/health`, `/ready`, `/ask` không key, `/ask` có key):
  ```text
  /health:
  200
  /ready:
  200
  /ask không key:
  401
  /ask có key:
  200
  ```
  Body trả về:
  ```text
  {"status":"ok","version":"1.0.0","environment":"production","uptime_seconds":33.5}
  {"ready":true,"redis":"ok"}
  {"question":"What is deployment?","answer":"Deployment là quá trình đưa code từ máy bạn lên server để người khác dùng được.","usage":{"input_tokens":4,"output_tokens":21,"cost_usd":1.32e-05}}
  ```
- Rate limit trên cloud (Redis của Railway), đã dùng 2 lượt trước đó, gửi tiếp 12 request:
  ```text
  req 1..8: 200
  req 9: 429  retry-after: 32
  req 10: 429  retry-after: 31
  req 11: 429  retry-after: 31
  req 12: 429  retry-after: 30
  ```
- `check_production_ready.py --public-url https://agent-production-5dafbd72.up.railway.app`:
  ```text
       ✅ Public URL: GET https://agent-production-5dafbd72.up.railway.app/health → 200
    Result: 12/12 tiêu chí đạt · 42/42 checks passed
    🎉 PASS 12/12 — PRODUCTION READY! Deploy nào!
  ```
- Ảnh: `screenshots/dashboard.png`, `screenshots/running.png`, `screenshots/test.png` [ĐIỀN — tự chụp]
- Ghi chú: Railway CLI 5.75 cảnh báo `railway.toml` (Config as Code) sẽ được thay bằng `.railway/railway.ts`, nhưng file cũ vẫn chạy đến 2026-12-01. Tôi giữ `railway.toml` vì đề bài và script chấm yêu cầu.

### So sánh `railway.toml` và `render.yaml`


File: [03-cloud-deployment/railway/railway.toml](03-cloud-deployment/railway/railway.toml), [03-cloud-deployment/render/render.yaml](03-cloud-deployment/render/render.yaml)

| Tiêu chí | `railway.toml` | `render.yaml` |
|---|---|---|
| Định dạng | TOML, chia khối `[build]`, `[deploy]` | YAML, danh sách `services:` |
| Phạm vi | Cấu hình **1 service** | Mô tả **cả hệ thống** (Blueprint): web service **và** Redis trong cùng file |
| Cách build | `builder = "NIXPACKS"` — Railway tự đoán ngôn ngữ (Python) và tự build | `runtime: python` + `buildCommand: pip install -r requirements.txt` — khai báo rõ |
| Lệnh chạy | `startCommand = "uvicorn app:app --host 0.0.0.0 --port $PORT"` | `startCommand: uvicorn app:app --host 0.0.0.0 --port $PORT` (giống nhau) |
| Health check | `healthcheckPath = "/health"`, có thêm `healthcheckTimeout = 30` | `healthCheckPath: /health` |
| Restart khi crash | Khai báo rõ: `restartPolicyType = "ON_FAILURE"`, tối đa 3 lần | Không khai báo, Render tự xử lý mặc định |
| Biến môi trường / secret | **Không** nằm trong file — đặt bằng `railway variables` hoặc dashboard | Khai báo **ngay trong file**: giá trị thường (`ENVIRONMENT: production`), `sync: false` = secret tự nhập trên dashboard, `generateValue: true` = Render tự sinh `AGENT_API_KEY` ngẫu nhiên |
| Hạ tầng khác | Không có `region`, `plan` | Có `region: singapore`, `plan: free`, `autoDeploy: true` (tự deploy mỗi lần push GitHub) |
| Cách deploy | CLI `railway up` từ máy (upload thư mục hiện tại) | Kết nối repo GitHub → Render đọc `render.yaml` |

**Giống nhau:** cả hai đều chạy uvicorn trên `0.0.0.0` và `$PORT` do nền tảng cấp (bài học Part 1), đều dùng `/health` để biết deploy thành công hay không, và đều **không ghi giá trị secret** vào file.

**Vì sao khác:** Railway thiên về **deploy nhanh từ CLI** — file chỉ cần nói cách build/chạy, phần còn lại (biến, database) làm trên dashboard. Render thiên về **Infrastructure as Code** — toàn bộ hạ tầng (service, Redis, region, biến cần có) nằm trong git, nên tạo lại môi trường giống hệt chỉ bằng một file, review được qua pull request.

### Exercise 3.3: Pipeline Cloud Run (`cloudbuild.yaml` + `service.yaml`)

File: [03-cloud-deployment/production-cloud-run/cloudbuild.yaml](03-cloud-deployment/production-cloud-run/cloudbuild.yaml), [03-cloud-deployment/production-cloud-run/service.yaml](03-cloud-deployment/production-cloud-run/service.yaml)

Pipeline Cloud Build chạy khi push lên `main`, gồm 4 bước nối nhau bằng `waitFor` (bước trước fail thì dừng, không deploy):

1. **test** — trong image `python:3.11-slim`, cài requirements + pytest rồi chạy `pytest tests/`. Test fail → pipeline dừng, code lỗi không lên production.
2. **build** — build Docker image, gắn 2 tag: `$COMMIT_SHA` (mỗi commit một image riêng → dễ rollback về đúng phiên bản) và `latest`; dùng `--cache-from` image `latest` để build nhanh nhờ layer cache.
3. **push** — đẩy image lên Container Registry (`gcr.io/$PROJECT_ID/ai-agent`).
4. **deploy** — `gcloud run deploy` image theo `$COMMIT_SHA` lên region `asia-southeast1`: 1–10 instance (`--min-instances=1` tránh cold start), 512Mi RAM, 1 CPU, timeout 60s; biến thường qua `--set-env-vars`, secret `OPENAI_API_KEY` lấy từ **Secret Manager** (`--set-secrets`), không nằm trong code.

`service.yaml` mô tả cùng service dưới dạng khai báo (IaC): autoscale 1–10 instance, mỗi instance tối đa 80 request đồng thời, giới hạn CPU/RAM, secret lấy từ Secret Manager, `livenessProbe` gọi `/health` (fail → restart) và `startupProbe` gọi `/ready` (chưa sẵn sàng → chưa nhận traffic) — đúng phân biệt liveness/readiness ở Part 1.

---

## Part 4: API Security

### Exercise 4.1: API key (bản develop)
- API key được check ở đâu: verify_api_key
- Sai key thì sao: raise HTTPException(
            status_code=401,
            detail="Missing API key. Include header: X-API-Key: <your-key>",
        )
- Rotate key thế nào: raise HTTPException(
            status_code=403,
            detail="Invalid API key.",
        )

File: [04-api-gateway/develop/app.py](04-api-gateway/develop/app.py)

Lệnh bật server (Git Bash, trong `04-api-gateway/develop`):
```bash
AGENT_API_KEY=secret-key-123 python app.py
```

Output test:
```text
$ curl -i -X POST http://localhost:8000/ask -H "Content-Type: application/json" -d '{"question": "Hello"}'
HTTP/1.1 401 Unauthorized
date: Wed, 25 Nov 2026 11:23:52 GMT
server: uvicorn
content-length: 67
content-type: application/json

{"detail":"Missing API key. Include header: X-API-Key: <your-key>"}

$ curl -i -X POST http://localhost:8000/ask -H "X-API-Key: wrong-key" -H "Content-Type: application/json" -d '{"question": "Hello"}'
HTTP/1.1 403 Forbidden
date: Wed, 25 Nov 2026 11:23:52 GMT
server: uvicorn
content-length: 29
content-type: application/json

{"detail":"Invalid API key."}

$ curl -i -X POST http://localhost:8000/ask -H "X-API-Key: secret-key-123" -H "Content-Type: application/json" -d '{"question": "Hello"}'
HTTP/1.1 200 OK
date: Wed, 25 Nov 2026 11:23:52 GMT
server: uvicorn
content-length: 114
content-type: application/json

{"question":"Hello","answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}
```

Tóm tắt: không key → **401**, sai key → **403**, đúng key → **200**.

### Exercise 4.2: JWT (bản production)

File: [04-api-gateway/production/auth.py](04-api-gateway/production/auth.py), [04-api-gateway/production/app.py](04-api-gateway/production/app.py) — bật bằng `python app.py` trong `04-api-gateway/production`. Token đã che (`***MASKED***`).

Lấy token (đúng và sai mật khẩu):
```text
$ curl -i -X POST http://localhost:8000/auth/token -H "Content-Type: application/json" -d '{"username": "student", "password": "demo123"}'
HTTP/1.1 200 OK
date: Wed, 25 Nov 2026 11:27:51 GMT
server: uvicorn
content-length: 307
content-type: application/json
x-content-type-options: nosniff
x-frame-options: DENY
x-xss-protection: 1; mode=block
referrer-policy: strict-origin-when-cross-origin

{"access_token":"eyJhbGciOiJ***MASKED***","token_type":"bearer","expires_in_minutes":60,"hint":"Include in header: Authorization: Bearer eyJhbGciOiJ***MASKED***"}

$ curl -i -X POST http://localhost:8000/auth/token -H "Content-Type: application/json" -d '{"username": "student", "password": "wrong"}'
HTTP/1.1 401 Unauthorized
...
{"detail":"Invalid credentials"}
```

Gọi `/ask` (không token / có token / token giả):
```text
$ curl -i -X POST http://localhost:8000/ask -H "Content-Type: application/json" -d '{"question": "Explain JWT"}'
HTTP/1.1 401 Unauthorized
date: Wed, 25 Nov 2026 11:27:51 GMT
server: uvicorn
www-authenticate: Bearer
content-length: 76
content-type: application/json

{"detail":"Authentication required. Include: Authorization: Bearer <token>"}

$ curl -i -X POST http://localhost:8000/ask -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"question": "Explain JWT"}'
HTTP/1.1 200 OK
date: Wed, 25 Nov 2026 11:27:51 GMT
server: uvicorn
content-length: 184
content-type: application/json
x-content-type-options: nosniff
x-frame-options: DENY
x-xss-protection: 1; mode=block
referrer-policy: strict-origin-when-cross-origin

{"question":"Explain JWT","answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé.","usage":{"requests_remaining":9,"budget_remaining_usd":1.6e-05}}

$ curl -i -X POST http://localhost:8000/ask -H "Authorization: Bearer invalid.token.here" -H "Content-Type: application/json" -d '{"question": "Explain JWT"}'
HTTP/1.1 403 Forbidden
...
{"detail":"Invalid token."}
```

Tóm tắt: sai mật khẩu → **401**; không token → **401** (kèm header `www-authenticate: Bearer`); token hợp lệ → **200**; token giả → **403**.

Giải thích luồng JWT: [ĐIỀN — tự viết: login → server ký token bằng `SECRET_KEY` (HS256), payload có `sub`, `role`, `exp` → client gửi `Authorization: Bearer <token>` → server chỉ cần kiểm tra chữ ký + hạn, không tra DB mỗi request]

trường `budget_remaining_usd` (app.py dòng 160) thực ra trả về `usage.total_cost_usd` — tức **số tiền đã dùng**, không phải số còn lại. Tên trường bị đặt sai.

### Exercise 4.3: Rate limiting
- Thuật toán: sliding window
- Giới hạn: 10 request/phút
- Bypass cho admin: limiter theo role trong app.py

File: [04-api-gateway/production/rate_limiter.py](04-api-gateway/production/rate_limiter.py), [04-api-gateway/production/app.py](04-api-gateway/production/app.py) (dòng 141–142)

Lệnh (Git Bash, token của `student`):
```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/token -H "Content-Type: application/json" \
  -d '{"username": "student", "password": "demo123"}' | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
for i in {1..20}; do
  echo -n "Request $i: "
  curl -s -w "  -> HTTP %{http_code}\n" -X POST http://localhost:8000/ask \
    -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "{\"question\": \"Test $i\"}"
done
```

Output (bắt đầu 11:36:41 UTC, 25/11/2026):
```text
Request 1: {"question":"Test 1","answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé.","usage":{"requests_remaining":9,"budget_remaining_usd":3.2e-05}}  -> HTTP 200
Request 2: {"question":"Test 2","answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic.","usage":{"requests_remaining":8,"budget_remaining_usd":5.3e-05}}  -> HTTP 200
Request 3: {"question":"Test 3","answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic.","usage":{"requests_remaining":7,"budget_remaining_usd":7.4e-05}}  -> HTTP 200
Request 4: {"question":"Test 4","answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé.","usage":{"requests_remaining":6,"budget_remaining_usd":9.1e-05}}  -> HTTP 200
Request 5: {"question":"Test 5","answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận.","usage":{"requests_remaining":5,"budget_remaining_usd":0.000109}}  -> HTTP 200
Request 6: {"question":"Test 6","answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic.","usage":{"requests_remaining":4,"budget_remaining_usd":0.00013}}  -> HTTP 200
Request 7: {"question":"Test 7","answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic.","usage":{"requests_remaining":3,"budget_remaining_usd":0.000151}}  -> HTTP 200
Request 8: {"question":"Test 8","answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận.","usage":{"requests_remaining":2,"budget_remaining_usd":0.00017}}  -> HTTP 200
Request 9: {"question":"Test 9","answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic.","usage":{"requests_remaining":1,"budget_remaining_usd":0.000191}}  -> HTTP 200
Request 10: {"question":"Test 10","answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận.","usage":{"requests_remaining":0,"budget_remaining_usd":0.000209}}  -> HTTP 200
Request 11: {"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":59}}  -> HTTP 429
Request 12: {"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":59}}  -> HTTP 429
Request 13: {"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":59}}  -> HTTP 429
Request 14: {"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":59}}  -> HTTP 429
Request 15: {"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":59}}  -> HTTP 429
Request 16: {"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":58}}  -> HTTP 429
Request 17: {"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":58}}  -> HTTP 429
Request 18: {"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":58}}  -> HTTP 429
Request 19: {"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":58}}  -> HTTP 429
Request 20: {"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":58}}  -> HTTP 429
```

Một response 429 đầy đủ (`curl -i`):
```text
HTTP/1.1 429 Too Many Requests
date: Wed, 25 Nov 2026 11:36:43 GMT
server: uvicorn
x-ratelimit-limit: 10
x-ratelimit-remaining: 0
x-ratelimit-reset: 1795606663
retry-after: 58
content-length: 98
content-type: application/json
x-content-type-options: nosniff
x-frame-options: DENY
x-xss-protection: 1; mode=block
referrer-policy: strict-origin-when-cross-origin

{"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":58}}
```

So sánh với admin (`teacher` / `teach456`, cùng 20 request ngay sau đó):
```text
200 200 200 200 200 200 200 200 200 200 200 200 200 200 200 200 200 200 200 200
```

Nhận xét kết quả:
- `student`: request 1–10 → **200**, `requests_remaining` giảm 9 → 0; từ request 11 → **429**.
- Response 429 có header `Retry-After` và `X-RateLimit-*` → client biết phải chờ bao lâu (~58–59 giây, tới khi request đầu tiên trượt ra khỏi cửa sổ 60 giây).
- `teacher` (role `admin`) dùng limiter 100 req/phút nên cả 20 request đều **200** — đó là cách "bypass" cho admin: không bỏ giới hạn, mà dùng một limiter có ngưỡng cao hơn.
- `budget_remaining_usd` tăng dần qua các request (cộng dồn cả request ở 4.2) → xác nhận nó là **chi phí đã dùng**, không phải số còn lại.

### Exercise 4.4: Cost guard

#### a) Bản có sẵn — [04-api-gateway/production/cost_guard.py](04-api-gateway/production/cost_guard.py)

- **Đếm chi phí:** mỗi request ước lượng token (`app.py` dòng 151–152: số từ × 2), nhân với giá GPT-4o-mini (dòng 20–21: $0.15/1M input, $0.60/1M output) → `total_cost_usd`.
- **Thứ tự trong `/ask`:** `check_budget()` chạy **trước** khi gọi LLM (`app.py` dòng 145) để chặn trước khi tốn tiền; `record_usage()` chạy **sau** (dòng 153) vì chỉ khi có câu trả lời mới biết số token thật.
- **Hai mức chặn:** vượt budget của **một user** ($1/ngày) → **402 Payment Required** (lỗi của riêng user đó); vượt budget **toàn hệ thống** ($10/ngày) → **503 Service Unavailable** (cả dịch vụ tạm ngừng, không phải lỗi của user). Dùng 80% budget → ghi log cảnh báo.
- **Khác với rate limit:** rate limit chặn **số request theo thời gian** (bảo vệ tốc độ), cost guard chặn **tổng tiền** (bảo vệ ví). Một user gửi ít request nhưng câu hỏi rất dài vẫn có thể đốt hết tiền mà không chạm rate limit → cần cả hai.
- **Điểm yếu:** dữ liệu nằm trong RAM (`self._records`, `self._global_cost`) → restart là mất hết, và chạy nhiều instance thì mỗi instance đếm riêng (user được nhân budget theo số instance).

#### b) Cách làm theo yêu cầu đề — $10/tháng/user, lưu trong Redis, reset đầu tháng

```python
import os
from datetime import datetime, timezone
import redis

MONTHLY_BUDGET_USD = float(os.getenv("MONTHLY_BUDGET_USD", "10"))
r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True)


def _budget_key(user_id: str) -> str:
    month = datetime.now(timezone.utc).strftime("%Y-%m")   # vd 2026-11
    return f"budget:{user_id}:{month}"


def check_budget(user_id: str, estimated_cost: float) -> bool:
    """True nếu còn budget (và đã giữ chỗ estimated_cost), False nếu vượt."""
    key = _budget_key(user_id)
    new_total = r.incrbyfloat(key, estimated_cost)          # cộng nguyên tử, trả về tổng mới
    r.expire(key, 32 * 24 * 3600, nx=True)                  # chỉ đặt TTL lần đầu
    if new_total > MONTHLY_BUDGET_USD:
        r.incrbyfloat(key, -estimated_cost)                 # vượt -> hoàn lại phần vừa cộng
        return False
    return True
```

Giải thích:
1. **Reset đầu tháng không cần cron job:** key chứa tháng (`budget:<user>:2026-11`). Sang tháng 12 code tự đọc key `...:2026-12` mới, bắt đầu từ 0.
2. **`EXPIRE` 32 ngày** để Redis tự dọn key của tháng cũ (32 > 31 ngày dài nhất). `nx=True` = chỉ đặt TTL khi key chưa có TTL, tránh mỗi request lại gia hạn thêm.
3. **Cấu hình từ env** (`MONTHLY_BUDGET_USD`, `REDIS_URL`) — không hardcode, đúng 12-Factor.
4. **Vì sao `INCRBYFLOAT` trước rồi mới so sánh** (khác lời giải mẫu trong CODE_LAB là `GET` → so sánh → `INCRBYFLOAT`): cách đọc-rồi-ghi có **race condition** — 2 request cùng lúc đều đọc thấy $9.5, cùng thấy "còn đủ", cùng cộng → vượt budget. `INCRBYFLOAT` là thao tác **nguyên tử** của Redis: mỗi request nhận về tổng **sau khi** đã cộng, nên chỉ request nào làm tổng vượt mức mới bị từ chối và hoàn lại.
5. **Vì sao lưu Redis:** mọi instance agent dùng chung một bộ đếm, restart agent không mất dữ liệu → stateless (Part 5, Part 6).
6. **Dùng trong endpoint:** `check_budget()` trả `False` → endpoint raise `HTTPException(402, ...)` **trước** khi gọi LLM. Sau khi gọi LLM có thể ghi chênh lệch giữa chi phí thật và `estimated_cost` bằng một lần `INCRBYFLOAT` nữa.

Chạy thử với Redis thật (`docker run -p 6390:6379 redis:7-alpine`), mỗi lần gọi ước tính $3:
```text
key: budget:test-user:2026-11 | budget: 10.0
call 1: +$3.00 -> ALLOW | spent = $3.00
call 2: +$3.00 -> ALLOW | spent = $6.00
call 3: +$3.00 -> ALLOW | spent = $9.00
call 4: +$3.00 -> BLOCK (402) | spent = $9.00
call 5: +$3.00 -> BLOCK (402) | spent = $9.00
small call +$0.50 -> ALLOW | spent = $9.50
TTL (days): 32.0
```

→ Lần 4 bị chặn vì $9 + $3 > $10, và tổng **vẫn giữ $9** (phần vừa cộng đã được hoàn lại). Câu nhỏ $0.50 vẫn được phép vì còn trong budget. TTL 32 ngày đã được đặt.

---

## Part 5: Scaling & Reliability

> Cách chạy 5.1–5.2: chạy `05-scaling-reliability/develop/app.py` trong container `python:3.11-slim` (cổng 8001, vì 8000 đang bận), để `docker stop` gửi **SIGTERM thật** như Railway/K8s. Trên Windows, `kill -TERM` không gửi được SIGTERM "êm".

### Exercise 5.1: Health checks (liveness vs readiness)

```text
GET /health -> HTTP 200
{"status":"ok","uptime_seconds":0.7,"version":"1.0.0","environment":"development","timestamp":"2026-11-25T13:40:12.708006+00:00","checks":{"memory":{"status":"ok","used_percent":10.7}}}

GET /ready -> HTTP 200
{"ready":true,"in_flight_requests":1}

POST /ask?question=docker -> HTTP 200
{"answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!"}
```

💡 GỢI Ý (viết lại bằng lời của bạn):
| | `/health` (liveness) | `/ready` (readiness) |
|---|---|---|
| Câu hỏi | Process còn sống không? | Có nên gửi traffic vào không? |
| Fail thì platform làm gì | **Restart** container | **Ngừng route** traffic vào instance đó, không restart |
| Trong code | Luôn 200 nếu process chạy, kèm uptime, version, memory | 503 khi `_is_ready = False` (đang khởi động hoặc đang tắt) |

- `in_flight_requests: 1` là vì middleware đếm luôn chính request `/ready` đang chạy.
- Không được để `/health` phụ thuộc Redis hay DB: dependency chết mà health fail thì platform restart container liên tục, dù restart không sửa được gì. Đây đúng là yêu cầu của Part 6: `/health` luôn 200, `/ready` 503 khi mất Redis.

### Exercise 5.2: Graceful shutdown

Test: gửi 2 request `/ask` song song (mock mất ~3s mỗi request), sau 0.5s `docker stop` (SIGTERM), sau 1.5s gửi thêm 1 request mới.

**Lần 1, code gốc** (`async def ask_agent`):
```text
t=0.5s gửi SIGTERM (docker stop)
t=1.5s thử request MỚI trong lúc đang tắt:
 | HTTP 000  -> bị từ chối kết nối (exit 52)
== kết quả 2 request đang chạy:
{"answer":"Deployment là quá trình đưa code từ máy bạn lên server để người khác dùng được."} | HTTP 200 | xong sau 3.016080s
 | HTTP 000 | xong sau 2.995162s        <- request thứ 2 BỊ CẮT
== log container:
INFO:     Shutting down
INFO:     172.17.0.1:44524 - "POST /ask?question=deploy HTTP/1.1" 200 OK
INFO:     Waiting for application shutdown.
2026-11-25 13:40:26,707 INFO 🔄 Graceful shutdown initiated...
2026-11-25 13:40:26,707 INFO ✅ Shutdown complete
INFO:     Finished server process [1]
2026-11-25 13:40:26,707 INFO Received signal 15 — uvicorn will handle graceful shutdown
ExitCode=0
```

Tìm nguyên nhân: gửi 2 request song song khi **không** tắt server:
```text
request 1: HTTP 200 sau 3.047457s
request 2: HTTP 200 sau 6.077989s      <- phải chờ request 1 xong mới chạy
```
→ `ask_agent` là `async def` nhưng bên trong `mock_llm.ask()` gọi `time.sleep(3)` (blocking), nên **event loop bị chặn** và 2 request chạy nối đuôi nhau. Khi SIGTERM đến, request 2 vẫn đang chờ, chưa được xử lý, nên uvicorn đóng kết nối của nó.

**Lần 2, sửa 1 dòng** `async def ask_agent` → `def ask_agent` (FastAPI chạy hàm `def` trong threadpool), test trên bản sao, chưa sửa file gốc:
```text
t=0.5s gửi SIGTERM
t=1.5s request MỚI:
 | HTTP 000  -> bị từ chối kết nối (exit 52)
== 2 request đang chạy:
{"answer":"Deployment là ..."} | HTTP 200 | xong sau 3.054923s
{"answer":"Deployment là ..."} | HTTP 200 | xong sau 3.048134s
== log:
INFO:     Shutting down
INFO:     Waiting for connections to close. (CTRL+C to force quit)
INFO:     172.17.0.1:39236 - "POST /ask?question=deploy HTTP/1.1" 200 OK
INFO:     172.17.0.1:39248 - "POST /ask?question=deploy HTTP/1.1" 200 OK
INFO:     Waiting for application shutdown.
2026-11-25 13:41:27,759 INFO 🔄 Graceful shutdown initiated...
2026-11-25 13:41:27,759 INFO ✅ Shutdown complete
INFO:     Finished server process [1]
ExitCode=0
```

- Sau khi sửa, **cả 2 request đang chạy đều trả 200**, request **mới** bị từ chối, và process thoát với `ExitCode=0` (tắt sạch, không bị SIGKILL).
- Flow: SIGTERM → uvicorn ngừng nhận kết nối mới → chờ các request đang xử lý (`timeout_graceful_shutdown=30`) → lifespan shutdown (`_is_ready = False`, chờ `_in_flight_requests == 0`) → exit.
- Bài học: graceful shutdown chỉ cứu được request **đã bắt đầu chạy**. Gọi code blocking trong `async def` làm request phải xếp hàng, và các request đang xếp hàng sẽ mất khi deploy. Với LLM thật nên dùng client async (`await`) hoặc dùng `def`.
- `docker stop -t 35`: Docker chờ 35s rồi mới SIGKILL, dài hơn 30s graceful của app. Trên Railway/K8s cũng phải để grace period lớn hơn thời gian app cần để tắt.

### Exercise 5.3: Stateless design

- **Không còn biến global giữ hội thoại.** Session lưu ở Redis với key `session:{session_id}` (`save_session`, dòng 59–65), dùng `SETEX` TTL 3600s nên session tự hết hạn sau 1 giờ.
- Mỗi request: `load_session` từ Redis → append → `save_session` lại (dòng 76–90), giữ tối đa 20 message.
- `INSTANCE_ID` ngẫu nhiên và được trả về ở `served_by`, nên thấy được request nào do instance nào xử lý.
- Lưu ý code: nếu không kết nối được Redis lúc khởi động thì app **lặng lẽ quay về dict trong RAM** (dòng 42–45), tức là lại thành stateful. Trong production nên fail hẳn (`/ready` 503) thay vì âm thầm fallback.
- Chưa an toàn khi chạy đồng thời: `load → append → save` không nguyên tử, 2 request cùng session đến cùng lúc có thể ghi đè history của nhau. Có thể dùng `RPUSH`/`LTRIM` trên Redis list để sửa.

### Exercise 5.4: Load balancing (3 instance + Nginx)

Lệnh (trong `05-scaling-reliability/production/`, đã `touch .env.local`):
```bash
docker compose -p k5-day14-scaling up -d --build --scale agent=3
```
```text
NAME                       STATUS                    PORTS
k5-day14-scaling-agent-1   Up 28 seconds (healthy)   8000/tcp
k5-day14-scaling-agent-2   Up 28 seconds (healthy)   8000/tcp
k5-day14-scaling-agent-3   Up 27 seconds (healthy)   8000/tcp
k5-day14-scaling-nginx-1   Up 27 seconds             0.0.0.0:8080->80/tcp, [::]:8080->80/tcp
k5-day14-scaling-redis-1   Up 39 seconds (healthy)   6379/tcp
```

**Thử tắt 1 instance** (`docker stop k5-day14-scaling-agent-2`, chính là `instance-19aa77`) rồi chat tiếp vào cùng session:
```text
HTTP 200 60.197488s       <- request đầu tiên sau khi tắt: chờ 60 giây
HTTP 200 0.133355s
HTTP 200 0.170029s
HTTP 200 0.146306s
HTTP 200 0.125652s served_by= instance-9920be turn= 11
HTTP 200 0.147224s served_by= instance-81dc4a turn= 11
HTTP 200 0.132582s served_by= instance-9920be turn= 11
HTTP 200 0.124636s served_by= instance-81dc4a turn= 11
history count = 20
```
Log nginx:
```text
[error] 30#30: *10 upstream timed out (110: Operation timed out) while connecting to upstream, ... upstream: "http://172.18.0.4:8000/chat"
```
- Không request nào lỗi: `proxy_next_upstream error timeout http_503` cho nginx thử instance khác. Sau đó traffic chỉ còn luân phiên giữa 2 instance sống, và session vẫn tiếp tục vì nằm trong Redis.
- **Nhưng request đầu tiên mất 60s**: nginx vẫn gửi vào IP cũ của container đã tắt và chờ hết `proxy_connect_timeout` mặc định (60s) mới chuyển. Cách sửa: đặt `proxy_connect_timeout 2s;`, thêm `max_fails=1 fail_timeout=10s` cho upstream, hoặc dùng health check chủ động.
- `turn` đứng ở 11 và `count` dừng ở 20 vì code chỉ giữ 20 message cuối (dòng 86–87), còn `turn` được tính từ history đã bị cắt. Đây là bug nhỏ: số turn hiển thị sai sau 10 lượt.

### Exercise 5.5: Test stateless — `python test_stateless.py`
```text
============================================================
Stateless Scaling Demo
============================================================

Session ID: 20255e53-0a44-4762-b70e-acb6aef7f84f

Request 1: [instance-19aa77]
  Q: What is Docker?
  A: Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!...

Request 2: [instance-81dc4a]
  Q: Why do we need containers?
  A: Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé....

Request 3: [instance-9920be]
  Q: What is Kubernetes?
  A: Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ O...

Request 4: [instance-19aa77]
  Q: How does load balancing work?
  A: Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận....

Request 5: [instance-81dc4a]
  Q: What is Redis used for?
  A: Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ O...

------------------------------------------------------------
Total requests: 5
Instances used: {'instance-9920be', 'instance-81dc4a', 'instance-19aa77'}
✅ All requests served despite different instances!

--- Conversation History ---
Total messages: 10
  [user]: What is Docker?...
  [assistant]: Container là cách đóng gói app để chạy ở mọi nơi. Build once...
  [user]: Why do we need containers?...
  [assistant]: Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đ...
  [user]: What is Kubernetes?...
  [assistant]: Đây là câu trả lời từ AI agent (mock). Trong production, đây...
  [user]: How does load balancing work?...
  [assistant]: Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã đư...
  [user]: What is Redis used for?...
  [assistant]: Đây là câu trả lời từ AI agent (mock). Trong production, đây...

✅ Session history preserved across all instances via Redis!
```
Xong: `docker compose -p k5-day14-scaling down`.

Giải thích: [ĐIỀN — tự viết. Gợi ý ý chính: 5 request đi lần lượt qua 3 instance khác nhau theo kiểu round-robin (19aa77 → 81dc4a → 9920be → 19aa77 → 81dc4a), vậy mà history vẫn đủ 10 message đúng thứ tự, vì không instance nào giữ state trong RAM, tất cả đọc/ghi chung Redis. Nếu lưu trong dict của từng instance thì request 2 (ở instance khác) sẽ không thấy câu hỏi 1.]

---

## Part 6: Output `check_production_ready.py`

Chạy chế độ **đầy đủ** (không `--skip-docker` / `--static-only`). Vì trên Windows script không gửi được SIGTERM (mục graceful shutdown sẽ ra ⚠️), tôi chạy script trong một container Linux `python:3.11-slim` có Docker CLI, mount Docker socket và dùng `--network host`:
```bash
docker run --rm --network host -v //var/run/docker.sock:/var/run/docker.sock \
  -v "<repo>:/repo:ro" -w /repo/06-lab-complete k5-checker python check_production_ready.py
```

```text
  📋 Checklist Deliverable
     ✅ Dockerfile (multi-stage, < 500 MB)
     ✅ docker-compose.yml (agent + redis)
     ✅ .dockerignore
     ✅ Health check endpoint (GET /health)
     ✅ Readiness endpoint (GET /ready)
     ✅ API Key authentication
     ✅ Rate limiting
     ✅ Cost guard
     ✅ Config từ environment variables
     ✅ Structured logging
     ✅ Graceful shutdown
     ✅ Public URL ready (Railway / Render config)
----------------------------------------------------------------
  Result: 12/12 tiêu chí đạt · 41/41 checks passed
  🎉 PASS 12/12 — PRODUCTION READY! Deploy nào!
================================================================
```
Chi tiết đáng chú ý trong output: image **274 MB** (build 22s), rate limit `429 sau 5 request thành công (RATE_LIMIT_PER_MINUTE=5)`, cost guard `402 ở request thứ 1`, `15 dòng JSON`, graceful shutdown `exit code 0`, `docker stop` `exit code 0, 0.7s`.

| Tiêu chí | File | Ý chính |
|---|---|---|
| Config | `app/config.py` | Mọi giá trị đọc từ env; `AGENT_API_KEY` **không có mặc định** (thiếu thì mọi request bị 401). Giá token cũng đọc từ env (`PRICE_INPUT_PER_1K`…) |
| Auth | `app/auth.py` | `APIKeyHeader(auto_error=False)` để tự trả 401 (mặc định FastAPI trả 403); `secrets.compare_digest` chống dò key qua thời gian phản hồi; chỉ lưu **fingerprint sha256** của key, không lưu key thật vào Redis/log |
| Redis | `app/redis_client.py` | `from_url` chưa mở kết nối, nên app khởi động được khi không có Redis; timeout 1s để `/ready` trả 503 nhanh |
| Rate limit | `app/rate_limiter.py` | Sorted set, sliding window 60s, trong `MULTI`: xoá cũ → **thêm trước** → đếm → TTL (nguyên tử, cùng ý với 4.4); vượt thì xoá lại request vừa thêm, trả 429 + `Retry-After` tính từ request cũ nhất |
| Cost guard | `app/cost_guard.py` | Key theo ngày + theo tháng, nên budget tự reset; `check_budget` trước khi gọi LLM, `record_cost` sau (`INCRBYFLOAT`). Hạn chế: request cuối có thể làm tổng vượt budget một chút |
| Health/Ready | `app/main.py` | `/health` không đụng Redis (luôn 200); `/ready` trả 503 khi Redis chết **hoặc đang shutdown** |
| Log | `app/main.py` | `JsonFormatter` tự viết; middleware ghi `method, path, status, ms, request_id`; bỏ qua `/health`, `/ready` để log không bị probe làm ngập |
| Shutdown | `app/main.py` + `Dockerfile` | Không tự đăng ký handler SIGTERM, để uvicorn lo; lifespan đánh dấu not-ready rồi đóng Redis. `CMD ["sh","-c","exec uvicorn ..."]`: `exec` giúp uvicorn là PID 1 nên nhận SIGTERM; `/ask` dùng `def` (bài học 5.2) |
| Docker | `Dockerfile` | Builder cài vào `/opt/venv` → runtime chỉ copy venv + `app/` + `utils/`; user `app` non-root; `HEALTHCHECK` đọc `PORT` |

---

## AI log

| # | Hỏi AI gì | Nhận được gì | Tôi tự sửa / tự kiểm tra thế nào |
|---|-----------|--------------|----------------------------------|
| 1 | Đọc repo, hướng dẫn cách làm lab Day 14 | Tóm tắt lộ trình CP0–CP8, các lưu ý K5, cách tránh mất điểm | [ĐIỀN] |
| 2 | Giải thích nguy hại của anti-pattern #3 (print/log secret), #4 (không health check), #5 (port/host cố định) | Giải thích + đối chiếu dòng code bản production | [ĐIỀN — vd: tự chạy 2 bản, so sánh log, thử `PORT=9000`] |
| 3 | Tạo khung `MISSION_ANSWERS.md` kèm gợi ý Part 1 | Bản nháp Part 1 + khung các Part còn lại | [ĐIỀN — vd: đọc lại, viết lại bằng lời mình, đối chiếu số dòng] |
| 4 | Sửa lỗi `docker build` (daemon chưa chạy, sai build context) | Bật Docker Desktop; build từ gốc repo với `-f` | [ĐIỀN] |
| 5 | Nhờ AI chạy build/run/compose Part 2 và điền output 2.2–2.4 | Output thật từ các lệnh đã chạy trên máy tôi, số MB từ `docker images` | [ĐIỀN — vd: tự chạy lại `docker images my-agent` để đối chiếu số] |
| 6 | Nhờ AI chạy 3 lệnh curl Exercise 4.1 và dán output | Output thật 401 / 403 / 200 từ server Part 4 develop trên máy tôi | [ĐIỀN] |
| 7 | Nhờ AI chạy test JWT Exercise 4.2 (token đã che) và dán output | Output thật 200 / 401 / 403 từ server Part 4 production trên máy tôi | [ĐIỀN] |
| 8 | Nhờ AI viết nháp Part 3: so sánh `railway.toml` / `render.yaml` và mô tả pipeline Cloud Run | Bảng so sánh + mô tả 4 bước pipeline | [ĐIỀN — vd: đối chiếu từng dòng với 2 file, viết lại bằng lời mình] |
| 9 | Nhờ AI chạy vòng lặp rate limit Exercise 4.3 (student + teacher) và dán output | Output thật: student 10×200 rồi 429; teacher 20×200 | [ĐIỀN] |
| 10 | Nhờ AI giải thích `cost_guard.py` và viết `check_budget` dùng Redis (Exercise 4.4) | Giải thích + code dùng `INCRBYFLOAT` nguyên tử, key theo tháng, TTL 32 ngày; chạy thử với Redis thật | [ĐIỀN — vd: tự đọc từng dòng, giải thích được race condition của cách GET-rồi-INCR] |
| 11 | Nhờ AI chạy Part 5: health/ready, test graceful shutdown bằng `docker stop`, stack 3 instance + `test_stateless.py`, thử tắt 1 instance | Output thật; phát hiện `async def` + `time.sleep` làm request thứ 2 bị cắt khi shutdown (sửa thử trên bản sao bằng `def`); nginx chờ 60s khi 1 instance chết | [ĐIỀN — vd: tự chạy lại test 2 request song song, thấy 3s/6s] |
| 12 | Nhờ AI sửa `async def` → `def` ở `05-scaling-reliability/develop/app.py` và viết các TODO Part 6 (`app/*.py`, Dockerfile, .dockerignore, compose, .env.example, railway.toml); chạy `check_production_ready.py` trong container Linux | Code đầy đủ 12 tiêu chí; output thật PASS 12/12, 41/41 checks, image 274 MB | [ĐIỀN — vd: tự đọc từng file, tự chạy lại script, thử đổi `RATE_LIMIT_PER_MINUTE` xem 429 đổi theo] |
| 13 | Nhờ AI deploy Part 6 lên Railway bằng CLI (project, Redis, biến môi trường, `railway up`, domain), chạy lệnh tự kiểm CP6 + Self-Test, viết `DEPLOYMENT.md`, cập nhật `DAY14_DELIVERY_CHECKLIST.md` | URL public; 200/200/401/200; rate limit 429 trên cloud; PASS 12/12 kèm `--public-url`. Key sinh ngẫu nhiên, đã che trong mọi output | [ĐIỀN — vd: tự mở URL `/health` trên điện thoại, tự xem Variables trên dashboard Railway] |
| 14 | Nhờ AI chạy Part 7 Bước 1 (CP7): load test 4 mức concurrency + 3 mức `MOCK_SLOW_RATE`, eval v1/v2, sửa `KNOWLEDGE_BASE` cho `security-02`/`scaling-03`, viết job CI quality gate, điền mục 1–3 `BENCHMARK_REPORT.md` | 10 file JSON trong `develop/reports/`; v2 đạt 100% không regression; số liệu bảng trích thẳng từ JSON; nhận xét dạng 💡 GỢI Ý | [ĐIỀN — vd: tự đối chiếu từng số trong báo cáo với file JSON, tự giải thích vì sao RPS giảm ở c=100] |
| 15 | Nhờ AI chạy Part 7 Bước 2 (CP8): dựng stack observability, sửa Dockerfile production (`PYTHONUSERBASE`), chạy Locust scale 1/3 instance, thí nghiệm A–E và đo thời gian alert bằng script hỏi Prometheus, tìm trace chậm/lỗi trong Jaeger + log khớp `trace_id`, đo số liệu và trả lời Exercise 7.4, copy `reports/` + `benchmark-results/` ra gốc repo, điền mục 4–6 `BENCHMARK_REPORT.md` | CSV `scale_1`/`scale_3`; 4 alert firing có thời gian đo (A 83 s, B 141 s, C 163 s, D 41 s), E không alert; 2 trace + log thật; ảnh do tôi tự chụp; nhận xét dạng 💡 GỢI Ý | [ĐIỀN — vd: tự mở Grafana/Jaeger xem lại, tự giải thích vì sao scale 3 instance không làm p95 giảm] |
