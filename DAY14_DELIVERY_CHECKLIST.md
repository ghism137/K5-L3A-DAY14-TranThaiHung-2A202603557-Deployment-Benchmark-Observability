#  Delivery Checklist — Day 14 Lab Submission

> **Student Name: Trần Thái Hưng**  
> **Student ID:2A202603557**    
> **Date: 25/11/2026**

---

##  Submission Requirements

Submit a **GitHub repository** containing:

### 1. Mission Answers (40 points)

Create a file `MISSION_ANSWERS.md` with your answers to all exercises:

```markdown
# Day 14 Lab - Mission Answers

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found
1. [Your answer]
2. [Your answer]
...

### Exercise 1.3: Comparison table
| Feature | Develop | Production | Why Important? |
|---------|---------|------------|----------------|
| Config  | ...     | ...        | ...            |
...

## Part 2: Docker

### Exercise 2.1: Dockerfile questions
1. Base image: [Your answer]
2. Working directory: [Your answer]
...

### Exercise 2.3: Image size comparison
- Develop: [X] MB
- Production: [Y] MB
- Difference: [Z]%

## Part 3: Cloud Deployment

### Exercise 3.1: Railway deployment
- URL: https://your-app.railway.app
- Screenshot: [Link to screenshot in repo]

## Part 4: API Security

### Exercise 4.1-4.3: Test results
[Paste your test outputs]

### Exercise 4.4: Cost guard implementation
[Explain your approach]

## Part 5: Scaling & Reliability

### Exercise 5.1-5.5: Implementation notes
[Your explanations and test results]
```

---

### 2. Full Source Code - Lab 06 Complete (60 points)

Your final production-ready agent, built from the skeleton in `06-lab-complete/` (xem mục **Hợp đồng** trong [06-lab-complete/README.md](06-lab-complete/README.md)):

```
your-repo/
├── app/
│   ├── main.py              # Main application
│   ├── config.py            # Configuration
│   ├── auth.py              # Authentication
│   ├── rate_limiter.py      # Rate limiting (Redis)
│   ├── cost_guard.py        # Cost protection (Redis)
│   └── redis_client.py      # Redis connection + health
├── utils/
│   └── mock_llm.py          # Mock LLM (provided)
├── check_production_ready.py  # Grading script (provided, do not modify)
├── Dockerfile               # Multi-stage build
├── docker-compose.yml       # Full stack
├── requirements.txt         # Dependencies
├── .env.example             # Environment template
├── .dockerignore            # Docker ignore
├── railway.toml             # Railway config (or render.yaml)
└── README.md                # Setup instructions
```

**Requirements:**
-  **`python check_production_ready.py` báo `PASS 12/12`** (chạy đầy đủ, có Docker) — dán phần "📋 Checklist Deliverable" của output vào `MISSION_ANSWERS.md`
-  All code runs without errors
-  Multi-stage Dockerfile (image < 500 MB)
-  API key authentication
-  Rate limiting (10 req/min)
-  Cost guard ($10/month)
-  Health + readiness checks
-  Graceful shutdown
-  Stateless design (Redis)
-  No hardcoded secrets

---

### 3. Service Domain Link

Create a file `DEPLOYMENT.md` with your deployed service information:

````markdown
# Deployment Information

## Public URL
https://your-agent.railway.app

## Platform
Railway / Render / Cloud Run

## Test Commands

### Health Check
```bash
curl https://your-agent.railway.app/health
# Expected: {"status": "ok"}
```

### API Test (with authentication)
```bash
curl -X POST https://your-agent.railway.app/ask \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test", "question": "Hello"}'
```

## Environment Variables Set
- PORT
- REDIS_URL
- AGENT_API_KEY
- LOG_LEVEL

## Screenshots
- [Deployment dashboard](screenshots/dashboard.png)
- [Service running](screenshots/running.png)
- [Test results](screenshots/test.png)
````

---

### 4. Benchmark & Observability Report — Part 7 (20 points)

Copy [06-lab-complete/benchmark-observability/BENCHMARK_REPORT_TEMPLATE.md](06-lab-complete/benchmark-observability/BENCHMARK_REPORT_TEMPLATE.md) thành `BENCHMARK_REPORT.md` và điền đầy đủ, kèm các file bằng chứng:

```
your-repo/
├── BENCHMARK_REPORT.md
├── reports/
│   ├── load_v2_c1.json ... load_v2_c100.json   # load_test.py --out
│   ├── eval_v1.json
│   ├── eval_v2.json
│   └── eval_v2_fixed.json                      # sau khi sửa knowledge base
├── benchmark-results/
│   ├── scale_1_stats.csv                       # Locust headless
│   └── scale_3_stats.csv
└── screenshots/
    ├── grafana-dashboard.png
    ├── jaeger-slow-trace.png
    ├── jaeger-error-trace.png
    └── prometheus-alert-firing.png
```

**Requirements:**
-  Load test ở 4 mức concurrency, có p50/p95/p99 và đối chiếu SLO
-  Eval v1 vs v2, sửa knowledge base để v2 đạt 100% không regression
-  Dashboard Grafana có tải, 1 trace chậm + 1 trace lỗi trong Jaeger
-  Ít nhất 2 alert firing, ghi lại thời gian phát hiện
-  Số liệu trong report khớp với file JSON/CSV

> **Cách tính điểm:** tổng thô 120 (40 + 60 + 20), quy đổi về thang 100.

---

##  Pre-Submission Checklist

