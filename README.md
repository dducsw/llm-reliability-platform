# LLM Monitor & Reliability Platform (Reflex)

> Dự án tham gia [MUGVN Hackathon 2026: Real-time Operations](https://mini-hackathon-sep-2026.mugvn.com)

---

## Đội thi: We Bare Bears
- **Lê Đình Đức** — Data Platform Engineer (*Student @ HCMUT*)
- **Bùi Hữu Lợi** — Software Engineer (*Student @ HCMUT*)

---

## Kiến trúc hệ thống
Hệ thống vận hành theo cơ chế **Dual-Loop** (Hai vòng lặp khép kín):
- **Fast-Loop (Data Plane — LLM Gateway)**: Proxy tương thích chuẩn OpenAI, độ trễ cực thấp (<5ms overhead). Tích hợp routing thông minh, circuit breaker, retry, auto-fallback và output validation (JSON schema, truncation, semantic).
- **Slow-Loop (Control Plane & Cortex AI Agent)**: Thu thập telemetry liên tục vào MongoDB Time Series, tính toán SLO multi-burn-rate, đẩy metrics/traces sang Datadog. Cortex Agent chẩn đoán nguyên nhân gốc (RCA) và tự động kích hoạt policy khắc phục (traffic shedding, model failover, prompt downgrade).

**Luồng dữ liệu:**
```mermaid
flowchart LR
    Client([Client App]) --> GW[LLM Gateway / Data Plane]
    GW --> Vendors[(LLM Vendors / Fallback)]
    GW --> Mongo[(MongoDB Time Series & Events)]
    GW --> DD[Datadog APM / LLMObs / Monitors]
    Mongo --> CP[Control Plane & Sentinel]
    DD --> Cortex[Cortex AI SRE Agent]
    Cortex -->|Remediation Actions| GW
```

---

## Hình ảnh hệ thống

| Reflex Console & Cortex AI Agent | Datadog Ops Dashboard (D1) |
| :---: | :---: |
| ![Reflex Console](docs/assets/Cortex-Console-Overview.jpeg) | ![Datadog Ops](docs/assets/DataDog-Ops-D1.jpeg) |
| **Datadog SLO & Error Budget (D2)** | **Datadog Cortex LLMObs (D3)** |
| ![Datadog SLO](docs/assets/DataDog-SLO-D2.jpeg) | ![Datadog Cortex](docs/assets/DataDog-Cortex-D3.jpeg) |
| **Datadog MongoDB Engine Metrics (D4)** | **MongoDB Atlas Cluster Overview** |
| ![Datadog Mongo D4](docs/assets/DataDog-Mongo-D4.jpeg) | ![Mongo Atlas](docs/assets/Mongo-Atlas-Overview.png) |

---

## Tính năng chính
- **Giám sát Telemetry Thời Gian Thực (Sub-Second Ingestion)**: Thu nạp từng request/stream qua MongoDB Time Series & DogStatsD. Đo lường tức thì P95/P99 latency, token throughput, error rate và chi phí thời gian thực theo từng route và vendor.
- **LLM Tracing & Observability Đa Chiều (Datadog APM & LLMObs)**: Distributed tracing end-to-end từ Client ➔ Gateway ➔ Vendor. Theo dõi real-time payload, span context, rate limit headers và token distribution.
- **Cảnh báo Cháy Ngân Sách Lỗi Tức Thì (Real-Time SLO Multi-Burn-Rate)**: Phát hiện vi phạm SLO sớm qua thuật toán multi-window multi-burn-rate (chuẩn Google SRE); cảnh báo ngay khi tốc độ tiêu hao error budget vượt ngưỡng cho phép thay vì phụ thuộc ngưỡng tĩnh trễ.
- **Kiểm định Chất Lượng In-Flight (Quality SLI Validation)**: Đánh giá tức thì độ hợp lệ của response ngay trên luồng stream (JSON schema, truncation, format guardrails) để phát hiện "silent failures" (lỗi trả về 200 OK nhưng nội dung rác/cắt cụt).
- **Reflex Live Console & Time Machine**: UI thời gian thực (live topology, stream metrics, incident timeline). Tích hợp Time Machine cho phép tua lại chính xác trạng thái toàn hệ thống tại thời điểm phát sinh sự cố.
- **Điều hướng & Tự Hồi Phục Tức Thì (Smart Gateway & Circuit Breaker)**: Kết nối trực tiếp với kết quả telemetry thời gian thực để tự động ngắt mạch, retry có kiểm soát và fallback tức thì khi vendor upstream gặp sự cố.
- **Cortex Autonomous SRE Agent**: AI Agent tự động tiêu thụ telemetry/traces thời gian thực, chẩn đoán nguyên nhân gốc (RCA) và tự động thực thi kịch bản khắc phục.

---

## Điểm nổi bật
- **Closed-Loop Self-Healing**: Quy trình tự động hoá toàn diện: *Detect ➔ Isolate (Breaker) ➔ Diagnose (Cortex) ➔ Mitigate (Actuator) ➔ Verify (Verifier)* không cần can thiệp thủ công.
- **Delivered SLO vs Provider SLO**: Tách biệt chất lượng thực tế người dùng nhận được khỏi biến động từ nhà cung cấp upstream (nâng độ tin cậy từ 95% upstream lên 99.9% delivered).
- **Hiệp đồng MongoDB + Datadog**:
  - **MongoDB**: Lưu trữ telemetry hiệu năng cao (Time Series Collections), phản ứng tức thì qua Change Streams, và truy vấn tương đồng sự cố qua Vector Search.
  - **Datadog**: APM Distributed Tracing, DogStatsD real-time metrics, LLM Observability và hệ thống Dashboard chuẩn SRE (D1 Ops, D2 SLO, D3 Cortex, D4 Mongo).

---

## Cấu trúc tài liệu (`docs/`)

Toàn bộ tài liệu chi tiết được tổ chức theo các tầng chức năng:

| Thư mục | Nội dung chính |
| :--- | :--- |
| [`docs/00-strategy/`](docs/00-strategy/) | Bối cảnh chiến lược, phân tích rubric cuộc thi và review thiết kế |
| [`docs/10-product/`](docs/10-product/) | Tầm nhìn sản phẩm Reflex, chân dung người dùng và kịch bản sự cố mẫu (Silent Brownout, …) |
| [`docs/20-architecture/`](docs/20-architecture/) | Kiến trúc tổng thể, sequence diagrams, quyết định kỹ thuật (ADRs) và Chaos Engine |
| [`docs/30-data/`](docs/30-data/) | Mô hình dữ liệu MongoDB (Time Series, Change Streams) và danh mục pipeline Aggregation (A1–A18) |
| [`docs/40-observability/`](docs/40-observability/) | Thiết kế quan sát Datadog: metrics, traces, monitors, SLOs và dashboards |
| [`docs/50-reliability/`](docs/50-reliability/) | Động cơ tin cậy: thuật toán SLO, Recovery Engine, Cortex AI SRE và Incident Memory |
| [`docs/60-interface/`](docs/60-interface/) | Thiết kế giao diện Reflex Console (SPA React) và đặc tả Backend-For-Frontend (BFF) |
| [`docs/70-delivery/`](docs/70-delivery/) | Quy hoạch repository, kế hoạch hiện thực, chiến lược kiểm thử và quản lý rủi ro |
| [`docs/submission/`](docs/submission/) | Hồ sơ nộp bài, kịch bản thuyết trình và artifact demo hackathon |
| [`docs/v1-compact/`](docs/v1-compact/) | Bản tóm tắt cô đọng dành cho người đọc nhanh |
| [`docs/assets/`](docs/assets/) | Tài nguyên media, ảnh chụp màn hình dashboards và console |

---

## Cấu trúc repository

Chi tiết: [repository-structure](docs/70-delivery/repository-structure.md).

| Thư mục | Nội dung |
| :--- | :--- |
| `apps/gateway` | **Data plane** — OpenAI-compatible gateway (FastAPI) |
| `apps/control-plane` | **Control plane** — sentinel, incidents, policy engine, actuator, verifier, time machine, BFF |
| `apps/cortex` | AI SRE agent (Datadog LLM Observability) |
| `apps/simulation` | ShopMate traffic, mock-llm, chaos-proxy, prober, scenario runner, bench importer |
| `apps/console` | React SPA (Vite + TanStack + ECharts) |
| `packages/reflex-core` | Domain thuần, không I/O: contracts, router, breaker, retry, SLI, validators |
| `packages/reflex-mongo` | Client, repos, pipelines A1–A18, change streams, migrations |
| `packages/reflex-telemetry` | ddtrace / LLMObs / structlog / DogStatsD, tag catalog, Datadog API |
| `infra/` | Compose, nginx, Mongo search indexes, Terraform Datadog |
| `scenarios/` · `seeds/` | Scenario-as-code · dữ liệu seed |

---

## Quickstart

Yêu cầu: Python 3.12+, [uv](https://docs.astral.sh/uv/), [Task](https://taskfile.dev), Docker, Node 22 + pnpm.

```bash
cp .env.example .env       # điền MONGODB_URI, DD_API_KEY, …
task install
task up && task seed
task scenario -- silent-brownout
```
