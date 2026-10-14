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
- [Ý tưởng & Thiết kế kiến trúc](docs/IDEA.md)
- [Thể lệ & Yêu cầu Hackathon](docs/REQUIREMENT.md)
- [Kế hoạch Dataset & Simulator](docs/DATASET.md)
