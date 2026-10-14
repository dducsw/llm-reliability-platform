# SRE Design — LLM Reliability Platform

> Tư duy thiết kế: SRE không phải "keep the lights on". SRE là **hệ thống ra quyết định tự động** dựa trên tín hiệu đo lường được — với fallback cho con người khi hệ thống không chắc chắn.

---

## 1. SLI → SLO → Error Budget

### 1.1. SLI (Service Level Indicators) — Những gì đo được

| SLI | Định nghĩa | Nguồn đo |
| :--- | :--- | :--- |
| **Availability** | % request trả `status=healthy` | `llm_probes` MongoDB |
| **Latency P95** | 95th percentile `latency_ms` của healthy requests | `llm_probes` MongoDB |
| **TTFT P95** | 95th percentile `ttft_ms` | `llm_probes` MongoDB |
| **Throughput** | Median `tokens_per_sec` | `llm_probes` MongoDB |

> Chỉ đo SLI trên **healthy requests** khi tính latency percentile. Error request có latency = 0 hoặc timeout sẽ skew P95 về phía sai.

### 1.2. SLO (Service Level Objectives) — Cam kết

| Provider/Model | Availability | P95 Latency | TTFT P95 | Window |
| :--- | :---: | :---: | :---: | :---: |
| openai/gpt-4o | 99.9% | ≤ 3000ms | ≤ 500ms | Rolling 30d |
| anthropic/claude-3-5-sonnet | 99.9% | ≤ 3500ms | ≤ 600ms | Rolling 30d |
| google/gemini-2.0-flash | 99.5% | ≤ 2000ms | ≤ 400ms | Rolling 30d |

### 1.3. Error Budget — Số phút "được phép lỗi"

```
Error Budget = (1 - SLO target) × window_duration

openai/gpt-4o (99.9%, 30d):
  Error Budget = 0.001 × 30 × 24 × 60 = 43.2 phút/tháng

anthropic/claude-3-5-sonnet (99.9%, 30d):
  Error Budget = 43.2 phút/tháng

google/gemini-2.0-flash (99.5%, 30d):
  Error Budget = 0.005 × 43200 = 216 phút/tháng
```

### 1.4. Error Budget Policy

| Budget Remaining | Hành động |
| :--- | :--- |
| > 50% | Bình thường. Deploy thoải mái. |
| 25% – 50% | Tăng monitoring frequency. Freeze non-critical deploys. |
| 10% – 25% | Alert SRE team. Review recent changes. Cân nhắc freeze toàn bộ. |
| < 10% | **Emergency mode.** Circuit breaker ngưỡng thấp hơn. Failover preemptive. |
| 0% | SLO breach. Incident report bắt buộc. Post-mortem. |

---

## 2. Incident Lifecycle — 3 bước bắt buộc

```
┌─────────────────────────────────────────────────────────────────┐
│  DETECT                INVESTIGATE              RESPOND          │
│                                                                  │
│  Monitor fires    →   Correlate signals    →   Act & Verify     │
│  (< 60s MTTD)         (< 5m MTTI)             (< 15m MTTR)     │
└─────────────────────────────────────────────────────────────────┘
```

### Mục tiêu thời gian

| KPI | Target | Đo bằng |
| :--- | :--- | :--- |
| **MTTD** (Mean Time To Detect) | < 1 phút | `detected_at - first_error_at` |
| **MTTI** (Mean Time To Investigate) | < 5 phút | `action_at - detected_at` |
| **MTTR** (Mean Time To Recover) | < 15 phút | `resolved_at - detected_at` |

---

## 3. Burn Rate — Logic Cảnh Báo

Dùng **multi-window burn rate** thay static threshold. Nguồn gốc: Google SRE Book, Chapter 5.

### 3.1. Công thức

