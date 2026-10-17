# Review bản nháp v0 — Giữ gì, sửa gì, bỏ gì

> Bản nháp v0 (nằm ở [`../archive/v0-draft/`](../archive/v0-draft/)) được viết bằng một model rẻ và chưa ai kiểm chứng. Tài liệu này đối chiếu v0 với ba nguồn: thể lệ chính thức, slide MongoDB Workshop (`docs/ref/`) và README gốc của dataset `llm-bench-data`. Mục đích là chỉ lấy ý tưởng tổng quan, không kế thừa lỗi.

---

## 1. Ý tưởng giữ lại

| Ý tưởng v0 | Đánh giá | Hướng phát triển trong v1 |
| :--- | :--- | :--- |
| Gateway đứng giữa app và LLM provider | ✅ Đúng hướng | Trở thành **data plane** có router chấm điểm, circuit breaker, hedging và quality validator |
| Time Series cho telemetry | ✅ Đúng, cũng là khuyến nghị của workshop | Chia thành 3 collection theo **tần suất nguồn** (mỗi nguồn một granularity), thêm rollup ấm |
| SLO + error budget + multi-window burn rate | ✅ Đúng (theo Google SRE Workbook) | Bổ sung SLI chất lượng, tách SLO **delivered** khỏi SLO **provider** |
| Change Streams kích hoạt recovery | ✅ Đúng, nhưng v0 đặt sai chỗ (xem §2) | Dùng cho policy hot-reload, vòng đời incident và phê duyệt action |
| Datadog chia 3 zone Detect/Investigate/Respond | ✅ Hợp với rubric | Giữ nguyên, thêm composite monitor để chẩn đoán phân biệt |
| Simulator kịch bản sự cố | ✅ Bắt buộc phải có cho demo | Nâng thành **Chaos Proxy + scenario-as-code** |

## 2. Lỗi sai cần sửa

| # | Lỗi trong v0 | Thực tế | Sửa trong v1 |
| :--- | :--- | :--- | :--- |
| E1 | `DATASET.md`: field `provider` là provider thật, status gồm `timeout` | README dataset: `provider` **luôn là `openai`** vì probe đi qua OpenRouter (đây là tên giao thức). Status chỉ có `healthy` hoặc `error`. Mỗi probe gửi "Hi" và cắt ở 20 token output | Lấy vendor từ tiền tố của `model` (`anthropic/…`). Chỉ dùng dataset làm **baseline và replay**, không coi là dữ liệu chi phí hay chất lượng |
| E2 | `granularity` lúc `"hours"` (DATASET), lúc `"minutes"` (MONGO) cho cùng một collection | Workshop: granularity đặt theo tần suất của **một nguồn** | Dataset hourly đi vào `bench_ts` (hours). Probe 15s đi vào `probes_ts` (seconds). Request đi vào `requests_ts` (seconds) |
| E3 | Trộn dữ liệu public, synthetic và gateway vào chung `llm_probes` | Các nguồn khác tần suất và khác ngữ nghĩa, gộp lại làm hỏng bucket và làm sai SLI | Mỗi loại nguồn một collection. Cờ `synthetic` nằm trong `meta` |
| E4 | Mâu thuẫn stack: Python/FastAPI (DATAGOG, SRE) và Go/Gin (DASHBOARD) | — | Chốt một stack, xem [ADR-0001](../20-architecture/adr/0001-python-monorepo.md) |
| E5 | Model cũ (`gpt-4o`, `claude-3-5-sonnet`, `gemini-2.0-flash`) bị hard-code | Đến 10/2026 các model này đã cũ | Catalog `targets` lưu trong MongoDB, model ID lấy từ cấu hình, không hard-code |
| E6 | Monitor P95 viết `p95(last_15m): distribution metric …` | Cú pháp này không hợp lệ | `percentile(last_15m):p95:llm.request.latency{…} by {target} > X`. Monitor được quản lý bằng Terraform |
| E7 | Datadog webhook gọi thẳng `/api/recovery/trigger` trên localhost | Datadog SaaS không gọi được vào localhost | Cần public endpoint (VM hoặc Cloudflare Tunnel) có xác thực header bí mật, xem [deployment](../20-architecture/deployment.md) |
| E8 | SLO latency định nghĩa dạng "P95 ≤ 3000ms" | Latency SLO chuẩn là **tỉ lệ good events** (request < ngưỡng) / total, nhờ vậy mới tính được error budget và burn rate | Latency SLI = `count(latency < T) / count(valid)` |
| E9 | "Không pre-aggregate" kèm "tính 30 ngày on-demand trên raw" | Mâu thuẫn với TTL 30 ngày. Quét 30 ngày raw mỗi phút rất tốn. Workshop khuyên làm hot/warm rollup bằng `$merge` | Rollup `sli_1m` và `sli_1h` dùng **histogram cộng dồn được** (§ data model) |
| E10 | Đo MTTR từ `detected_at`, nhưng lại ghi "MTTR đo từ first error" | Hai định nghĩa tự mâu thuẫn | Định nghĩa thống nhất ở [slo-and-error-budget](../50-reliability/slo-and-error-budget.md#kpi) |
| E11 | Circuit breaker mở sau "5 lỗi liên tiếp" | Đếm lỗi liên tiếp dễ bật/tắt liên tục khi traffic cao và nhạy sai khi traffic thấp | Sliding window theo error-rate, có `min_requests`, backoff cho thời gian mở |
| E12 | Burn rate chia cứng cho `0.001` | Mỗi SLO có objective riêng | Lấy `1 - objective` từ document `slos` |
| E13 | `$setWindowFields` chạy trên toàn bộ raw, không có `$match` theo thời gian | Workshop: `$match` theo metaField và time phải đứng đầu pipeline | Mọi pipeline trong [aggregation catalog](../30-data/aggregation-catalog.md) đều bắt đầu bằng `$match` có giới hạn |
| E14 | Incident dedup không có cơ chế | Webhook Datadog và detector nội bộ có thể cùng mở 2 incident | `dedup_key` + **partial unique index** trên incident đang mở |

## 3. Bỏ hoặc hạ cấp

- **"Bỏ qua Vector Search"** → v1 **đảo ngược** quyết định này. Vector Search trên *hình dạng tín hiệu* của sự cố là một trong các điểm sáng tạo chính ([Incident Memory](../50-reliability/incident-memory.md)).
- **PagerDuty và Slack thật** → không cần. Dùng Datadog notification lên Slack webhook (tùy chọn) và Console.
- **Embed dashboard Datadog bằng iframe** → bỏ, vì Datadog chặn embed nếu không bật public sharing. Thay bằng deep link có time range và `incident_id`.

## 4. Kết luận

v0 đúng về **hình dạng** (gateway + Mongo + Datadog + SLO) nhưng nhiều chi tiết sai, và chưa có gì khác biệt so với một LLM gateway thông thường (LiteLLM, Portkey đều đã có retry/fallback). v1 giữ hình dạng đó và đặt trọng tâm vào các trụ cột sáng tạo ở [`../10-product/vision.md`](../10-product/vision.md).
