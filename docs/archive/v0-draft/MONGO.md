# MongoDB Design — LLM Reliability Platform

> Tư duy thiết kế: **access pattern trước, schema sau**. Mỗi collection tồn tại vì một query không thể làm khác đi — không phải vì "có thể cần sau".

---

## 1. Tổng quan Collections

| Collection | Loại | Vai trò |
| :--- | :--- | :--- |
| `llm_probes` | Time Series | Raw telemetry — latency, error, throughput từng probe |
| `incidents` | Standard | Vòng đời sự cố: Detect → Investigate → Recover |
| `slo_configs` | Standard | Định nghĩa SLO theo provider/model |
| `recovery_actions` | Standard | Audit trail hành động tự động (retry, circuit break, failover) |

---

## 2. Schema chi tiết

### 2.1. `llm_probes` — Time Series Collection

**Tại sao Time Series?**
MongoDB Time Series dùng columnar storage nội bộ: ghi nhanh hơn ~4x, đọc range nhanh hơn ~10x so với collection thường cho time-ordered data. Không cần manual partitioning.

```js
db.createCollection("llm_probes", {
  timeseries: {
    timeField: "timestamp",   // bắt buộc ISO Date
    metaField: "meta",        // index tự động trên meta.*
    granularity: "minutes"    // probes chạy mỗi phút trong demo
  },
  expireAfterSeconds: 2592000  // TTL 30 ngày — tự purge, không cần cron
})

// Document shape
{
  timestamp: ISODate("2026-10-20T10:15:00Z"),  // timeField
  meta: {                                        // metaField — dùng cho filter
    provider: "openai",
    model: "openai/gpt-4o",
    synthetic: false
  },
  status: "error",          // "healthy" | "error" | "timeout"
  ttft_ms: null,
  latency_ms: null,
  tokens_per_sec: null,
  token_count: 0
}
```

**Index:** Time Series tự tạo compound index trên `(meta, timestamp)`. Không cần thêm gì cho read pattern cơ bản.

---

### 2.2. `incidents` — Lifecycle Document

**Tại sao embed `timeline` array?**
Một incident có nhiều state transitions. Embed tránh join, cho phép Change Stream watch toàn bộ lifecycle trên 1 document. Timeline array bounded (sự cố kết thúc trong giờ) → không có unbounded growth risk.

```js
{
  _id: ObjectId(),
  provider: "openai",
  model: "openai/gpt-4o",
  type: "latency_spike",          // "provider_down" | "latency_spike" | "degradation" | "failover"
  severity: "critical",           // "warning" | "critical"
  status: "investigating",        // "detected" | "investigating" | "recovering" | "resolved"

  detected_at: ISODate("2026-10-20T10:15:00Z"),
  resolved_at: null,              // null khi chưa resolved

  // SLO context tại thời điểm phát hiện
  slo_snapshot: {
    threshold_p95_ms: 3000,
    observed_p95_ms: 9800,
    error_budget_remaining_pct: 12.3
  },

  // Root cause từ aggregation pipeline
  root_cause: {
    window_start: ISODate("2026-10-20T09:45:00Z"),
    window_end:   ISODate("2026-10-20T10:15:00Z"),
    error_rate_pct: 87.5,
    affected_probes: 21
  },

  // Embed: không cần collection riêng cho state changes
  timeline: [
    { at: ISODate("2026-10-20T10:15:00Z"), event: "detected",       actor: "monitor" },
    { at: ISODate("2026-10-20T10:16:00Z"), event: "circuit_opened",  actor: "gateway" },
    { at: ISODate("2026-10-20T10:16:30Z"), event: "failover_start",  actor: "gateway" },
    { at: ISODate("2026-10-20T10:45:00Z"), event: "resolved",        actor: "monitor" }
  ]
}
```

**Index:**
```js
db.incidents.createIndex({ status: 1, detected_at: -1 })             // query open incidents
db.incidents.createIndex({ provider: 1, model: 1, detected_at: -1 }) // per-model history
```

---

### 2.3. `slo_configs` — Policy per Model