```
burn_rate = observed_error_rate / slo_error_budget_rate

Ví dụ: SLO 99.9% → slo_error_budget_rate = 0.001
Nếu observed_error_rate = 5% → burn_rate = 50x
→ Error budget cạn trong 30d / 50 = 14.4 giờ
```

### 3.2. Alert Tiers (4 mức)

| Tier | Window Ngắn | Window Dài | Burn Rate | Severity | Action |
| :--- | :---: | :---: | :---: | :--- | :--- |
| **P1 — Critical** | 1h × 14x | 5m × 14x | Cả 2 | Page on-call | Auto-failover |
| **P2 — High** | 6h × 6x | 30m × 6x | Cả 2 | Slack urgent | Circuit breaker |
| **P3 — Warning** | 3d × 3x | – | 1 cửa sổ | Slack notify | Monitor closely |
| **P4 — Info** | Budget < 10% | – | – | Dashboard | Freeze deploys |

**Logic AND giữa 2 window** → tránh false positive từ spike ngắn (P1/P2).

---

## 4. Recovery Automation — Decision Tree

```
Alert fired (burn_rate > threshold)
    │
    ├─► Classify incident type
    │       │
    │       ├─ error_rate > 80% trong 10 phút
    │       │   └─► PROVIDER DOWN → Failover ngay
    │       │
    │       ├─ latency_p95 > 3x SLO threshold
    │       │   └─► LATENCY SPIKE → Circuit Breaker OPEN
    │       │
    │       ├─ tokens_per_sec giảm > 40% so với 24h baseline
    │       │   └─► DEGRADATION → Rate limit + Alert (không auto-failover)
    │       │
    │       └─ error_rate 20–80%
    │           └─► PARTIAL FAILURE → Circuit Breaker + Monitor
    │
    ├─► Execute recovery action
    │       │
    │       ├─ Failover: chuyển traffic sang fallback_providers[0]
    │       ├─ Circuit Breaker OPEN: stop sending, drain in-flight requests
    │       └─ Rate limit: giảm concurrency 50%
    │
    └─► Verify recovery (60s sau action)
            │
            ├─ error_rate < 5% AND latency < SLO → RESOLVED ✅
            ├─ error_rate 5–20% → Partial recovery, tiếp tục monitor
            └─ error_rate > 20% → Escalate, thử fallback tiếp theo
```

---

## 5. Circuit Breaker Pattern

3 trạng thái, logic chuyển tiếp rõ ràng.

```
          failure_threshold           success_threshold
CLOSED ──────────────────→ OPEN ──────────────────────→ HALF-OPEN
  ↑                          │   probe_interval=30s         │
  └──────────────────────────┘ ←───────────────────────────┘
         still failing                  healthy

```

### 5.1. Cấu hình per provider

```python
CIRCUIT_CONFIG = {
    "openai/gpt-4o": CircuitConfig(
        failure_threshold=5,      # 5 lỗi liên tiếp → OPEN
        success_threshold=2,      # 2 success liên tiếp → CLOSED
        probe_interval_s=30,      # OPEN → thử 1 probe mỗi 30s
        timeout_s=30,             # Request timeout
        half_open_max_calls=1     # Chỉ 1 request thử trong HALF-OPEN
    )
}
```

### 5.2. State transitions ghi vào MongoDB

```python
async def open_circuit(provider: str, model: str, incident_id: str):
    # Ghi metric cho Datadog
    statsd.gauge("llm.circuit_breaker.state", 1,
                 tags=[f"provider:{provider}", f"model:{model}"])

    # Change Stream trên incidents tự kích hoạt failover
    await db.incidents.update_one(
        {"_id": incident_id},
        {
            "$set": {"status": "recovering"},
            "$push": {
                "timeline": {
                    "at": datetime.utcnow(),
                    "event": "circuit_opened",
                    "actor": "gateway"
                }
            }
        }
    )
```

---

## 6. Retry Strategy — Không retry mù quáng