> Trạng thái kiểm tra ngày 25/11/2026. Chỉ đánh `[x]` mục đã kiểm chứng bằng lệnh thật.

- [x] Repository is public (or instructor has access): `gh repo view` → `"visibility":"PUBLIC"`
- [ ] `MISSION_ANSWERS.md` completed with all exercises: Part 1–6 đã có output thật; **còn** các ô `[ĐIỀN]` tự viết (2.1 Q3–Q4, câu hỏi 4.1/4.3, luồng JWT 4.2, giải thích 5.5, cột "tự kiểm tra" của AI log) và viết lại các đoạn 💡 GỢI Ý
- [x] `DEPLOYMENT.md` has working public URL: https://agent-production-5dafbd72.up.railway.app
- [x] All source code in `app/` directory: `06-lab-complete/app/` (main, config, auth, rate_limiter, cost_guard, redis_client)
- [x] `README.md` has clear setup instructions: `06-lab-complete/README.md` (mục *Chạy local*, *Chấm bài*, *Deploy*)
- [x] No `.env` file committed (only `.env.example`): `.env` nằm trong `.gitignore`, `git ls-files` không có `.env`
- [x] No hardcoded secrets in code: script chấm ✅ "Không hard-code secret trong code"; `AGENT_API_KEY` chỉ nằm trong Railway Variables
- [x] Public URL is accessible and working: `/health` 200, `/ready` 200, `/ask` 401 khi không key / 200 khi có key
- [x] Screenshots included in `screenshots/` folder: đủ 7 ảnh: `dashboard.png`, `running.png`, `test.png` (CP6) + `grafana-dashboard.png`, `jaeger-slow-trace.png`, `jaeger-error-trace.png`, `prometheus-alert-firing.png` (Part 7, 2 alert firing)
- [ ] Repository has clear commit history: **chưa commit** bài làm
- [x] `python check_production_ready.py` → `PASS 12/12`: chạy đầy đủ (có Docker, trong container Linux), `12/12 tiêu chí · 42/42 checks` (kèm `--public-url`)
- [ ] `BENCHMARK_REPORT.md` điền đủ, có `reports/`, `benchmark-results/` và screenshot Part 7: mục 1–6 + Exercise 7.4 đã điền bằng số liệu thật; `reports/` (10 JSON) và `benchmark-results/` (CSV scale_1/scale_3) đã copy ra gốc repo theo SUBMISSION.md; ảnh đủ; **còn** viết lại các đoạn 💡 GỢI Ý bằng lời của mình

---

##  Self-Test

Before submitting, verify your deployment:

> Lệnh đã chỉnh theo README (*Lưu ý khi làm bài* số 8): lệnh gốc gọi `GET /ask` nên trả **405**, không phải 401 (đã thử: `curl $BASE/ask` → `HTTP 405`). Vì vậy dùng `POST` kèm `Content-Type: application/json`.

```bash
BASE=https://agent-production-5dafbd72.up.railway.app
AGENT_API_KEY=<key trên Railway>

# 1. Health check
curl $BASE/health
# Thực tế: {"status":"ok","version":"1.0.0","environment":"production","uptime_seconds":201.9}  -> HTTP 200

# 2. Authentication required
curl -X POST $BASE/ask -H "Content-Type: application/json" -d '{"user_id":"test","question":"Hello"}'
# Thực tế: {"detail":"Missing or invalid API key. Send header: X-API-Key: <key>"}  -> HTTP 401

# 3. With API key works
curl -X POST $BASE/ask -H "X-API-Key: $AGENT_API_KEY" -H "Content-Type: application/json" \
  -d '{"user_id":"test","question":"Hello"}'
# Thực tế: {"question":"Hello","answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé.","usage":{...}}  -> HTTP 200

# 4. Rate limiting
for i in $(seq 1 15); do
  curl -s -o /dev/null -w "%{http_code} " -X POST $BASE/ask -H "X-API-Key: $AGENT_API_KEY" \
    -H "Content-Type: application/json" -d '{"user_id":"test","question":"test"}'
done
# Thực tế: 200 200 200 200 200 200 200 200 200 429 429 429 429 429 429
# (9 lần 200 + 1 request ở bước 3 = giới hạn 10 request/phút)

# 5. Part 7 — eval quality gate (agent v2 đang chạy ở local)
cd 06-lab-complete/benchmark-observability/develop
python eval/run_eval.py --min-accuracy 1.0
# Should print: Quality gate ... ✅ PASS
# Thực tế (2026-11-25, sau khi sửa KNOWLEDGE_BASE, thêm --baseline reports/eval_v2.json --out reports/eval_v2_fixed.json):
#   Accuracy : 100.0%  (23/23) · Câu bị regression : 0
#   Quality gate (accuracy ≥ 100%, không regression): ✅ PASS   (exit code 0)
```

---

##  Submission

**Submit your GitHub repository URL:**

```
https://github.com/ghism137/K5-L3A-DAY14-TranThaiHung-2A202603557-Deployment-Benchmark-Observability
```

---

##  Quick Tips

1.  Test your public URL from a different device
2.  Make sure repository is public or instructor has access
3.  Include screenshots of working deployment
4.  Write clear commit messages
5.  Test all commands in DEPLOYMENT.md work
6.  No secrets in code or commit history

---

##  Need Help?

- Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- Review [CODE_LAB.md](CODE_LAB.md)
- Ask in office hours
- Post in discussion forum

---

**Good luck! **
