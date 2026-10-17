# LLM Monitor & Reliability Platform

> Dự án tham gia [MUGVN Hackathon 2026: Real-time Operations](https://mini-hackathon-sep-2026.mugvn.com)

---

## Đội thi: We Bare Bears
- **Lê Đình Đức** — Data Engineer (*Student @ HCMUT*)
- **Bùi Hữu Lợi** — Software Engineer (*Student @ HCMUT*)

---

## Giới thiệu ngắn
Nền tảng giám sát và đảm bảo độ tin cậy thời gian thực cho ứng dụng tích hợp LLM:
- **LLM Gateway:** Điều phối request, kiểm soát lỗi, circuit breaker và auto-fallback.
- **MongoDB:** Lưu trữ chuỗi telemetry (Time Series), aggregate phân tích P95 latency, cost/token và SLO.
- **Datadog:** Dashboard giám sát thời gian thực, APM tracing và cảnh báo sự cố vi phạm SLO.

---

## Tài liệu dự án
Toàn bộ thiết kế nằm trong [`docs/`](docs/README.md). Nên bắt đầu từ:
- [Tầm nhìn sản phẩm — Reflex](docs/10-product/vision.md)
- [Kịch bản sự cố trình diễn](docs/10-product/incident-scenarios.md)
- [Kiến trúc hệ thống](docs/20-architecture/system-architecture.md)
- [Kế hoạch hiện thực](docs/70-delivery/implementation-plan.md)