**Nguyên tắc:**
- Retry chỉ cho **transient errors** (5xx, timeout)
- Không retry **client errors** (4xx, auth fail, context length)
- Retry có **exponential backoff + jitter** — tránh thundering herd
- Giới hạn tổng thời gian retry = 50% SLO latency threshold

```python
import asyncio, random

RETRYABLE_ERRORS = {500, 502, 503, 504, 429}  # 429 = rate limited

async def call_with_retry(provider, model, payload, max_retries=3):
    attempt = 0
    base_delay = 0.5  # 500ms

    while attempt <= max_retries:
        try:
            return await call_provider(provider, model, payload)

        except ProviderHTTPError as e:
            if e.status_code not in RETRYABLE_ERRORS:
                raise  # không retry 4xx

            if attempt == max_retries:
                raise  # hết lượt

            # Exponential backoff + jitter: tránh thundering herd
            delay = base_delay * (2 ** attempt) + random.uniform(0, 0.5)
            delay = min(delay, 10)  # cap 10s

            await record_retry(provider, model, attempt + 1, e.status_code)
            await asyncio.sleep(delay)
            attempt += 1
```

**Retry budget:** Nếu error rate > 50%, không retry — retry chỉ tăng tải provider đang sập. Failover ngay.

---

## 7. Failover Strategy

### 7.1. Priority list

```python
FAILOVER_CHAIN = {
    "openai/gpt-4o": [
        "anthropic/claude-3-5-sonnet",  # primary fallback: comparable quality
        "google/gemini-2.0-flash",       # secondary: faster, slightly different
    ],
    "anthropic/claude-3-5-sonnet": [
        "openai/gpt-4o",
        "google/gemini-2.0-flash",
    ]
}
```

### 7.2. Failover execution

```python
async def execute_failover(incident: Incident) -> str:
    chain = FAILOVER_CHAIN.get(incident.model, [])

    for fallback in chain:
        # Kiểm tra circuit breaker của fallback — không failover sang provider đang sập
        if circuit_breaker.state(fallback) == "OPEN":
            continue

        # Test probe trước khi chuyển toàn bộ traffic
        probe_ok = await health_probe(fallback, timeout_s=5)
        if not probe_ok:
            continue

        # Ghi decision
        await db.recovery_actions.insert_one({
            "incident_id": incident.id,
            "action": "failover",
            "from_provider": incident.model,
            "to_provider": fallback,
            "triggered_at": datetime.utcnow(),
            "triggered_by": "auto"
        })

        # Switch traffic
        await traffic_router.set_primary(fallback)
        return fallback

    # Tất cả fallback đều fail — escalate to human
    await escalate_to_oncall(incident, reason="all_fallbacks_failed")
    raise NoFallbackAvailableError()
```

### 7.3. Fail-back (khôi phục provider gốc)

```
Provider gốc OPEN → probe mỗi 30s (HALF-OPEN)
  → 2 probe thành công liên tiếp
  → Circuit → CLOSED
  → Route 10% traffic về gốc (canary)
  → Nếu error rate < 1% trong 5 phút → Route 100% traffic về gốc
  → Ghi "resolved" vào incident
```

Không fail-back ngay lập tức — tránh oscillation (đi về, đi về liên tục).

---

## 8. Runbook — Từng Kịch Bản

### 8.1. PROVIDER DOWN (error rate > 80%)

```
1. [Auto]  Detect: burn_rate Monitor fires (< 1m)
2. [Auto]  Circuit Breaker OPEN
3. [Auto]  Failover sang fallback[0], probe test trước
4. [Auto]  Ghi recovery_action vào MongoDB
5. [Auto]  Datadog dashboard: verify latency trở về baseline
6. [Human] Review sau 15 phút: nếu provider gốc vẫn down → notify stakeholders
7. [Auto]  Probe provider gốc mỗi 30s
8. [Auto]  Khi 2 probe thành công → canary 10% → fail-back
9. [Human] Post-mortem nếu incident > 30 phút
```

