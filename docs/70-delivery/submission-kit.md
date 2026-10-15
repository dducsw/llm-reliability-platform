# Submission Kit — 12 mục hồ sơ

| # | Mục | Nguồn trong repo | Trạng thái |
| :--- | :--- | :--- | :---: |
| 1 | Tên dự án & mô tả bài toán | [vision](../10-product/vision.md) §1–2 | ☐ |
| 2 | Thông tin đội & đầu mối | `README.md` | ☐ |
| 3 | Kiến trúc giải pháp | [system-architecture](../20-architecture/system-architecture.md) + ADRs | ☐ |
| 4 | Kiến trúc dữ liệu & data model MongoDB | [mongodb-data-model](../30-data/mongodb-data-model.md) + [aggregation-catalog](../30-data/aggregation-catalog.md) | ☐ |
| 5 | Kiến trúc Observability Datadog | [datadog-architecture](../40-observability/datadog-architecture.md) + [monitors](../40-observability/monitors-and-slos.md) + [dashboards](../40-observability/dashboards.md) | ☐ |
| 6 | Link repo & hướng dẫn cài đặt | `README.md` (cấp quyền cho giám khảo đến 22/11/2026) | ☐ |
| 7 | README: môi trường, triển khai, cấu hình, kiểm thử | `README.md` + [deployment](../20-architecture/deployment.md) | ☐ |
| 8 | MVP chạy được / link demo | Console + Datadog dashboard public link (nếu được phép) | ☐ |
| 9 | Video demo | §2 bên dưới | ☐ |
| 10 | Slide chung kết | §3 bên dưới | ☐ |
| 11 | Mô tả kịch bản sự cố | [incident-scenarios](../10-product/incident-scenarios.md) | ☐ |
| 12 | Khai báo thành phần tái sử dụng, dataset, AI | §4 bên dưới | ☐ |

## 2. Kịch bản video (mục tiêu 5–7 phút)

| Thời lượng | Cảnh | Màn hình |
| :--- | :--- | :--- |
| 0:00–0:30 | Hook: "Uptime 100% nhưng người dùng nhận rác" | Datadog: uptime xanh cạnh một response bị cắt |
| 0:30–1:15 | Kiến trúc: Reflex + Cortex, MongoDB + Datadog | Sơ đồ (slide) |
| 1:15–2:00 | **Detect**: bật S1 → quality burn → M3, composite M9 | Datadog D1 + monitor |
| 2:00–3:30 | **Investigate**: War Room, giả thuyết của Cortex kèm evidence, nhảy từ log → trace → LLMObs, Memory tìm sự cố tương tự | Console + Datadog |
| 3:30–4:30 | **Respond**: action auto qua guardrails → policy v17 → đường cong hồi phục → Recovery Proof → failback | Console + D1 overlays |
| 4:30–5:30 | **Impact**: Time Machine so sánh với static failover; con số requests saved, budget, cost | Console |
| 5:30–6:15 | Kỹ thuật MongoDB: TS × 4, rollup, vector signature, Change Streams; Query Explorer | Console + Compass |
| 6:15–6:45 | Kết: giá trị và hướng phát triển | Slide |

Quay bằng OBS, độ phân giải 1080p, Console ở `?present=1`, chạy `task demo:reset` trước mỗi lần quay. Mọi key được che, và terminal không hiển thị `.env`.

## 3. Dàn ý slide chung kết (10–12 slide)

1. Vấn đề (lỗi im lặng của LLM) · 2. Ý tưởng cung phản xạ hai tốc độ · 3. Kiến trúc · 4. MongoDB data model (nhiệt độ dữ liệu) · 5. Aggregation nổi bật (burn rate một lần quét, signature vector) · 6. Datadog (tagging, composite chẩn đoán, LLMObs) · 7. Demo live hoặc video · 8. Impact (Delivered vs Provider, Time Machine, ablation) · 9. An toàn của agent (bounded actions, evidence validator, prompt injection) · 10. Giới hạn và hướng phát triển · 11. Team.

**Q&A bank (chuẩn bị trước):** Vì sao không dùng LiteLLM/Portkey? · Change Streams trên Time Series? · Nếu Cortex hallucinate? · Time Machine đáng tin đến đâu? · Chi phí vận hành? · Vì sao quality validator không dùng LLM-judge? · Dữ liệu synthetic có thật không? · Scale lên 10k rps cần thay đổi gì?

## 4. Declarations

| Loại | Thành phần | License / nguồn | Ghi chú |
| :--- | :--- | :--- | :--- |
| Dataset | `Jwrede/llm-bench-data` | CC0 1.0 | Chỉ dùng làm baseline và replay hình dạng; đo bằng prompt "Hi", ≤ 20 token, qua OpenRouter |
| Dữ liệu synthetic | Prompt ShopMate, mock outputs, game-day incidents | Tự tạo | `synthetic: true` trên mọi record |
| Thư viện chính | FastAPI, httpx, PyMongo, Pydantic, ddtrace, datadog, structlog, fastjsonschema, React, ECharts, TanStack, Tailwind, shadcn/ui, Terraform DataDog provider | MIT / BSD / Apache-2.0 (kiểm tra lại khi chốt) | Liệt kê đầy đủ trong `THIRD_PARTY.md` (sinh tự động) |
| Hạ tầng | MongoDB Atlas, Datadog (trial), LLM vendor APIs | Dịch vụ | — |
| Công cụ AI hỗ trợ phát triển | *(điền: ví dụ Claude Code dùng cho thiết kế và code)* | — | Đội hiểu và giải thích được toàn bộ giải pháp |
| AI trong sản phẩm | Cortex dùng LLM qua API | — | Model ID được cấu hình; chi tiết trong [cortex-agent](../50-reliability/cortex-agent.md) |
