# BÁO CÁO KỸ THUẬT DỰ ÁN
## REFLEX — NỀN TẢNG GIÁM SÁT THỜI GIAN THỰC & TỰ HỒI PHỤC CHO ỨNG DỤNG LLM

**Cuộc thi:** MUGVN Hackathon 2026  
**Chủ đề:** Real-time Operations  
**Đơn vị tổ chức:** MongoDB User Group Vietnam (MUGVN) & Datadog  
**Đội thi:** We Bare Bears  
**Thành viên thực hiện:**
- Lê Đình Đức (Kỹ sư Dữ liệu)
- Bùi Hữu Lợi (Kỹ sư Phần mềm)

**Thời gian:** Tháng 11/2026  
**Trạng thái:** Bản chính thức nộp bài

<div style="page-break-after: always;"></div>

## LỜI CẢM ƠN

Đội ngũ kỹ sư We Bare Bears xin gửi lời cảm ơn chân thành tới Ban Tổ Chức cuộc thi: **Cộng đồng MongoDB User Group Vietnam (MUGVN)** và **Datadog**.

Đề tài Real-time Operations là một bài toán vận hành sát với thực tế sản xuất tại các doanh nghiệp ứng dụng AI hiện nay. Quá trình phát triển dự án giúp chúng tôi khai thác sâu các công nghệ lõi:
- Xử lý dữ liệu chuỗi thời gian nén và luồng sự kiện thời gian thực (Change Streams) trên **MongoDB Atlas**.
- Cơ chế giám sát tốc độ đốt ngân sách lỗi (Multi-Burn-Rate) và quan sát chuyên sâu cho AI trên **Datadog LLM Observability**.

Sự đồng hành của các chuyên gia kỹ thuật cùng hạ tầng tài nguyên được tài trợ từ MongoDB và Datadog là điểm tựa quan trọng giúp nhóm hoàn thiện giải pháp Reflex từ bản vẽ kiến trúc đến sản phẩm chạy thực tế.

## TÓM TẮT ĐIỀU HÀNH

**Reflex** giải quyết bài toán sụt giảm chất lượng âm thầm (**The Silent Brownout**) trong các hệ thống GenAI thời gian thực:
- **Vấn đề:** Khi mô hình LLM gặp lỗi (câu trả lời bị cắt cụt, vỡ cấu trúc JSON Schema, hoặc từ chối ngầm), mã HTTP vẫn trả về 200 OK và mạng vẫn ổn định. Các hệ thống giám sát truyền thống không phát hiện ra, trong khi nghiệp vụ người dùng bị gián đoạn.
- **Giải pháp:** Áp dụng mô hình Cung phản xạ hai tốc độ (Two-Speed Architecture):
  1. *Data Plane (< 2.8ms overhead):* Kiểm định nội dung in-flight, tự động ngắt mạch và thử lại sang mô hình dự phòng lành lặn trong vài mili-giây.
  2. *Control Plane (Giây đến Phút):* AI Agent Cortex kết hợp giám sát Multi-Burn-Rate trên Datadog và tra cứu Incident Memory (Vector Search 64D) trên MongoDB Atlas để tìm nguyên nhân gốc rễ, nạp chính sách điều phối mới xuống Gateway trong **dưới 1 giây** qua Change Streams.
- **Kết quả:** Duy trì Delivered SLO ở mức 99.6% khi nhà cung cấp upstream suy giảm xuống 61%, giảm 91.8% thiệt hại ngân sách lỗi so với các proxy gateway thông thường.

<div style="page-break-after: always;"></div>

## MỤC LỤC BÁO CÁO KỸ THUẬT

Bộ hồ sơ báo cáo gồm 7 chuyên đề chuyên sâu:

1. [01 — Bối Cảnh, Mục Tiêu & Giải Pháp](./01-IDEA.md)  
Khoảng mù The Silent Brownout, 4 mục tiêu kỹ thuật, kiến trúc Cung phản xạ hai tốc độ và 6 điểm nhấn kỹ thuật (nổi bật với Trục Dữ Liệu Thời Gian Thực MongoDB Atlas & Nền Tảng Quan Sát Datadog).

2. [02 — Kiến Trúc Hệ Thống & Trụ Cột Công Nghệ](./02-ARCHITECTURE.md)  
Phân tách Data Plane vs Control Plane, cơ sở lý thuyết vì sao chọn MongoDB Atlas và Datadog, cơ chế Zero-Downtime Hot-Reload.

3. [03 — Thiết Kế Cơ Sở Dữ Liệu MongoDB Atlas](./03-MONGO.md)  
Chiến lược phân tầng Hot/Warm/Operational, thiết kế 4 Time Series Collections, cấu trúc Incident Memory 64D và thư viện Aggregation Pipelines.