### 8.2. LATENCY SPIKE (P95 > 3x threshold)

```
1. [Auto]  Detect: P95 Monitor fires
2. [Auto]  Circuit Breaker OPEN (stop sending mới, drain in-flight)
3. [Auto]  Check: degradation ở provider hay gateway?
           - APM span: nếu http.request span dài → provider-side
           - Nếu internal span dài → gateway bug → alert developer
4. [Auto]  Nếu provider-side: Failover
5. [Auto]  Nếu gateway-side: Rollback last deploy (manual trigger)
6. [Human] Investigate root cause trong Datadog APM
```

### 8.3. GRADUAL DEGRADATION (tokens_per_sec giảm dần)

```
1. [Auto]  Detect: Anomaly Detection fires (không phải static threshold)
2. [Auto]  Ghi incident, severity=warning
3. [Auto]  Tăng monitoring frequency (probe 30s thay 60s)
4. [Human] SRE xem xét: có pattern theo giờ không? (US peak hours?)
5. [Human] Quyết định: chờ tự hồi phục hay preemptive failover
6. [Auto]  Nếu sau 30 phút vẫn giảm → auto-failover
```

### 8.4. PARTIAL RECOVERY (error rate 10–20%)

```
1. [Auto]  Detect: burn_rate vẫn > 3x sau failover
2. [Auto]  Check fallback health — nếu fallback cũng degraded → next fallback
3. [Auto]  Rate limit: giảm concurrency 50% để giảm error count tuyệt đối
4. [Human] Notify: "hệ thống đang recover nhưng chưa hoàn toàn"
5. [Auto]  Monitor mỗi 60s, resolve khi error_rate < 1% trong 5 phút liên tiếp
```

---

## 9. Incident Document Template

```
INCIDENT-{date}-{provider}-{type}

Severity:     P1 / P2 / P3
Status:       Detected / Investigating / Recovering / Resolved
Detected at:  2026-10-20T10:15:00Z
Resolved at:  2026-10-20T10:28:00Z (13 phút)

SLO Impact:
  Error budget consumed: 13 / 43.2 phút (30.1%)
  Burn rate peak:        47x (1h window)

Root Cause:
  Provider: openai đột ngột tăng timeout rate lên 87.5%
  Affected: openai/gpt-4o

Timeline:
  10:14:00  First error detected in llm_probes
  10:15:00  Monitor fires (burn_rate 1h = 14x)
  10:15:05  Circuit breaker OPEN
  10:15:08  Failover → anthropic/claude-3-5-sonnet (probe OK)
  10:15:10  100% traffic → anthropic
  10:16:00  Error rate = 0%, latency P95 = 1850ms ✅
  10:45:00  openai probe thành công (2 lần)
  10:50:00  Canary 10% → openai
  10:55:00  Error rate < 1% → fail-back hoàn tất
  10:55:00  Incident RESOLVED

Action items:
  [ ] Tìm hiểu nguyên nhân từ phía OpenAI status page
  [ ] Xem xét giảm timeout threshold từ 30s → 20s
  [ ] Review error budget: còn 70% → không cần freeze deploy
```

---

## 10. Những gì KHÔNG làm

| Antipattern | Vấn đề | Thay bằng |
| :--- | :--- | :--- |
| Alert trên error count tuyệt đối | False positive khi traffic thấp/cao | Burn rate (rate-based) |
| Failover không probe trước | Failover sang provider đang sập | `health_probe()` trước khi switch |
| Retry không có cap | Thundering herd, tăng tải provider | Exponential backoff + jitter + max_retries |
| Fail-back ngay lập tức | Oscillation loop | Canary 10% + 5 phút observation |
| Auto-action mọi thứ | Hệ thống tự tạo incident bằng action | Escalate khi không chắc, human quyết định |
| MTTR đo từ thời điểm alert | Alert chậm che giấu vấn đề thực | MTTD đo từ first error, MTTR từ first error |
