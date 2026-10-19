# Reflex — Bản Tóm Tắt Thiết Kế Rút Gọn (v1-compact)

> **Mục đích:** Bộ tài liệu cô đọng toàn bộ 44 tài liệu chi tiết (từ `00-strategy` đến `70-delivery`) thành 7 chủ đề trực quan, tự nhiên và dễ đọc nhất cho nhóm 2 người phát triển và báo cáo.

---

## 🗺️ Bản đồ tài liệu rút gọn

| File | Chủ đề | Trọng tâm chính |
| :--- | :--- | :--- |
| [01-IDEA.md](01-IDEA.md) | **Ý tưởng & Đột phá** | Bài toán Silent Brownout (200 OK nhưng lỗi chất lượng), Cung phản xạ 2 tốc độ (Reflex ms + Cortex phút). |
| [02-ARCHITECTURE.md](02-ARCHITECTURE.md) | **Kiến trúc & Công nghệ** | Data Plane vs Control Plane, chốt Python monorepo (`uv`), cơ chế hot-reload không downtime. |
| [03-MONGO.md](03-MONGO.md) | **Dữ liệu MongoDB** | 4 Time Series collections theo nguồn, TTL tự động, Change Streams, Vector Search 64D. |
| [04-DATADOG.md](04-DATADOG.md) | **Giám sát Datadog** | Datadog LLM Observability, APM trace, Unified Tagging, Composite Monitor bắt bệnh vendor. |
| [05-SRE-RELIABILITY.md](05-SRE-RELIABILITY.md) | **Độ tin cậy & Tự chữa lành** | Quality SLI, chứng minh hồi phục (Two-proportion test), Incident Memory, Time Machine replay. |
| [06-DATASET-CHAOS.md](06-DATASET-CHAOS.md) | **Dữ liệu & Giả lập** | Public dataset `llm-bench-data`, app mẫu ShopMate (3 routes), Chaos Proxy bơm lỗi. |
| [07-PLAN.md](07-PLAN.md) | **Phân chia & Kế hoạch** | Phân vai Dev A & Dev B, 3 mốc kiểm soát (G1 Hợp lệ → G2 Khác biệt → G3 Nộp bài). |

---

## ⚡ 3 thông điệp kỹ thuật cốt tử cần nhớ
1. **Khác biệt hoàn toàn với Gateway thông thường:** Không chỉ bắt lỗi 500 hay timeout. Reflex bắt **lỗi im lặng** (cắt cụt token, vỡ schema JSON) ngay tại tầng mạng và tự chữa lành.
2. **Khai thác MongoDB đúng kỹ thuật:** Không dùng Change Streams trên Time Series (vì MongoDB không hỗ trợ). Tách collection đo đạc theo đúng tần suất ghi. Dùng Vector Search cho telemetry shape.
3. **Đạt chuẩn Enterprise SRE:** Đo Delivered SLO (người dùng nhận) tách biệt Provider SLO (vendor cấp). Mọi quyết định tự chữa lành đều có kiểm định toán học thống kê.
