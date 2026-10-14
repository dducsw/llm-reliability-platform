# Datadog Design — LLM Reliability Platform

> Tư duy thiết kế: Datadog không phải "dashboard đẹp". Datadog là **vòng lặp tín hiệu** — Detect → Investigate → Respond — mỗi tính năng phục vụ đúng một bước trong vòng lặp đó.

---

## 1. Tổng quan Signal Flow

```
Client Request
    ↓
LLM Gateway  ──── APM Trace ──────────────────────────────→ Datadog APM
    │                                                            │
    ├── Custom Metrics (latency, error, token) ──────────→ Datadog Metrics
    │                                                            │
    ├── Structured Logs (request/response/error) ────────→ Datadog Logs
    │                                                            │
    └── LLM Provider API ──── APM Span ──────────────────→ Datadog APM
                                                                 │
                                                    Datadog Monitor/Alert
                                                                 │
                                              Webhook → Gateway (auto-recover)
```

**Nguyên tắc:** Mọi signal đều gắn `provider`, `model`, `incident_id` tag → correlation không cần manual join.

---

## 2. Custom Metrics — Nguồn sự thật cho SLO

Gửi từ Gateway qua **Datadog Agent** (StatsD protocol). Không dùng APM metric tự động vì cần tag `provider` + `model` chính xác.

### 2.1. Danh sách metrics

| Metric | Type | Tags | Mô tả |
| :--- | :--- | :--- | :--- |
| `llm.request.latency` | Distribution | `provider`, `model`, `status` | End-to-end latency (ms) — tự tính P50/P95/P99 |
| `llm.request.ttft` | Distribution | `provider`, `model` | Time To First Token (ms) |
| `llm.request.count` | Count | `provider`, `model`, `status` | Số request theo status |
| `llm.request.error_rate` | Gauge | `provider`, `model` | Error rate % — tính từ MongoDB, push mỗi phút |
| `llm.tokens.total` | Count | `provider`, `model`, `direction` | Token usage (input/output) |
| `llm.cost.usd` | Gauge | `provider`, `model` | Chi phí ước tính USD |
| `llm.slo.burn_rate` | Gauge | `provider`, `model`, `window` | Burn rate theo window (1h, 6h) |
| `llm.circuit_breaker.state` | Gauge | `provider`, `model` | 0=closed, 1=open, 2=half-open |
| `llm.failover.count` | Count | `from_provider`, `to_provider` | Số lần failover |

### 2.2. Gửi metric từ Gateway (Python DogStatsD)

```python
from datadog import statsd

def record_probe(result: dict):
    tags = [
        f"provider:{result['provider']}",
        f"model:{result['model']}",
        f"status:{result['status']}"
    ]

    # Distribution = Datadog tự tính P50/P95/P99 server-side
    if result["latency_ms"] is not None:
        statsd.distribution("llm.request.latency", result["latency_ms"], tags=tags)

    if result["ttft_ms"] is not None:
        statsd.distribution("llm.request.ttft", result["ttft_ms"], tags=tags)

    statsd.increment("llm.request.count", tags=tags)
```

> **Dùng `distribution` thay `histogram`** — Distribution tính percentile chính xác hơn trên distributed hosts. Histogram chỉ approximate khi nhiều agent.

---

## 3. APM & Distributed Tracing — Investigate Step

**Mục tiêu:** Trace trọn vẹn `Client → Gateway → LLM Provider → Client`. Khi sự cố xảy ra, xem ngay span nào fail, tại layer nào, bao lâu.

### 3.1. Instrumentation (Python ddtrace)

```python
from ddtrace import tracer, patch_all
patch_all()  # auto-instrument requests, FastAPI, pymongo

@tracer.wrap(service="llm-gateway", resource="proxy_request")
async def proxy_to_provider(provider: str, model: str, payload: dict):
    with tracer.trace("llm.provider.call", service="llm-gateway") as span:
        span.set_tag("provider", provider)
        span.set_tag("model", model)
        span.set_tag("synthetic", payload.get("synthetic", False))

        try:
            response = await call_provider(provider, model, payload)
            span.set_tag("status", "healthy")
            span.set_metric("ttft_ms", response.ttft_ms)
            span.set_metric("latency_ms", response.latency_ms)
            span.set_metric("tokens_per_sec", response.tokens_per_sec)
            return response

        except ProviderError as e:
            span.set_tag("status", "error")
            span.set_tag("error.type", type(e).__name__)
            span.error = 1
            raise
```

### 3.2. Span hierarchy

```
llm-gateway  proxy_request          500ms total
  └─ llm-gateway  llm.provider.call  480ms
       └─ http.request (openai)       480ms ← SPAN BỊ LỖI
```

