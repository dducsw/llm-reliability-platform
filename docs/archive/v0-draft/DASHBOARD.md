# Dashboard Design — LLM Reliability Platform

> Tư duy thiết kế: Dashboard MVP là **công cụ kể chuyện** cho giám khảo — mỗi màn hình minh họa đúng 1 bước trong vòng lặp Detect → Investigate → Respond. Không làm dashboard "đẹp nhưng rỗng".

---

## 1. Kiến trúc tổng thể

```
Browser (React/Vite)
    │
    ├── REST API  ──────────────────── FastAPI (Python)
    │       │                               │
    │       │                ┌──────────────┴──────────────┐
    │       │            MongoDB                       Datadog API
    │       │         (aggregation)                  (metrics, monitors)
    │       │
    └── WebSocket ──────────────────── FastAPI WebSocket
                                            │
                                    MongoDB Change Stream
                                    (push incident events)
```

**Nguyên tắc phân luồng:**
- **REST**: Data lịch sử, SLO report, incident list — từ MongoDB Aggregation
- **WebSocket**: Real-time alerts, incident state change — từ Change Stream
- **Datadog API**: Embed iframe dashboard Datadog hoặc pull monitor status

---

## 2. Tech Stack

| Layer | Công nghệ | Lý do chọn |
| :--- | :--- | :--- |
| **Backend** | Go + Gin | Goroutine-native concurrency, production SRE idiom |
| **Frontend** | React + Vite | SPA, fast dev, WebSocket dễ |
| **Realtime** | WebSocket (gorilla/websocket) | Goroutine per connection, zero overhead |
| **Charts** | Recharts | Nhẹ, dễ custom với React |
| **Styling** | Tailwind CSS | Rapid UI, dark mode sẵn |
| **State** | Zustand | Tối giản hơn Redux cho scope này |

**Go packages chính:**
```
go.mongodb.org/mongo-driver/mongo       — MongoDB driver
github.com/gin-gonic/gin                — HTTP framework
github.com/gorilla/websocket            — WebSocket
github.com/DataDog/datadog-go/v5/statsd — DogStatsD metrics
gopkg.in/DataDog/dd-trace-go.v1/...    — APM tracing
```

---

## 3. Các màn hình (Routes)

| Route | Tên | Mục đích | Bước vận hành |
| :--- | :--- | :--- | :--- |
| `/` | **Overview** | Tổng quan sức khỏe hệ thống | DETECT |
| `/incidents` | **Incidents** | Danh sách + timeline sự cố | INVESTIGATE |
| `/incidents/:id` | **Incident Detail** | Drill-down 1 sự cố | INVESTIGATE |
| `/slo` | **SLO Report** | Error budget per model | DETECT + RESPOND |
| `/demo` | **Demo Control** | Trigger scenario cho hackathon | — |

---

## 4. Màn hình chi tiết

### 4.1. Overview (`/`) — DETECT

**Mục tiêu:** Một cái nhìn → biết ngay hệ thống có vấn đề không.

