# Dataset Strategy — LLM Reliability Platform

## 1. Nguồn dữ liệu thực (Public Dataset)

### llm-bench-data
- **Repo:** https://github.com/Jwrede/llm-bench-data
- **License:** CC0 1.0 — dùng tự do, không cần xin phép, phù hợp yêu cầu hackathon
- **Loại:** JSONL, đo hourly từ continuous probing các LLM API endpoint thực
- **Tần suất cập nhật:** Mỗi giờ (3.864+ commits)

#### Schema mỗi record
```jsonl
{
  "provider": "openai",
  "model": "anthropic/claude-sonnet-4.6",
  "status": "healthy",
  "ttft_ms": 312,
  "latency_ms": 2100,
  "tokens_per_sec": 68.4,
  "token_count": 20,
  "timestamp": "2026-05-06T14:00:00Z"
}
```

| Field | Kiểu | Mô tả |
| :--- | :--- | :--- |
| `provider` | string | Provider định tuyến (OpenRouter, openai, anthropic...) |
| `model` | string | Model ID đầy đủ |
| `status` | string | `healthy` / `error` / `timeout` |
| `ttft_ms` | number | Time To First Token (ms) |
| `latency_ms` | number | Tổng latency end-to-end (ms) |
| `tokens_per_sec` | number | Throughput (tokens/s) |
| `token_count` | number | Số token output thực tế |
| `timestamp` | ISO 8601 | Thời điểm probe (UTC) |

#### Cấu trúc file
```
data/
  2026-05/
    2026-05-06.jsonl
    2026-05-07.jsonl
    ...
  2026-06/
    ...
```

#### Ý nghĩa với dự án
- **Status `error` / `timeout`** → nguồn kịch bản sự cố thực tế để seed incident history trong MongoDB
- **`ttft_ms` + `latency_ms` spike** → trigger Datadog Monitor / Alert (SLO burn rate)
- **`tokens_per_sec` sụt** → phát hiện degradation theo provider/model
- Dữ liệu theo giờ → lý tưởng cho **MongoDB Time Series Collections**

---

## 2. Simulator — Synthetic Data Generator

> _Dùng khi cần tái hiện kịch bản sự cố có kiểm soát (cho demo hackathon)._

### Mục tiêu
- Bổ sung các pattern mà public dataset chưa có (cascading failure, gradual degradation)
- Replay lại sự cố nhất quán trong video demo
- Không vi phạm quy định "không dùng dữ liệu nhạy cảm" (toàn bộ là synthetic)

### Các kịch bản simulator cần tạo

| Kịch bản | Mô tả | Signal trong data |
| :--- | :--- | :--- |
| **Provider Down** | Một provider trả `error` liên tục ≥ 15 phút | `status=error` rate → 100% trong cửa sổ thời gian |
| **Latency Spike** | `latency_ms` tăng đột ngột 3x–10x so với baseline | P95 vượt SLO threshold |
| **Gradual Degradation** | `tokens_per_sec` giảm dần theo thời gian | Anomaly detection bắt được trước khi breach SLO |
| **Partial Recovery** | Provider hồi phục không hoàn toàn, error rate còn ~20% | Error budget burn rate giảm nhưng chưa về 0 |
| **Provider Failover** | Gateway chuyển sang provider backup, latency tăng tạm thời | Thay đổi `provider` field, latency tăng rồi ổn định |

### Interface simulator (Python)
```bash
python simulator.py \
  --scenario provider_down \
  --provider openai \
  --model gpt-5.5 \
  --start "2026-10-20T10:00:00Z" \
  --duration 60  # phút
```

### Schema output simulator (giống public dataset, thêm 1 field)
```jsonl
{
  "provider": "openai",
  "model": "openai/gpt-5.5",
  "status": "error",
  "ttft_ms": null,
  "latency_ms": null,
  "tokens_per_sec": null,
  "token_count": 0,
  "timestamp": "2026-10-20T10:15:00Z",
  "synthetic": true
}
```

> `"synthetic": true` — phân biệt dữ liệu giả lập vs. real, để khai báo đúng mục 12 hồ sơ nộp bài.

---

## 3. Chiến lược nạp dữ liệu vào MongoDB

### Collection: `llm_probes` (Time Series)
```js
db.createCollection("llm_probes", {
  timeseries: {
    timeField: "timestamp",
    metaField: "meta",    // { provider, model, synthetic }
    granularity: "hours"
  },
  expireAfterSeconds: 2592000  // TTL 30 ngày
})
```

### Seed script flow
1. Clone `llm-bench-data` → lấy 30–60 ngày gần nhất
2. Parse JSONL → batch insert vào `llm_probes`
3. Chạy simulator → seed các kịch bản sự cố vào cùng collection
4. Verify: Aggregation Pipeline đếm record theo `status`, `provider`, `model`

---

## 4. Khai báo (Checklist mục 12 nộp bài)

| Thành phần | Nguồn | Ghi chú |
| :--- | :--- | :--- |
| Public dataset | `llm-bench-data` (CC0) | Đo thực từ LLM API, không chứa PII |
| Synthetic data | Simulator tự viết | `"synthetic": true`, toàn bộ giả lập |
| Không dùng dữ liệu thật công ty | ✅ | Tuân thủ quy định hackathon |