# Benchmark & Observability Report — Day 14

> Mọi con số lấy từ file đã chạy thật, không ước lượng: JSON trong [reports/](reports/) và CSV Locust trong [benchmark-results/](benchmark-results/) (bản copy từ `06-lab-complete/benchmark-observability/develop/reports/` và `production/benchmark-results/` theo SUBMISSION.md); số liệu mục 4 lấy từ Prometheus/Jaeger lúc chạy.

**Họ tên:** Trần Thái Hưng
**Ngày chạy:** 2026-11-25
**Môi trường:** Laptop Windows 11, Intel Core i3-1115G4 (2 nhân / 4 luồng), RAM 11.7 GB; Docker Desktop 29.9.3 (VM 4 vCPU / 5.7 GB). Agent v1, v2 và `load_test.py` / `run_eval.py` đều chạy trong container `python:3.11-slim` với `--network host`, nên URL vẫn là `localhost:8001` / `localhost:8002`. Máy tạo tải và agent **dùng chung CPU**.

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | < 500 ms | Lúc bình thường một request ≈ 120–180 ms LLM + ~20 ms retrieval, p95 đo được ≈ 220 ms. Đặt 500 ms để có khoảng dư cho lúc tải cao, mà người dùng vẫn thấy phản hồi gần như tức thì. Dùng p95 chứ không dùng average vì average che mất nhóm người dùng phải chờ lâu (xem 2.2) |
| Error rate `/ask` | < 2 % | Mock LLM có ~1% lỗi upstream (`MOCK_ERROR_RATE=0.01`). Đặt gấp đôi mức nền để có error budget, không báo động vì vài lỗi ngẫu nhiên |
| Accuracy trên golden dataset | ≥ 80 %, **không có câu regression** | 80% là ngưỡng mặc định của quality gate. Điều kiện "không regression" quan trọng hơn con số: bản mới không được làm sai câu mà bản cũ làm đúng. Khi release sau khi sửa KB, tôi nâng gate lên 100% (`--min-accuracy 1.0`) |

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2)

Lệnh: `python load_test.py --url http://localhost:8002 --requests 300 --concurrency <c> --out reports/load_v2_c<c>.json`

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | 4.58 | 189.9 | 218.0 | 1661.3 | 0.33% | ✅ PASS |
| 10 | 49.2 | 191.8 | 218.7 | 228.3 | 0.00% | ✅ PASS |
| 50 | 86.75 | 233.9 | 726.9 | 1713.5 | 0.67% | ❌ FAIL (p95) |
| 100 | 48.31 | 1095.0 | 4249.4 | 5178.5 | 0.00% | ❌ FAIL (p95) |

**Nhận xét:** RPS có tăng tuyến tính theo concurrency không? Vì sao?

- **Từ 1 lên 10: tuyến tính.** RPS tăng ×10.7 (4.58 → 49.2) trong khi p50 gần như giữ nguyên (190 ms). Lý do: mock LLM là `asyncio.sleep`, tức là phần lớn thời gian request chỉ **chờ I/O**, nên 1 event loop phục vụ 10 request song song mà không tốn thêm CPU. Theo định luật Little: RPS ≈ concurrency / latency = 10 / 0.2 s ≈ 50.
- **Lên 50: dưới tuyến tính.** RPS chỉ ×1.76 (49 → 87) dù concurrency ×5. p50 bắt đầu tăng (234 ms) và p95 vượt SLO (727 ms): request đã phải **xếp hàng** chờ CPU.
- **Lên 100: RPS giảm** (87 → 48) và p50 vọt lên 1095 ms. Hệ thống đã quá điểm bão hoà: chỉ có **1 tiến trình uvicorn** (1 nhân CPU) phải lo JSON, log, metrics cho 100 kết nối, trong khi load generator chạy chung 4 vCPU với agent. Tăng concurrency lúc này chỉ làm hàng đợi dài thêm, throughput không tăng.
- Kết luận: điểm hoạt động tốt nhất trên máy này nằm khoảng **concurrency 10–50**. Muốn chịu tải cao hơn thì phải scale ngang (nhiều worker / instance), xem phần 5.
- Lưu ý: ở c=1 p99 = 1661 ms dù rất nhẹ tải. Đó là ~3% request "slow" của mock (`MOCK_SLOW_RATE`), không phải do quá tải.