```
┌──────────────────────────────────────────────────────────────┐
│  🟢 System Healthy   |  Active Incidents: 0  |  ⏱ 14:52 UTC │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  PROVIDER HEALTH                                             │
│  ┌──────────────────┐ ┌──────────────────┐ ┌─────────────┐  │
│  │ OpenAI GPT-4o    │ │ Anthropic Claude │ │ Gemini Flash│  │
│  │ 🟢 HEALTHY       │ │ 🟢 HEALTHY       │ │ 🟡 DEGRADED │  │
│  │ P95: 1.2s        │ │ P95: 1.8s        │ │ P95: 4.1s   │  │
│  │ Error: 0.1%      │ │ Error: 0.2%      │ │ Error: 8.3% │  │
│  │ Budget: 87%      │ │ Budget: 91%      │ │ Budget: 34% │  │
│  └──────────────────┘ └──────────────────┘ └─────────────┘  │
│                                                              │
│  LATENCY TREND (1h)                    ERROR RATE (1h)       │
│  ┌───────────────────────┐  ┌──────────────────────────┐    │
│  │  [Recharts LineChart] │  │  [Recharts AreaChart]    │    │
│  │   P50 / P95 / P99     │  │   per provider stacked   │    │
│  └───────────────────────┘  └──────────────────────────┘    │
│                                                              │
│  RECENT INCIDENTS                        BURN RATE NOW       │
│  ┌───────────────────────────────┐  ┌──────────────────┐    │
│  │ [Table: last 5 incidents]     │  │ 1h:  1.2x  🟢    │    │
│  │ type | provider | duration    │  │ 6h:  0.8x  🟢    │    │
│  └───────────────────────────────┘  │ 3d:  0.3x  🟢    │    │
│                                     └──────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

**API endpoints phục vụ màn hình này:**

```python
# GET /api/overview
{
  "system_status": "healthy",          # "healthy" | "degraded" | "critical"
  "active_incidents": 0,
  "providers": [
    {
      "id": "openai/gpt-4o",
      "status": "healthy",
      "p95_latency_ms": 1200,
      "error_rate_pct": 0.1,
      "budget_remaining_pct": 87.3,
      "circuit_breaker": "closed"
    }
  ],
  "latency_trend": [...],              # 60 data points, last 1h
  "error_rate_trend": [...],
  "burn_rates": { "1h": 1.2, "6h": 0.8, "3d": 0.3 }
}
```

**MongoDB query (Go):**
```go
// System status = worst provider status
// Provider status = error_rate_pct trong 15 phút gần nhất
fifteenAgo := time.Now().UTC().Add(-15 * time.Minute)

pipeline := mongo.Pipeline{
    {{"$match", bson.D{{"timestamp", bson.D{{"$gte", fifteenAgo}}}}}},
    {{"$group", bson.D{
        {"_id", "$meta.model"},
        {"total", bson.D{{"$sum", 1}}},
        {"errors", bson.D{{"$sum", bson.D{{"$cond", bson.A{
            bson.D{{"$ne", bson.A{"$status", "healthy"}}}, 1, 0,
        }}}}}},
        {"p95", bson.D{{"$percentile", bson.D{
            {"input", "$latency_ms"},
            {"p", bson.A{0.95}},
            {"method", "approximate"},
        }}}},
    }}},
    {{"$project", bson.D{
        {"error_rate_pct", bson.D{{"$multiply", bson.A{
            bson.D{{"$divide", bson.A{"$errors", "$total"}}}, 100,
        }}}},
        {"p95_latency_ms", bson.D{{"$arrayElemAt", bson.A{"$p95", 0}}}},
    }}},
}

