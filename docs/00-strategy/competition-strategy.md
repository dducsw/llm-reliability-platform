# Chiến lược thi — Ánh xạ Rubric → Thiết kế

> Nguồn: [thể lệ chính thức](https://mini-hackathon-sep-2026.mugvn.com) và [bản tóm tắt thể lệ](../archive/v0-draft/REQUIREMENT.md) (đã đối chiếu lại với website vào 15/10/2026).

## 1. Cách giám khảo sẽ nhìn bài

Đề bài là **"ứng dụng tự phát hiện và xử lý sự cố"**. Hầu hết các đội sẽ làm cùng một chuỗi: *app → lỗi → Datadog alert → restart hoặc failover → biểu đồ xanh lại*. Vì vậy:

- **Creativity (30%)**: nếu chỉ dừng ở "failover khi provider down" thì bài sẽ giống bài của các đội khác. Cần những sự cố mà **monitor uptime không thấy**, và một cách dùng MongoDB/Datadog mà các đội khác ít khả năng nghĩ tới.
- **Technical (30%)**: giám khảo MongoDB sẽ xem data model, granularity, metaField, `$match` có đứng đầu pipeline không, có hiểu giới hạn của Time Series không (Change Streams không chạy trên TS). Giám khảo Datadog sẽ xem tagging thống nhất, khả năng nhảy metric → log → trace, monitor có ý nghĩa thật.
- **Impact (30%)**: cần **con số**. "Provider chỉ đạt 61% availability nhưng người dùng vẫn nhận 99,6%." "Policy mới tiết kiệm 37% error budget so với static failover."
- **Presentation (10%)**: demo phải lặp lại được 100%. Scenario-as-code và seed cố định giúp quay video bao nhiêu lần kết quả cũng giống nhau.

## 2. Ma trận Rubric × Tính năng

| Tính năng | Creativity | Technical | Impact | Presentation | Tài liệu |
| :--- | :---: | :---: | :---: | :---: | :--- |
| Two-speed loop: Reflex (ms) + Cortex (phút) | ●●● | ●● | ●● | ●● | [vision](../10-product/vision.md) |
| Quality SLI: phát hiện "200 OK nhưng hỏng" | ●●● | ●● | ●●● | ●● | [slo](../50-reliability/slo-and-error-budget.md) |
| Delivered SLO ≠ Provider SLO (dual ledger) | ●● | ●● | ●●● | ●●● | [slo](../50-reliability/slo-and-error-budget.md) |
| Incident Memory: Vector Search trên hình dạng time series | ●●● | ●●● | ●● | ●● | [incident-memory](../50-reliability/incident-memory.md) |
| Budget-aware adaptive routing | ●● | ●●● | ●●● | ● | [recovery-engine](../50-reliability/recovery-engine.md) |
| Time Machine: replay phản thực tế | ●●● | ●●● | ●●● | ●●● | [time-machine](../50-reliability/time-machine.md) |
| Recovery Proof có kiểm định thống kê | ●● | ●● | ●●● | ●● | [recovery-engine](../50-reliability/recovery-engine.md#verify) |
| Composite monitor phân biệt lỗi provider và lỗi của mình | ●● | ●●● | ●● | ●● | [monitors](../40-observability/monitors-and-slos.md) |
| Cortex agent được quan sát bằng Datadog LLM Observability | ●● | ●● | ● | ●● | [cortex](../50-reliability/cortex-agent.md) |
| Chaos Proxy + scenario-as-code | ● | ●● | ● | ●●● | [chaos](../20-architecture/simulation-and-chaos.md) |
| Observability-as-code (Terraform) + Mongo migrations | ● | ●●● | ● | ●● | [repo](../70-delivery/repository-structure.md) |

## 3. Checklist yêu cầu bắt buộc → nơi đáp ứng

| Yêu cầu | Đáp ứng bởi |
| :--- | :--- |
| MongoDB là nền tảng dữ liệu vận hành chính | Toàn bộ telemetry, SLO, policy, incident, action và memory nằm trong MongoDB; gateway hot-reload policy từ MongoDB |
| Data model hợp lý, access pattern hiệu quả | [mongodb-data-model](../30-data/mongodb-data-model.md): mỗi collection gắn với query cụ thể, có bảng index → query |
| Aggregation Pipeline phục vụ bài toán | [aggregation-catalog](../30-data/aggregation-catalog.md): 16 pipeline, mỗi pipeline gắn với một bước Detect/Investigate/Respond |
| (KK) Time Series, Window functions, TTL, Change Streams, Vector Search | Có đủ, và mỗi feature được dùng vì bài toán cần |
| ≥1 Dashboard | 3 dashboard: Operations, SLO & Budget, Cortex Agent |
| ≥1 Monitor có ý nghĩa | 11 monitor, gồm SLO burn rate và composite |
| ≥1 năng lực bổ sung | APM + Distributed Tracing + Log Management + Anomaly Detection + LLM/Agent Observability |
| Correlate metrics, logs, traces, context | Unified tagging, `incident_id` propagation, trace-log injection, Events overlay, deep link từ Console |
| Loop Detect → Investigate → Respond trên dữ liệu thật của hệ thống | [incident-scenarios](../10-product/incident-scenarios.md): scenario chính "Silent Brownout" và 4 scenario phụ |
| Không PII, không secret trong repo | Prompt synthetic; secret qua `.env` (gitignored) và pre-commit `gitleaks` |
| Khai báo AI, dataset, thư viện | [submission-kit](../70-delivery/submission-kit.md) §Declarations |

## 4. Chiến lược trình diễn

1. **Mở bằng cú sốc**: dashboard uptime xanh 100%, nhưng người dùng đang nhận câu trả lời bị cắt cụt. "Monitor của bạn không thấy được sự cố này."
2. **Hai vòng lặp**: Reflex cứu người dùng trong vòng mili giây. Cortex tìm ra root cause trong vài phút và đưa bằng chứng.
3. **Chốt bằng Time Machine**: "Nếu dùng chính sách failover tĩnh như mọi gateway khác, sự cố này đã đốt 41% error budget. Reflex chỉ đốt 6%." Con số này được tính lại ngay trước mặt giám khảo bằng aggregation pipeline.