Datadog APM hiển thị ngay: lỗi ở `http.request` → provider-side, không phải gateway bug.

### 3.3. Trace → Log Correlation

Mỗi log line inject `dd.trace_id` + `dd.span_id` tự động qua `ddtrace`:

```python
import logging
from ddtrace import tracer

log = logging.getLogger(__name__)

# Log này tự gắn trace_id — trong Datadog Logs click "View Trace" → jump sang APM
log.error("Provider call failed", extra={
    "provider": provider,
    "model": model,
    "error": str(e),
    "dd.trace_id": tracer.current_trace_id(),
    "dd.span_id": tracer.current_span_id()
})
```

---

## 4. Log Management — Structured Logs

**Nguyên tắc:** Mọi log là JSON. Không log free-text. Tag nhất quán với metrics → faceted search.

### 4.1. Log schema

```json
{
  "timestamp": "2026-10-20T10:15:00.123Z",
  "level": "error",
  "service": "llm-gateway",
  "provider": "openai",
  "model": "openai/gpt-4o",
  "status": "error",
  "latency_ms": null,
  "error_type": "ConnectionTimeout",
  "error_message": "Read timeout after 30s",
  "request_id": "req_abc123",
  "dd.trace_id": "4293829394",
  "dd.span_id": "8293012934",
  "incident_id": "67abc..."
}
```

### 4.2. Log-based Metric (tiết kiệm custom metric quota)

Trong Datadog Logs, tạo **Log-based Metric** từ error logs:

```
# Tạo metric llm.log.error_count từ logs có status:error
Filter: @provider:* @status:error
Group by: @provider, @model
```

→ Không cần gateway push metric riêng cho error count — dùng log làm nguồn sự thật.

### 4.3. Saved Searches cho Investigate

| Saved Search | Filter | Dùng khi |
| :--- | :--- | :--- |
| OpenAI Errors | `service:llm-gateway @provider:openai @status:error` | Provider down |
| Timeout Pattern | `service:llm-gateway @error_type:*Timeout*` | Latency investigation |
| Failover Events | `service:llm-gateway @level:info @action:failover` | Recovery audit |
| High Latency | `service:llm-gateway @latency_ms:>5000` | SLO breach investigation |

---

## 5. Monitors & Alerts — Detect Step

Thiết kế theo **Dual-window burn rate** (Google SRE) để tránh false positive.

### 5.1. Monitor 1 — Fast Burn Rate (Critical, pager-worthy)

```yaml
name: "[LLM] SLO Fast Burn Rate Critical — {{provider}} / {{model}}"
type: metric alert
query: >
  avg(last_1h):
    sum:llm.slo.burn_rate{window:1h} by {provider,model}
  > 14
message: |
  🚨 Error budget đang cạn nhanh
  Provider: {{provider.name}} | Model: {{model.name}}
  Burn rate 1h: {{value}}x (threshold: 14x)
  → Error budget sẽ cạn trong < 1 giờ nếu tiếp diễn
  @pagerduty-oncall @slack-incident-channel
notify_no_data: false
evaluation_delay: 60
thresholds:
  critical: 14
  warning: 10
```

### 5.2. Monitor 2 — Slow Burn Rate (Warning, async alert)

```yaml
name: "[LLM] SLO Slow Burn Rate Warning — {{provider}} / {{model}}"
query: >
  avg(last_6h):
    sum:llm.slo.burn_rate{window:6h} by {provider,model}
  > 6
thresholds:
  critical: 6
  warning: 3
message: |
  ⚠️ Error budget burn rate cao bất thường (6h window)
  Kiểm tra trend trước khi escalate
  @slack-sre-channel
```

### 5.3. Monitor 3 — P95 Latency SLO Breach

```yaml
name: "[LLM] P95 Latency SLO Breach — {{model}}"
type: metric alert
query: >
  p95(last_15m):
    distribution metric llm.request.latency{status:healthy}
    by {provider,model}
  > 3000
thresholds:
  critical: 3000   # SLO threshold
  warning: 2000    # cảnh báo sớm
```

### 5.4. Monitor 4 — Circuit Breaker OPEN (Recovery confirmation)

```yaml
name: "[LLM] Circuit Breaker OPEN — {{provider}} / {{model}}"
query: >
  max(last_5m):
    llm.circuit_breaker.state{*} by {provider,model}
  >= 1
message: |
  🔴 Circuit breaker OPEN
  Gateway đã dừng gửi request sang {{provider.name}}
  Failover sang: {{fallback_provider}}
  Incident: {{incident_id}}
```

### 5.5. Webhook → Gateway (Automated Recovery Loop)