cursor, err := coll.Aggregate(ctx, pipeline)
```

---

### 4.2. Incidents (`/incidents`) — INVESTIGATE

**Mục tiêu:** Timeline tất cả sự cố, filter được, thấy được MTTR.

```
┌──────────────────────────────────────────────────────────────┐
│  Incidents                    Filter: [All ▾] [All ▾] [🔍]  │
├──────────────────────────────────────────────────────────────┤
│  Status    Provider/Model       Type           Duration  MTTR │
│  ─────────────────────────────────────────────────────────── │
│  🔴 ACTIVE  openai/gpt-4o       provider_down  8m ago    —   │
│  ✅ RESOLVED anthropic/claude   latency_spike  2h ago  12m   │
│  ✅ RESOLVED openai/gpt-4o      degradation    1d ago   4m   │
│  ✅ RESOLVED google/gemini      provider_down  3d ago  18m   │
│  ─────────────────────────────────────────────────────────── │
│                                            MTTR avg:  11.3m  │
└──────────────────────────────────────────────────────────────┘
```

**WebSocket push khi có incident mới:**
```javascript
// React hook
useEffect(() => {
  const ws = new WebSocket("ws://localhost:8000/ws/incidents")
  ws.onmessage = (event) => {
    const incident = JSON.parse(event.data)
    // Prepend vào list, toast notification
    setIncidents(prev => [incident, ...prev])
    toast.error(`🚨 ${incident.type} — ${incident.model}`)
  }
  return () => ws.close()
}, [])
```

---

### 4.3. Incident Detail (`/incidents/:id`) — INVESTIGATE

**Đây là màn hình quan trọng nhất** — minh họa Investigate step cho giám khảo.

```
┌──────────────────────────────────────────────────────────────┐
│  ← Back   INCIDENT-2026-10-20-openai-provider_down           │
│           🔴 P1 CRITICAL | openai/gpt-4o | RESOLVED ✅        │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  IMPACT SUMMARY                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Duration: 13 phút  |  MTTR: 13m  |  Budget used: 30%│   │
│  │  Peak error rate: 87.5%  |  Peak burn rate: 47x      │   │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ERROR RATE DURING INCIDENT              TIMELINE            │
│  ┌──────────────────────┐  ┌────────────────────────────┐   │
│  │ [AreaChart]          │  │ 10:14 🔍 First error       │   │
│  │ Trước | Trong | Sau  │  │ 10:15 🚨 Monitor fires     │   │
│  │ spike rõ ràng        │  │ 10:15 🔌 Circuit OPEN      │   │
│  │ recovery visible     │  │ 10:15 🔄 Failover → Claude │   │
│  └──────────────────────┘  │ 10:16 ✅ Error rate = 0%   │   │
│                             │ 10:45 🔍 Probe openai OK   │   │
│  ROOT CAUSE                 │ 10:55 ✅ Fail-back hoàn tất│   │
│  ┌──────────────────────┐   └────────────────────────────┘   │
│  │ Window: 10:00–10:15  │                                    │
│  │ Errors: 21/24 probes │   RECOVERY ACTIONS                 │
│  │ Error rate: 87.5%    │   ┌────────────────────────────┐   │
│  │ First error: 10:14   │   │ circuit_open   10:15  auto │   │
│  └──────────────────────┘   │ failover       10:15  auto │   │
│                              │   → anthropic/claude-3-5  │   │
│  SLO SNAPSHOT                │ latency_before: 9800ms    │   │
│  P95 observed: 9800ms        │ latency_after:  1850ms ✅ │   │
│  SLO threshold: 3000ms       └────────────────────────────┘   │
│  Budget before: 42.5%                                        │
│  Budget after:  12.3%        [🔗 View in Datadog APM]        │
└──────────────────────────────────────────────────────────────┘
```

**"View in Datadog APM"** — deep link sang trace trong thời gian incident:
```python
def datadog_trace_link(incident: Incident) -> str:
    start = int(incident.detected_at.timestamp() * 1000) - 300_000   # 5m trước
    end   = int(incident.resolved_at.timestamp() * 1000) + 300_000   # 5m sau
    return (
        f"https://app.datadoghq.com/apm/traces"
        f"?query=service%3Allm-gateway"
        f"&start={start}&end={end}"
    )
```

---

### 4.4. SLO Report (`/slo`) — Error Budget

```
┌──────────────────────────────────────────────────────────────┐
│  SLO Report — Rolling 30 days                                │
├──────────────────────────────────────────────────────────────┤
│  openai/gpt-4o                                               │
│  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░  72% budget remaining │
│  Availability: 99.93%  Target: 99.9%  ✅                     │
│  P95 Latency:  1.8s    Target: 3.0s   ✅                     │
│  Budget used:  12.3m / 43.2m                                 │
│                                                              │
│  anthropic/claude-3-5-sonnet                                 │
│  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░  91% budget remaining │
│  Availability: 99.97%  Target: 99.9%  ✅                     │
│                                                              │
│  google/gemini-2.0-flash                              ⚠️     │
│  ▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░░░░░░  34% budget remaining │
│  Availability: 99.68%  Target: 99.5%  ✅  (nhưng burn cao)  │
│                                                              │
│  INCIDENT IMPACT (30d)                                       │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ [BarChart] Budget consumed per incident per model     │  │
│  └───────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