### 2.2 Tail latency

Lệnh: khởi động lại v2 với `MOCK_SLOW_RATE=<x>`, rồi `load_test.py --requests 300 --concurrency 20 --out reports/load_v2_slow_<x>.json`

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | 191.6 | 221.0 | 242.9 |
| 0.03 (mặc định) | 228.7 | 232.4 | 1703.9 |
| 0.1 | 343.0 | 1691.7 | 1717.6 |

(p50 lần lượt 192.7 / 194.9 / 195.5 ms; RPS 101.17 / 62.43 / 47.86)

**Nhận xét:** Chỉ số nào nhạy nhất với request chậm? Vì sao SLO không nên đặt theo average?

- **p99 nhạy nhất.** Chỉ cần 3% request chậm là p99 nhảy ×7 (243 → 1704 ms), trong khi avg chỉ tăng 19% (192 → 229 ms) và p50 **gần như không đổi** (193 → 195 ms). Khi tỉ lệ chậm lên 10% (vượt 5%), p95 cũng vọt lên 1692 ms và vi phạm SLO.
- **Average đánh lừa:** với 3% slow, avg = 229 ms trông "ổn", nhưng cứ 100 người thì 3 người phải chờ ~1.7 s. Average bị phần đông request nhanh kéo xuống, nên che mất trải nghiệm tệ nhất, mà người dùng thì nhớ lần chờ lâu chứ không nhớ trung bình. SLO theo p95/p99 cam kết trực tiếp "95%/99% người dùng nhận phản hồi dưới X ms".
- Tail latency còn **làm giảm throughput**: RPS từ 101 xuống 48 vì mỗi request chậm giữ một "slot" concurrency lâu gấp ~9 lần.

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 4.3% (1/23) | 91.3% (21/23) | **100.0% (23/23)** |
| Avg tokens / câu | 58.4 | 108.8 | 117.0 |
| Tổng cost (USD) | 0.000422 | 0.000757 | 0.000820 |
| Cost / câu đúng (USD) | 0.00042195 | 0.00003607 | 0.00003563 |
| Quality gate | ❌ FAIL (gate 80%) | ✅ PASS (gate 80%, baseline v1, 0 regression) | ✅ PASS (gate 100%, baseline v2, 0 regression) |

File: `reports/eval_v1.json`, `reports/eval_v2.json`, `reports/eval_v2_fixed.json`.

**Những câu v2 trả lời sai ban đầu và cách bạn sửa:**

| ID | Keyword bị thiếu | Bạn đã sửa gì |
|---|---|---|
| `security-02` ("JWT khác gì API key trong xác thực?") | `token`, `hết hạn`, `chữ ký` (score 0.00) | Retrieval không khớp tài liệu nào nên agent trả câu chung chung. Thêm entry `(["jwt", "json web token"], ...)` vào `KNOWLEDGE_BASE` trong `utils/mock_llm.py`: JWT là **token** có thời điểm **hết hạn** (`exp`), được ký bằng **chữ ký** số; API key là chuỗi cố định |
| `scaling-03` ("Kubernetes HPA scale dựa trên những chỉ số nào?") | `cpu`, `memory`, `custom metrics` (score 0.00) | Cùng nguyên nhân. Thêm entry `(["hpa", "autoscaler", "autoscaling"], ...)`: HPA scale theo **CPU**, **memory** hoặc **custom metrics** (qua Prometheus adapter) |

Trước khi thêm, tôi kiểm tra `jwt`, `hpa` chỉ xuất hiện 1 lần trong `golden_dataset.jsonl` (đúng câu cần sửa), nên entry mới không "cướp" retrieval của câu khác. Kết quả `--baseline reports/eval_v2.json`: **cải thiện 2 câu, regression 0**. Không sửa `golden_dataset.jsonl`.

**Quality gate trong CI (bài tập 4):** chạy eval của v1 với `--baseline reports/eval_v2.json` thì accuracy 4.3%, **20 câu regression**, `Quality gate ❌ FAIL`, **exit code 1**. Job CI: [.github/workflows/eval-quality-gate.yml](.github/workflows/eval-quality-gate.yml) chạy khi PR sửa `benchmark-observability/develop/**`: khởi động agent v2 (`MOCK_ERROR_RATE=0` để gate không fail ngẫu nhiên vì lỗi giả lập), rồi `run_eval.py --min-accuracy 1.0 --baseline reports/eval_v2_fixed.json`. Exit code ≠ 0 làm step fail, job fail; bật branch protection *Require status checks* thì PR không merge được.