```js
{
  _id: "openai/gpt-4o",           // provider/model làm _id — lookup O(1), không cần index riêng
  p95_latency_ms: 3000,
  error_rate_max_pct: 1.0,        // SLO: < 1% error trong 30 ngày
  availability_target_pct: 99.9,
  burn_rate_thresholds: {
    fast_burn: { window_h: 1, multiplier: 14 },  // cảnh báo khẩn
    slow_burn: { window_h: 6, multiplier: 6  }   // cảnh báo sớm
  },
  fallback_providers: ["anthropic/claude-3-5-sonnet", "google/gemini-2.0-flash"]
}
```

---

### 2.4. `recovery_actions` — Audit Trail

**Tại sao không embed vào `incidents`?**
Actions có thể nhiều (retry nhiều lần) → unbounded array. Tách ra để query độc lập: "tất cả failover trong 7 ngày", "MTTR theo action type".

```js
{
  _id: ObjectId(),
  incident_id: ObjectId("..."),
  action: "failover",           // "retry" | "circuit_open" | "failover" | "circuit_close"
  from_provider: "openai/gpt-4o",
  to_provider: "anthropic/claude-3-5-sonnet",
  triggered_at: ISODate("2026-10-20T10:16:30Z"),
  triggered_by: "auto",         // "auto" | "manual"
  outcome: "success",
  latency_before_ms: 9800,
  latency_after_ms: 1850        // chứng minh hồi phục bằng số liệu
}
```

---

## 3. Aggregation Pipeline — Các Query Cốt lõi

### 3.1. Error Rate trong cửa sổ N phút

```js
// Dùng cho: Detect step, Monitor check mỗi phút
db.llm_probes.aggregate([
  { $match: {
    "meta.provider": "openai",
    "meta.model": "openai/gpt-4o",
    timestamp: { $gte: new Date(Date.now() - 15 * 60 * 1000) }
  }},
  { $group: {
    _id: null,
    total:  { $sum: 1 },
    errors: { $sum: { $cond: [{ $ne: ["$status", "healthy"] }, 1, 0] }}
  }},
  { $project: {
    error_rate_pct: { $multiply: [{ $divide: ["$errors", "$total"] }, 100] }
  }}
])
```

### 3.2. P95 / P99 Latency với `$percentile` (MongoDB 7.0+)

```js
// Dùng cho: SLO evaluation, Datadog custom metric
db.llm_probes.aggregate([
  { $match: {
    "meta.model": "openai/gpt-4o",
    status: "healthy",
    timestamp: { $gte: new Date(Date.now() - 60 * 60 * 1000) }
  }},
  { $group: {
    _id: "$meta.provider",
    p50: { $percentile: { input: "$latency_ms", p: [0.50], method: "approximate" }},
    p95: { $percentile: { input: "$latency_ms", p: [0.95], method: "approximate" }},
    p99: { $percentile: { input: "$latency_ms", p: [0.99], method: "approximate" }}
  }}
])
```

### 3.3. Error Budget Burn Rate — Dual Window (Google SRE Pattern)

**Logic:** Alert khi `fast_burn_rate > 14` VÀ `slow_burn_rate > 6` → error budget cạn trong < 1 giờ nếu tiếp diễn. Tránh false positive (spike ngắn) và miss slow burn.

```js
// burn_rate = observed_error_rate / slo_error_budget_rate
// slo_error_budget_rate = 1 - availability_target = 1 - 0.999 = 0.001

function getBurnRate(windowMinutes) {
  return db.llm_probes.aggregate([
    { $match: {
      "meta.model": "openai/gpt-4o",
      timestamp: { $gte: new Date(Date.now() - windowMinutes * 60 * 1000) }
    }},
    { $group: {
      _id: null,
      total:  { $sum: 1 },
      errors: { $sum: { $cond: [{ $ne: ["$status", "healthy"] }, 1, 0] }}
    }},
    { $project: {
      burn_rate: { $divide: [{ $divide: ["$errors", "$total"] }, 0.001] }
    }}
  ])
}

// Chạy song song 2 window
const [fast, slow] = await Promise.all([
  getBurnRate(60),   // 1h — fast burn
  getBurnRate(360)   // 6h — slow burn
])
```

### 3.4. Rolling Trend với `$setWindowFields`