**MongoDB query cho SLO:**
```python
# Availability trong 30d
pipeline = [
    {"$match": {"timestamp": {"$gte": thirty_days_ago}}},
    {"$group": {
        "_id": "$meta.model",
        "total": {"$sum": 1},
        "healthy": {"$sum": {"$cond": [{"$eq": ["$status", "healthy"]}, 1, 0]}}
    }},
    {"$project": {
        "availability_pct": {"$multiply": [{"$divide": ["$healthy", "$total"]}, 100]},
        "downtime_min": {
            "$multiply": [
                {"$divide": [{"$subtract": ["$total", "$healthy"]}, "$total"]},
                43200  # 30d in minutes
            ]
        }
    }}
]
```

---

### 4.5. Demo Control (`/demo`) — Hackathon Scenario Trigger

**Chỉ dùng để demo** — trigger simulator scenarios real-time trước giám khảo.

```
┌──────────────────────────────────────────────────────────────┐
│  🎬 Demo Control Panel                                       │
│  (Hackathon use only)                                        │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Target Provider: [openai/gpt-4o ▾]                         │
│                                                              │
│  ┌─────────────────────┐  ┌─────────────────────┐           │
│  │  🔴 Provider Down   │  │  🔶 Latency Spike   │           │
│  │  error rate → 100%  │  │  latency × 5x       │           │
│  │  Duration: [15m ▾]  │  │  Duration: [10m ▾]  │           │
│  │  [▶ Trigger]        │  │  [▶ Trigger]        │           │
│  └─────────────────────┘  └─────────────────────┘           │
│                                                              │
│  ┌─────────────────────┐  ┌─────────────────────┐           │
│  │  📉 Degradation     │  │  🔄 Test Failover   │           │
│  │  tps giảm 40%/5min  │  │  Force switch now   │           │
│  │  Duration: [30m ▾]  │  │  To: [anthropic ▾]  │           │
│  │  [▶ Trigger]        │  │  [▶ Trigger]        │           │
│  └─────────────────────┘  └─────────────────────┘           │
│                                                              │
│  ┌────────────────────────────────────────────┐             │
│  │  🟢 [Reset All — Return to Healthy State]  │             │
│  └────────────────────────────────────────────┘             │
│                                                              │
│  LIVE LOG                                                    │
│  ┌────────────────────────────────────────────┐             │
│  │ 14:52:01 Scenario started: provider_down   │             │
│  │ 14:52:05 Injecting errors into openai...   │             │
│  │ 14:52:10 Monitor fires: burn_rate = 51x    │             │
│  │ 14:52:11 Circuit breaker OPEN              │             │
│  │ 14:52:13 Failover → anthropic/claude ✅    │             │
│  └────────────────────────────────────────────┘             │
└──────────────────────────────────────────────────────────────┘
```

**Backend endpoint (Go):**
```go
// POST /api/demo/trigger
func (h *Handler) TriggerScenario(c *gin.Context) {
    var req ScenarioRequest
    if err := c.ShouldBindJSON(&req); err != nil {
        c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
        return
    }
    // Goroutine = non-blocking background task, không cần BackgroundTasks
    go h.simulator.Run(req.Scenario, req.Provider, req.DurationMin)
    c.JSON(http.StatusOK, gin.H{"status": "started", "scenario": req.Scenario})
}

// GET /ws/demo-log
func (h *Handler) DemoLogWS(c *gin.Context) {
    conn, err := upgrader.Upgrade(c.Writer, c.Request, nil)
    if err != nil {
        return
    }
    defer conn.Close()
    for line := range h.simulator.LogChan() {  // channel từ simulator goroutine
        if err := conn.WriteMessage(websocket.TextMessage, []byte(line)); err != nil {
            return
        }
    }
}
```