**Nhận xét về trade-off chất lượng / chi phí / latency giữa v1 và v2:**

💡 GỢI Ý:
- **Chất lượng:** v2 (RAG) tăng accuracy từ 4.3% lên 91.3% (sửa KB thì lên 100%). v1 trả lời chung chung, gần như vô dụng.
- **Chi phí:** v2 tốn **gấp ~1.9 lần token** mỗi câu (58.4 → 108.8) vì prompt có thêm context, nên tổng cost cũng gấp ~1.8 lần. Nhưng **cost / câu đúng rẻ hơn ~11.7 lần** (0.000422 → 0.0000361 USD). Tiền trả cho v1 phần lớn là tiền cho câu sai. Vì vậy so hai phiên bản phải dùng "cost / câu đúng", không dùng "cost / câu".
- **Latency:** v2 thêm bước retrieval (~20 ms) nên p50 chậm hơn ~15 ms (170 → 185 ms), không đáng kể so với SLO 500 ms. (p95 của eval v1 = 1513 ms chỉ do 2 câu trúng request "slow", mẫu 23 câu quá nhỏ để kết luận về latency; latency phải đo bằng load test.)
- Sửa KB làm avg tokens tăng thêm 8.2 và tổng cost tăng 0.000063 USD, nhưng cost / câu đúng vẫn **giảm** (0.00003607 → 0.00003563). Đáng làm.

---

## 4. Observability stack (production)

### 4.1 Screenshot

Stack: `docker compose -p k5-day14-observability up -d --scale agent=2`. Tải nền là Locust headless **20 user** (container riêng, cùng network `obs_net`, gọi qua nginx). Baseline ở 20 user: 12.3 req/s, lỗi 1.07%, p95 0.29 s, chi phí ≈ $1.52/giờ, không có alert nào.

- [x] Dashboard Grafana khi đang có tải (thấy rõ Golden Signals): [screenshots/grafana-dashboard.png](screenshots/grafana-dashboard.png), chụp lúc A + B đang bật (10 req/s, error rate 21.38%, p95 1.89 s, 2 instance)
- [x] Một trace chậm trong Jaeger (thấy span nào chiếm thời gian): [screenshots/jaeger-slow-trace.png](screenshots/jaeger-slow-trace.png)
- [x] Một trace lỗi trong Jaeger (có event `exception`): [screenshots/jaeger-error-trace.png](screenshots/jaeger-error-trace.png)
- [x] Trang Alerts của Prometheus với ít nhất 1 alert đang **firing**: [screenshots/prometheus-alert-firing.png](screenshots/prometheus-alert-firing.png), **2 alert firing** (`AgentHighErrorRate`, `AgentHighLatencyP95`)

### Exercise 7.4: Đọc dashboard ở trạng thái bình thường

Đo lúc 02:37 ngày 2026-11-26 với `.env` mặc định (`.env.example`), 2 instance, Locust **30 user / ramp 5**, chạy ~3 phút. Số liệu lấy bằng cùng các query PromQL với panel Grafana, cửa sổ 2 phút:

| Chỉ số | Giá trị |
|---|---|
| Traffic `/ask` | 18.41 req/s |
| avg / p50 / p95 / p99 | 241.6 ms / 174.9 ms / 295.7 ms / 1860.5 ms |
| Error rate | 1.37% |
| Requests/s theo instance | `172.18.0.3:8000` 9.2174, `172.18.0.8:8000` 9.2174 |
| Tokens/s | input 1339.1, output 712.4 (input/output ≈ 1.88) |

1. **p95 và avg là bao nhiêu? Khoảng cách nói lên điều gì?**
   💡 GỢI Ý: avg 242 ms, p95 296 ms, nhưng p50 chỉ 175 ms và p99 vọt lên 1861 ms. avg **lớn hơn p50 khá nhiều** vì bị ~3% request "slow" (+1.5 s) kéo lên: phân phối latency lệch phải, có đuôi dài. avg không đại diện cho ai cả: đa số người dùng nhanh hơn avg, còn số ít chậm thì chậm hơn avg rất nhiều. Vì vậy phải nhìn percentile, nhất là p99, để thấy tail.