```js
// Dùng cho: dashboard trend line, feed vào Datadog Anomaly Detection
db.llm_probes.aggregate([
  { $match: { "meta.model": "openai/gpt-4o" }},
  { $setWindowFields: {
    partitionBy: "$meta.model",
    sortBy: { timestamp: 1 },
    output: {
      rolling_error_rate: {
        $avg: { $cond: [{ $ne: ["$status", "healthy"] }, 1.0, 0.0] },
        window: { range: [-60, 0], unit: "minute" }
      },
      rolling_p95_latency: {
        $percentile: { input: "$latency_ms", p: [0.95], method: "approximate" },
        window: { range: [-60, 0], unit: "minute" }
      }
    }
  }},
  { $group: {
    _id: { $dateTrunc: { date: "$timestamp", unit: "hour" }},
    error_rate:  { $last: "$rolling_error_rate" },
    p95_latency: { $last: "$rolling_p95_latency" }
  }},
  { $sort: { _id: 1 }}
])
```

### 3.5. MTTR per Provider/Type — KPI Dashboard

```js
db.incidents.aggregate([
  { $match: {
    status: "resolved",
    resolved_at: { $gte: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000) }
  }},
  { $project: {
    duration_min: { $divide: [{ $subtract: ["$resolved_at", "$detected_at"] }, 60000] },
    provider: 1,
    type: 1
  }},
  { $group: {
    _id: { provider: "$provider", type: "$type" },
    mttr_min:  { $avg: "$duration_min" },
    incidents: { $sum: 1 }
  }},
  { $sort: { mttr_min: -1 }}
])
```

---

## 4. Change Streams — Event-driven Recovery

**Pattern:** Gateway watch `incidents`. Khi document mới `status: "detected"` xuất hiện → trigger recovery workflow ngay, không cần polling.

```js
// Gateway process — Node.js
const changeStream = db.collection("incidents").watch(
  [{ $match: { "fullDocument.status": "detected" } }],
  { fullDocument: "updateLookup" }
)

changeStream.on("change", async (event) => {
  const incident = event.fullDocument

  // Load SLO config — cache 5 phút, không query mỗi event
  const config = sloConfigCache.get(incident.model)

  let action
  if (incident.type === "provider_down" || incident.root_cause.error_rate_pct > 50) {
    action = "failover"
    await triggerFailover(incident, config.fallback_providers[0])
  } else {
    action = "circuit_open"
    await openCircuitBreaker(incident.provider, incident.model)
  }

  // Audit trail
  await db.collection("recovery_actions").insertOne({
    incident_id: incident._id,
    action,
    triggered_at: new Date(),
    triggered_by: "auto",
    outcome: "success"
  })
})
```

**Tại sao Change Streams thay vì polling?**
- Polling 1s = N queries/s overhead không cần thiết
- Change Stream = push-based, latency < 100ms sau write
- **Resume token**: tự restart sau disconnect, không mất event

---

## 5. Index Strategy

> Mỗi write-index = overhead ingest. Chỉ index query đang chạy thực sự.

| Collection | Index | Dùng cho |
| :--- | :--- | :--- |
| `llm_probes` | Auto `(meta, timestamp)` | Time Series tự tạo — đủ cho mọi read |
| `incidents` | `{ status: 1, detected_at: -1 }` | Query open incidents |
| `incidents` | `{ provider: 1, model: 1, detected_at: -1 }` | Per-model incident history |
| `recovery_actions` | `{ incident_id: 1 }` | Join từ incident → actions |
| `slo_configs` | `_id` (default) | Lookup bằng model string = O(1) |

---

## 6. Những gì KHÔNG làm (và tại sao)

| Antipattern | Vấn đề | Thay bằng |
| :--- | :--- | :--- |
| Collection riêng mỗi provider | Scatter queries, schema drift | Filter `meta.provider` trong `llm_probes` |
| Embed `recovery_actions` vào `incidents` | Unbounded array nếu retry nhiều | Collection riêng + `incident_id` ref |
| Tính P95 ở application layer | Kéo toàn bộ data về, OOM risk | `$percentile` trong aggregation |
| Cron job purge data cũ | Race condition, complexity | `expireAfterSeconds` TTL |
| Lookup SLO config trong mỗi aggregation | N+1 pattern | App-level cache, refresh 5 phút |
| Pre-aggregate vào summary collection | Premature optimization, stale data | `$setWindowFields` on-demand |