---

## 5. WebSocket — Real-time Incident Feed

```go
// GET /ws/incidents — goroutine per connection, watch Change Stream
func (h *Handler) IncidentFeedWS(c *gin.Context) {
    conn, err := upgrader.Upgrade(c.Writer, c.Request, nil)
    if err != nil {
        return
    }
    defer conn.Close()

    pipeline := mongo.Pipeline{
        {{"$match", bson.D{{"operationType", "insert"}}}},
    }
    opts := options.ChangeStream().SetFullDocument(options.UpdateLookup)
    cs, err := h.db.Collection("incidents").Watch(c.Request.Context(), pipeline, opts)
    if err != nil {
        return
    }
    defer cs.Close(c.Request.Context())

    for cs.Next(c.Request.Context()) {
        var event struct {
            FullDocument Incident `bson:"fullDocument"`
        }
        if err := cs.Decode(&event); err != nil {
            continue
        }
        payload, _ := json.Marshal(map[string]any{
            "id":          event.FullDocument.ID.Hex(),
            "provider":    event.FullDocument.Provider,
            "model":       event.FullDocument.Model,
            "type":        event.FullDocument.Type,
            "severity":    event.FullDocument.Severity,
            "detected_at": event.FullDocument.DetectedAt,
        })
        if err := conn.WriteMessage(websocket.TextMessage, payload); err != nil {
            return  // client disconnected
        }
    }
}
```

**Mỗi WebSocket client = 1 goroutine** — Go scheduler xử lý N ngàn connections không tốn thread pool như Python async.

---

## 6. API Endpoints Summary

| Method | Path | MongoDB query | Màn hình |
| :--- | :--- | :--- | :--- |
| GET | `/api/overview` | Agg: error_rate + P95 per model (15m) | Overview |
| GET | `/api/providers` | Agg: health status per model | Overview |
| GET | `/api/incidents` | Find: incidents, sorted, paginated | Incidents |
| GET | `/api/incidents/:id` | FindOne + join recovery_actions | Incident Detail |
| GET | `/api/slo/:model` | Agg: 30d availability + budget | SLO Report |
| GET | `/api/metrics/latency` | Agg: $setWindowFields trend 24h | Charts |
| POST | `/api/demo/trigger` | — (simulator) | Demo |
| WS | `/ws/incidents` | Change Stream | All pages |
| WS | `/ws/demo-log` | — | Demo |

---

## 7. Build Order (MVP Priority)

```
Tuần 1 (17–23/10):
  [ ] Backend: Go module init + Gin skeleton + MongoDB connection
  [ ] Backend: /api/overview endpoint + aggregation pipeline
  [ ] Frontend: Overview page, provider health cards
  [ ] Backend: WebSocket handler + Change Stream goroutine
  [ ] Frontend: Real-time incident toast

Tuần 2 (24–31/10):
  [ ] Backend: /api/incidents + /api/incidents/:id
  [ ] Frontend: Incidents list + timeline component
  [ ] Frontend: Incident detail với charts + recovery actions
  [ ] Backend: /api/demo/trigger + simulator goroutine
  [ ] Frontend: Demo control panel + live log stream
  [ ] Frontend: SLO report page
  [ ] Polish: dark mode, responsive, loading states
  [ ] Datadog: ddtrace Gin middleware, statsd gauges
```

---

## 8. Những gì KHÔNG làm trong MVP

| Feature | Lý do bỏ | Nếu cần thêm |
| :--- | :--- | :--- |
| Authentication | Demo hackathon, không cần | Thêm JWT sau |
| User management | Out of scope | — |
| Alert config UI | Đã hardcode trong slo_configs | Thêm CRUD form |
| Historical export | MongoDB có thể export trực tiếp | — |
| Mobile responsive | Giám khảo xem trên laptop | CSS media query cơ bản |
| Datadog embed iframe | Gửi link deep link là đủ | Datadog iframe API |