2. **Nginx có chia đều traffic cho 2 instance không?**
   💡 GỢI Ý: Có, **đều tuyệt đối** (9.2174 = 9.2174 req/s). Nginx dùng round-robin mặc định trong `upstream agent_cluster`, request lần lượt vào từng instance. Đều được vì các request gần như giống nhau; nếu request dài ngắn rất khác nhau thì nên dùng `least_conn`.
3. **Vì sao input tokens/s lớn hơn output tokens/s?**
   💡 GỢI Ý: Input gấp ~1.88 lần output vì agent v2 là RAG: prompt gửi LLM = câu hỏi + **context lấy từ retrieval** (+ chỉ dẫn hệ thống), còn câu trả lời ngắn. Thí nghiệm E xác nhận: v1 không có context thì input/request giảm từ 73.7 xuống 36.2 token. Trong LLM thật, output đắt hơn input (ở đây 0.0006 so với 0.00015 USD/1K), nên dù input nhiều token hơn, chi phí vẫn phải tính riêng hai loại.
4. **`curl http://localhost:8080/metrics` trả về gì? Vì sao?**
   💡 GỢI Ý: Trả **`HTTP/1.1 404 Not Found`** (trang 404 của `nginx/1.28.3`). Trong [nginx.conf](06-lab-complete/benchmark-observability/production/nginx/nginx.conf) có `location = /metrics { return 404; }`. `/metrics` chỉ dành cho Prometheus, nó scrape **trực tiếp** từng container trong mạng nội bộ `obs_net` (gọi `http://localhost:8000/metrics` bên trong agent vẫn ra `# HELP python_gc_objects_collected_total ...`). Không public vì metric lộ thông tin nội bộ: route, lưu lượng, phiên bản, chi phí, giúp kẻ tấn công dò hệ thống. Ngoài ra, nếu đi qua nginx thì mỗi lần scrape trúng một instance ngẫu nhiên, số liệu sẽ sai.

### 4.2 Thí nghiệm "phá hệ thống"

