# Reflex — Tài liệu thiết kế

> Các thư mục được đánh số theo lớp trừu tượng: **00 (tại sao) → 70 (làm thế nào và giao gì)**. Đọc theo thứ tự này sẽ dễ hiểu nhất.

```
docs/
├── 00-strategy/        Tại sao thiết kế như vậy — rubric, review bản nháp
├── 10-product/         Sản phẩm là gì — tầm nhìn, kịch bản sự cố
├── 20-architecture/    Hệ thống trông thế nào — kiến trúc, triển khai, chaos, ADR
├── 30-data/            MongoDB — data model, aggregation catalog
├── 40-observability/   Datadog — tín hiệu, monitor/SLO, dashboard
├── 50-reliability/     Bộ não vận hành — SLO, recovery, Cortex, memory, time machine, runbook
├── 60-interface/       Bề mặt tương tác — Console, API
├── 70-delivery/        Hiện thực & nộp bài — repo, kế hoạch, test, rủi ro, hồ sơ
├── archive/v0-draft/   Bản nháp cũ (chỉ để tham khảo, không dùng làm nguồn sự thật)
└── ref/                Tài liệu của BTC (workshop, website)
```

## Lộ trình đọc

| Bạn muốn… | Đọc |
| :--- | :--- |
| Hiểu ý tưởng trong 5 phút | [vision](10-product/vision.md) → [Silent Brownout](10-product/incident-scenarios.md#1-scenario-chính--the-silent-brownout-) |
| Biết vì sao đổi so với bản nháp | [draft-review](00-strategy/draft-review.md) → [design-review-v1](00-strategy/design-review-v1.md) |
| Đối chiếu với thể lệ | [competition-strategy](00-strategy/competition-strategy.md) |
| Hiểu kiến trúc | [system-architecture](20-architecture/system-architecture.md) → [ADRs](20-architecture/adr/README.md) |
| Làm phần MongoDB | [data model](30-data/mongodb-data-model.md) → [aggregation catalog](30-data/aggregation-catalog.md) |
| Làm phần Datadog | [architecture](40-observability/datadog-architecture.md) → [monitors & SLOs](40-observability/monitors-and-slos.md) → [dashboards](40-observability/dashboards.md) |
| Làm gateway và recovery | [slo](50-reliability/slo-and-error-budget.md) → [recovery engine](50-reliability/recovery-engine.md) |
| Làm AI agent | [cortex](50-reliability/cortex-agent.md) → [incident memory](50-reliability/incident-memory.md) |
| Bắt đầu code | [repository-structure](70-delivery/repository-structure.md) → [implementation-plan](70-delivery/implementation-plan.md) → [team-plan](70-delivery/team-plan.md) |
| Chuẩn bị nộp bài | [submission-kit](70-delivery/submission-kit.md) |

## Bảng thuật ngữ

| Thuật ngữ | Nghĩa |
| :--- | :--- |
| **Reflex** | Tên sản phẩm; cũng là vòng lặp nhanh trong gateway |
| **Cortex** | AI SRE agent; vòng lặp chậm |
| **Target** | Một (vendor, model) cụ thể, ví dụ `vendorA:large` |
| **Route** | Một use case của app, ví dụ `order.extract`; mỗi route có policy, validator và SLO riêng |
| **Provider SLO / Delivered SLO** | Chất lượng vendor trả về / chất lượng người dùng nhận được |
| **Quality SLI** | Tỉ lệ response vượt qua validator (schema, truncation, …) |
| **Burn rate** | Tốc độ tiêu error budget so với tốc độ "vừa đủ" |
| **Recovery Proof** | Kết quả kiểm định thống kê cho thấy SLI đã hồi phục |
| **Signature** | Vector 64 chiều mô tả hình dạng sự cố |
| **Demo profile** | Cấu hình SLO với cửa sổ được nén để trình diễn |