4. [04 — Kiến Trúc Quan Sát Thời Gian Thực Trên Datadog](./04-DATADOG.md)  
Toán học cảnh báo Multi-Window Multi-Burn-Rate theo chuẩn Google SRE, Composite Monitor M9 phân lập lỗi, và cấu hình Datadog LLMObs.

5. [05 — Vòng Lặp Tự Chữa Lành Khép Kín (Closed-Loop SRE)](./05-GUIDE.md)  
Quy trình 5 pha (Detect ➔ Isolate ➔ Diagnose ➔ Mitigate ➔ Verify), cơ chế rào chắn Bounded Actions và kiểm định thống kê toán học.

6. [06 — Kịch Bản Vận Hành & Giả Lập Sự Cố (Chaos Engineering)](./06-CHAOS.md)  
Thiết kế Chaos Proxy với 5 dạng lỗi thực tế, kịch bản trọng tâm S1, tính khách quan chống gian lận và tính tái lập cao với Seed 42.

7. [07 — Tổng Kết Dự Án, Hướng Dẫn Triển Khai & Định Hướng Phát Triển](./07-SUMMARY.md)  
Tổng kết giải pháp, hướng dẫn triển khai đơn giản, những điểm đạt được, điểm hạn chế, lộ trình tương lai, bảng khai báo thành phần và kịch bản demo.

## BẢNG ĐỐI CHIẾU 12 HẠNG MỤC NỘP BÀI

Bảng đối chiếu phục vụ Ban Giám Khảo tra cứu theo yêu cầu tại `docs/submission/README.md`:

| # | Hạng mục nộp bài | Vị trí trình bày | Trạng thái |
| :---: | :--- | :--- | :---: |
| 1 | Tên dự án và mô tả bài toán | [01-IDEA.md](./01-IDEA.md) | Đầy đủ |
| 2 | Thông tin đội thi và đầu mối liên hệ | [README.md](./README.md) (Trang bìa) | Đầy đủ |
| 3 | Kiến trúc giải pháp và ứng dụng | [02-ARCHITECTURE.md](./02-ARCHITECTURE.md) & [05-GUIDE.md](./05-GUIDE.md) | Đầy đủ |
| 4 | Kiến trúc dữ liệu trên MongoDB | [03-MONGO.md](./03-MONGO.md) | Đầy đủ |
| 5 | Kiến trúc observability trên Datadog | [04-DATADOG.md](./04-DATADOG.md) | Đầy đủ |
| 6 | Repository mã nguồn và cài đặt | [07-SUMMARY.md](./07-SUMMARY.md) (Mục 2) | Đầy đủ |
| 7 | Môi trường, triển khai, cấu hình & test | [07-SUMMARY.md](./07-SUMMARY.md) (Mục 2) | Đầy đủ |
| 8 | MVP và kênh truy cập demo | [07-SUMMARY.md](./07-SUMMARY.md) (Mục 2) | Đầy đủ |
| 9 | Video demo | [07-SUMMARY.md](./07-SUMMARY.md) (Mục 7) | Đầy đủ |
| 10 | Slide thuyết trình chung kết | [slide.md](../slide.md) & [slide.html](../slide.html) | Đầy đủ |
| 11 | Giả lập sự cố và kịch bản vận hành | [06-CHAOS.md](./06-CHAOS.md) | Đầy đủ |
| 12 | Khai báo dataset, thư viện & công cụ AI | [07-SUMMARY.md](./07-SUMMARY.md) (Mục 6) | Đầy đủ |

## DANH MỤC BIỂU ĐỒ KIẾN TRÚC

Hệ thống biểu đồ vector SVG chuẩn mực tại [images/](./images/):
- [two-speed-loop.svg](./images/two-speed-loop.svg) — Tổng quan kiến trúc Cung phản xạ hai tốc độ Reflex.
- [change-streams-hot-reload.svg](./images/change-streams-hot-reload.svg) — Luồng cập nhật cấu hình thời gian thực qua MongoDB Change Streams.
- [mongo-data-tiering.svg](./images/mongo-data-tiering.svg) — Phân tầng dữ liệu MongoDB Atlas (Hot / Warm / Operational).
- [closed-loop-sre.svg](./images/closed-loop-sre.svg) — Quy trình tự chữa lành khép kín 5 pha của Reflex Control Plane.
- [multi-burn-rate-logic.svg](./images/multi-burn-rate-logic.svg) — Sơ đồ logic cảnh báo Multi-Window Multi-Burn-Rate Datadog.
- [cortex-llmobs-trace.svg](./images/cortex-llmobs-trace.svg) — Cấu trúc distributed trace trong Datadog LLM Observability.
- [chaos-injection-flow.svg](./images/chaos-injection-flow.svg) — Kiến trúc bơm lỗi và phân lập luồng của Chaos Proxy.