Cách đo: sửa `.env`, chạy `docker compose up -d --scale agent=2 agent`, lấy t=0 là lúc container agent mới khởi động (`docker inspect .State.StartedAt`); với D, t=0 là lúc `docker pause`. Một script hỏi `GET /api/v1/alerts` của Prometheus mỗi 5 s và ghi lại lúc alert chuyển sang `pending` và `firing`.

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` (critical, > 5%, `for: 1m`) | pending 23 s → **firing 83 s** | *Error rate* (lên 17.8%) và *Requests/s theo status code* (đường 503 tăng) |
| B | `MOCK_SLOW_RATE=0.3` | `AgentHighLatencyP95` (warning, p95 > 1 s, `for: 2m`) | pending 21 s → **firing 141 s** (đo lại lần 2: 21 s → 142 s) | *Latency /ask p50/p95/p99* (p95 lên 1.89 s, p50 gần như không đổi) |
| C | `LLM_MODEL=mock-llm-large` | `LLMCostBurnRateHigh` (warning, > $2/giờ, `for: 2m`) | pending 43 s → **firing 163 s** | *Cost burn rate (USD/giờ)*: $1.52 → **$22.65/giờ** (×14.9); *LLM latency p95 theo model* (p95 /ask 0.29 → 0.66 s) |
| D | `docker pause` 1 instance | `AgentInstanceDown` (critical, `up == 0`, `for: 30s`) | pending 11 s → **firing 41 s**; `docker unpause` thì alert hết sau ~3 s | *Instances up* (2 → 1) và *Requests/s theo instance*; RPS tổng giảm 12.3 → 7.8 |
| E | `AGENT_VERSION=v1` | **Không có** | — | *Retrieval hit ratio* **mất dữ liệu** (v1 không retrieve); *Tokens/s* giảm |

Quan sát thêm:

- **Thời gian tới firing = thời gian để biểu thức vượt ngưỡng + `for`.** Cột pending cho thấy phần đầu (11–43 s, do cửa sổ `rate()` cần dữ liệu mới đủ để vượt ngưỡng), phần còn lại đúng bằng `for` (30 s / 1 m / 2 m). C chậm nhất vì dùng `rate(...[5m])`: cửa sổ 5 phút còn trộn chi phí cũ thấp.
- **D, nginx không chuyển hướng ngay.** Container bị `pause` vẫn nhận kết nối TCP (kernel bắt tay hộ), nên `proxy_connect_timeout 2s` không có tác dụng. nginx phải chờ hết `proxy_read_timeout 10s` mới thử instance còn lại (`proxy_next_upstream error timeout`). Trong ~50 s pause (02:12:39 → 02:13:29), log nginx có **19 dòng `upstream timed out`**, nên RPS tụt dù vẫn còn 1 instance khoẻ.
- **Vì sao lỗi timeout / 504 ở nginx không hiện trên metric của agent?** 💡 GỢI Ý: metric `http_requests_total` do **chính agent** đếm khi nó xử lý xong request. Request bị treo ở instance đang pause không bao giờ được agent đó trả lời, nên không có dòng nào trong metric; instance còn lại chỉ thấy request retry (status 200). Lỗi chỉ tồn tại ở tầng nginx. Phía người dùng thấy request chậm 10 s (hoặc 504 nếu cả 2 instance cùng treo), nhưng dashboard của agent vẫn báo error rate thấp. Cách khắc phục: giám sát thêm từ phía load balancer (nginx/ingress exporter, đếm 5xx và `upstream_response_time`), hoặc synthetic check gọi từ ngoài vào giống người dùng.
- **E, số liệu so sánh** (Prometheus, cửa sổ 2 phút, cùng tải 20 user):

  | Chỉ số | v2 | v1 |
  |---|---|---|
  | Retrieval hit ratio | 88.9% (10.48 hit/s, 1.31 miss/s) | không có (metric trống) |
  | Token / request (input + output) | 73.7 + 39.2 = 112.9 | 36.2 + 19.8 = 56.0 |
  | Cost / request (USD) | 0.000035 | 0.000017 |
  | p95 /ask | 0.297 s | 0.199 s |
  | Error rate | 0.68% | 0.69% |

- **Ngưỡng `LLMCostBurnRateHigh` > $2/giờ quá sát mức bình thường.** Với 30 user và model *small*, chi phí ≈ $2.29/giờ (cửa sổ 1 m) và alert đã firing dù hệ thống hoàn toàn khoẻ. Tôi phải giảm tải nền xuống 20 user (≈ $1.5/giờ) mới có baseline sạch. Trong production, alert kiểu này gây *alert fatigue*: ngưỡng nên tính từ ngân sách (vd ngân sách tháng / 720 giờ × hệ số) chứ không phải một số cố định.
- **Sửa Dockerfile production:** image mẫu crash-loop với `No module named 'uvicorn'`. `useradd -d /app` làm `HOME=/app`, nên Python tìm user site-packages ở `/app/.local`, trong khi package được copy vào `/home/agent/.local`. Tôi thêm `ENV PYTHONUSERBASE=/home/agent/.local`.

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**

💡 GỢI Ý:
- E là **lỗi chất lượng, không phải lỗi vận hành**: mọi golden signal đều trông *tốt hơn* (p95 nhanh hơn 33%, cost/request rẻ một nửa, error rate không đổi), nhưng accuracy thật rơi từ 91.3% xuống 4.3% (phần 3). Alert dựa trên latency/error/cost không bao giờ bắt được.
- Cách phát hiện:
  1. **Chặn trước khi deploy:** quality gate trong CI (`run_eval.py --min-accuracy ... --baseline ...`), chính là bài tập 4. v1 có 20 câu regression nên exit code 1 và không merge được.
  2. **Alert theo metric "proxy chất lượng":** retrieval hit ratio. Ví dụ `sum(rate(agent_retrieval_total{result="hit"}[5m])) / sum(rate(agent_retrieval_total[5m])) < 0.7`, và thêm `absent(agent_retrieval_total)` vì ở E metric **biến mất hẳn**. Ngoài ra alert khi tokens/request lệch quá xa baseline (giảm 50% đột ngột là đáng ngờ).
  3. **Online eval:** định kỳ (vd mỗi 15 phút) chạy một phần golden dataset vào production, hoặc dùng LLM-as-judge chấm một mẫu traffic thật, rồi xuất accuracy thành metric Prometheus để đặt alert.
  4. **Tín hiệu từ người dùng:** tỷ lệ 👎, tỷ lệ hỏi lại, câu trả lời kiểu "tôi không biết". Gắn nhãn `agent_version` vào mọi metric để so sánh v1 và v2 khi canary.

### 4.3 Debug bằng trace

Lúc A + B đang bật, tìm trong Jaeger bằng API `GET /api/v3/traces` (service `observable-agent`, `duration_min`), lấy trace chậm nhất **có log khớp**:

- `trace_id`: `3d4be0275bde28737c3d40b9e595d8b2` (instance `dd88edb520cb`)
- Tổng thời gian: **1734.7 ms** (`POST /ask`, status 200)
- Span chiếm nhiều thời gian nhất: **`chat mock-llm-small`** (**1656.6 ms, 95.5%**; input 37 / output 20 token). Cây span: `POST /ask` 1734.7 ms → `agent.run` 1681.9 ms (97.0%) → `agent.retrieve_context` 25.0 ms (1.4%) + `chat mock-llm-small` 1656.6 ms (95.5%)
- Dòng log tương ứng (grep theo `trace_id`):

```json
{"ts": "2026-11-25T16:01:26.421391+00:00", "level": "INFO", "service": "observable-agent", "instance": "dd88edb520cb", "event": "llm_call", "trace_id": "3d4be0275bde28737c3d40b9e595d8b2", "span_id": "8cff58e4641b6b0d", "request_id": "62817ea87cda", "model": "mock-llm-small", "agent_version": "v2", "input_tokens": 37, "output_tokens": 20, "cost_usd": 1.8e-05, "llm_ms": 1655.9}
{"ts": "2026-11-25T16:01:26.421916+00:00", "level": "INFO", "service": "observable-agent", "instance": "dd88edb520cb", "event": "http_request", "trace_id": "3d4be0275bde28737c3d40b9e595d8b2", "method": "POST", "route": "/ask", "status": 200, "ms": 1734.2}
```

Kết luận: nút thắt là **LLM call** chứ không phải retrieval hay code của agent. Đây là một request "slow" (tail latency) của mock LLM. Log `llm_ms=1655.9` khớp với span `chat` (1656.6 ms). Prompt chỉ 37 token nên không phải do prompt dài. Muốn giảm thì cần timeout + retry/hedging cho LLM call, không phải tối ưu retrieval.

**Trace lỗi** (ảnh `jaeger-error-trace.png`): `7808c90a5e8092c8f7f3912fc8c4ec79`, 104.5 ms, status 503. Span `agent.run` và `chat mock-llm-small` có status error và event `exception`. Log cùng `trace_id`: `"event": "llm_error", "error": "Upstream LLM error: 503 Service Unavailable (mock)"`, sau đó là `"event": "http_request", "status": 503, "ms": 103.9`. Lỗi đến sau ~100 ms, sớm hơn response thành công, vì mock trả lỗi ở nửa thời gian latency.

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | 60.01 | 190 | 240 | 1700 | 60 / 7173 (0.84%) |
| 3 | 59.74 | 190 | 240 | 1700 | 58 / 7137 (0.81%) |

Số liệu là dòng `POST /ask` trong [benchmark-results/scale_1_stats.csv](benchmark-results/scale_1_stats.csv) và [scale_3_stats.csv](benchmark-results/scale_3_stats.csv) (dòng *Aggregated* có thêm `/health`: 66.18 và 65.84 RPS). Toàn bộ failures là `503 Service Unavailable`, tức lỗi giả lập ~1% của mock LLM (`scale_*_failures.csv`), không phải lỗi do quá tải. Lệnh: `docker compose run --rm locust ... --headless -u 100 -r 10 -t 2m --csv /mnt/results/scale_<n>` sau `--scale agent=<n>`, với `.env` mặc định.

**Giải thích kết quả:** Scale có cải thiện p95 không? Nút thắt nằm ở đâu?

💡 GỢI Ý:
- **Không cải thiện:** RPS, p50, p95, p99 của 1 và 3 instance gần như **trùng nhau**. Lý do là **1 instance chưa hề bão hoà**, nên thêm instance không có gì để cải thiện.
- **Nút thắt nằm ở load generator, không phải agent.** Locust là tải *closed-loop*: mỗi user gửi request, chờ response, rồi nghỉ `wait_time = between(0.5, 2)` (trung bình 1.25 s). Theo định luật Little: RPS tối đa ≈ 100 user / (1.25 s + ~0.21 s latency) ≈ **68 req/s**. Đo được 66 req/s tổng, đúng sát trần đó. 100 user này chỉ tạo ra ~60 req/s cho `/ask`, trong khi phần 2.1 cho thấy 1 process đã chịu được ~87 req/s.
- **p95/p99 do LLM quyết định:** p95 = 240 ms ≈ latency mock LLM (120 ms + jitter) + retrieval. p99 = 1700 ms là ~3% request "slow" (`MOCK_SLOW_RATE=0.03`, +1500 ms). Thêm instance **không thể** làm LLM upstream nhanh hơn. Muốn giảm tail phải xử lý ở tầng LLM (timeout, hedged request, cache, model nhanh hơn).
- **Muốn thấy scale có tác dụng** thì phải đẩy 1 instance qua điểm bão hoà: tăng user (vd 300–500) hoặc giảm `wait_time`, và chạy Locust ở máy khác (ở đây Locust, nginx, 3 agent, Prometheus, Jaeger dùng chung 4 vCPU). Khi đó 1 instance sẽ có p95 tăng vọt như mức c=100 ở phần 2.1, còn 3 instance chia tải sẽ giữ p95 thấp.
- Lưu ý: scale ngang giúp **throughput và khả năng chịu lỗi** (thí nghiệm D: còn 1 instance thì vẫn phục vụ), không giúp latency của từng request khi chưa quá tải.

---

## 6. Kết luận

- 3 điều bạn học được về benchmark & observability:

  💡 GỢI Ý:
  1. **Trung bình nói dối, phải nhìn percentile và tail.** Chỉ 3% request chậm làm p99 ×7 trong khi avg chỉ +19% và p50 không đổi (2.2). Trace (4.3) cho thấy 95.5% thời gian của request chậm nằm ở LLM call. Không có trace thì chỉ đoán.
  2. **Benchmark phải hiểu mô hình tải trước khi kết luận.** Scale 1 → 3 instance "không cải thiện gì" vì Locust closed-loop chỉ tạo được ~68 req/s (định luật Little), chứ không phải vì scale vô dụng. Load generator chạy chung máy với hệ thống cũng là một biến gây nhiễu.
  3. **Monitoring vận hành không bắt được lỗi chất lượng.** Thí nghiệm E: v1 rẻ hơn, nhanh hơn, không alert nào kêu, nhưng accuracy 4.3%. Cần eval + quality gate trong CI và metric proxy chất lượng (retrieval hit ratio). Ngược lại, alert đặt ngưỡng sai (cost > $2/giờ) thì kêu cả khi hệ thống khoẻ: ngưỡng alert cũng cần được "benchmark".

- Nếu đưa agent này lên production thật, bạn sẽ thêm metric / alert nào nữa?

💡 GỢI Ý:
- **Chất lượng:** `RetrievalHitRatioLow` (hit ratio < 70% trong 10 m) + `absent(agent_retrieval_total)`; metric `eval_accuracy` từ online eval định kỳ, alert khi < 80%; tỷ lệ feedback 👎.
- **Cost theo ngân sách:** thay ngưỡng $2/giờ cố định bằng *budget burn rate* (vd chi phí 1 h > ngân sách tháng / 720 × 3), kèm cost theo `user_id`/`model` để bắt một user lạm dụng (khớp cost guard ở Part 6).
- **Latency theo SLO burn rate** (multi-window, vd 1 h và 5 m) thay cho ngưỡng p95 tĩnh, để giảm alert giả nhưng vẫn bắt sự cố nhanh.
- **Saturation:** in-flight requests / instance, độ dài hàng đợi, CPU/memory container; `nginx upstream timeout` rate (thí nghiệm D cho thấy instance treo tốn 10 s mỗi request trước khi failover); giảm `proxy_read_timeout` và thêm `max_fails`/health check chủ động.
- **Phụ thuộc ngoài:** error rate và latency của LLM provider tách theo `model` + mã lỗi (429 rate limit khác 503), alert riêng để phân biệt "lỗi của mình" với "lỗi của provider"; Redis `up` / latency (rate limiter và cost guard phụ thuộc Redis).
- **Rate limit / auth:** tỷ lệ 401/429 tăng đột biến (dấu hiệu bị dò key hoặc client lỗi).