Monitor alert → Datadog Webhook → Gateway `/api/recovery/trigger`:

```python
# Gateway endpoint nhận webhook từ Datadog
@app.post("/api/recovery/trigger")
async def trigger_recovery(payload: DatadogWebhookPayload):
    # Datadog gửi alert context
    provider = payload.tags.get("provider")
    model = payload.tags.get("model")

    # Ghi incident vào MongoDB → Change Stream tự kích hoạt recovery
    await db.incidents.insert_one({
        "provider": provider,
        "model": model,
        "status": "detected",
        "detected_at": datetime.utcnow(),
        "source": "datadog_monitor"
    })
```

---

## 6. Dashboard — Một màn hình, toàn bộ context

**Thiết kế theo 3 zone tương ứng 3 bước vận hành:**

### Zone 1 — DETECT (top row)
| Widget | Metric | Mô tả |
| :--- | :--- | :--- |
| SLO Widget | `llm.slo.burn_rate` | Burn rate hiện tại vs threshold |
| Timeseries | `llm.request.error_rate` | Error rate 24h theo provider |
| Query Value | `llm.circuit_breaker.state` | Circuit breaker state per model |
| Monitor Summary | All LLM monitors | Trạng thái alert tổng hợp |

### Zone 2 — INVESTIGATE (middle row)
| Widget | Source | Mô tả |
| :--- | :--- | :--- |
| Timeseries | `llm.request.latency` p50/p95/p99 | Latency percentile trend |
| Heatmap | `llm.request.latency` by model | So sánh latency distribution |
| Log Stream | `service:llm-gateway @status:error` | Live error logs |
| Trace List | APM — top slow spans | Slow/error traces live |

### Zone 3 — RESPOND (bottom row)
| Widget | Source | Mô tả |
| :--- | :--- | :--- |
| Timeseries | `llm.failover.count` | Failover events timeline |
| Timeseries | `llm.request.latency` after failover | Recovery confirmation |
| Query Value | `llm.slo.burn_rate` current | Burn rate đang giảm? |
| Timeseries | `llm.cost.usd` | Cost impact của failover |

---

## 7. Anomaly Detection (Extended)

Dùng cho: phát hiện degradation **trước khi** breach SLO threshold — slow burn khó thấy bằng static threshold.

```yaml
name: "[LLM] Latency Anomaly — {{model}}"
type: anomaly alert
query: >
  avg(last_4h):
    anomalies(
      avg:llm.request.latency.95percentile{*} by {model},
      "agile",    # algorithm: agile handles seasonality
      3,          # deviations: 3 sigma
      direction="above",
      interval=60,
      alert_window="last_15m",
      seasonality="hourly"
    )
  >= 1
```

**Tại sao `agile` algorithm?** LLM API có hourly seasonality (peak giờ làm việc US/EU). `agile` học pattern theo thời gian, ít false positive hơn `basic`.

---

## 8. Correlation Strategy — "The Glue"

Điểm mạnh nhất của hệ thống: **một click từ metric → log → trace**.

```
Datadog Dashboard
  → Latency spike lúc 10:15
  → Click timeseries point
  → Filter logs: timestamp:10:10–10:20 @provider:openai
  → Thấy log: ConnectionTimeout tại 10:15:02
  → Click "View Trace" từ log
  → APM: span http.request mất 30s, timeout ở provider layer
  → Xác nhận: provider-side issue, không phải gateway bug
  → Trigger failover
```

**Kỹ thuật đảm bảo correlation:**
1. **Unified tagging**: `provider`, `model`, `incident_id` có mặt ở METRIC + LOG + TRACE
2. **Trace injection vào log**: `dd.trace_id` trong mọi log line
3. **Incident ID propagation**: khi Gateway mở incident, inject `incident_id` vào mọi log/span sau đó
4. **Time sync**: tất cả component dùng UTC, NTP-synced

---

## 9. Những gì KHÔNG làm

| Antipattern | Vấn đề | Thay bằng |
| :--- | :--- | :--- |
| Alert trên error count tuyệt đối | False positive khi traffic tăng | Alert trên error rate % hoặc burn rate |
| Static threshold cho latency | Không account seasonality | Anomaly Detection + burn rate |
| Dùng APM metric cho SLO calculation | APM sampling có thể bỏ sót | Custom metric từ gateway (100% data) |
| Alert mỗi error đơn lẻ | Alert fatigue → ignore tất cả | Burn rate threshold, min eval window 5m |
| Log full request/response body | PII risk, storage cost | Log chỉ metadata (latency, status, error_type) |
| Dùng RUM | Trọng tâm là Backend API + Gateway | APM đủ, RUM là overhead không cần |
