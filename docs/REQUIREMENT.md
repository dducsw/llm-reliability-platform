# MUGVN Hackathon 2026: Real-time Operations
> **Thông tin chính thức, Thể lệ & Yêu cầu kỹ thuật từ [mini-hackathon-sep-2026.mugvn.com](https://mini-hackathon-sep-2026.mugvn.com)**

---

## 1. Thông tin chung

| Hạng mục | Chi tiết |
| :--- | :--- |
| **Đơn vị tổ chức** | MUGVN (MongoDB User Group Vietnam) |
| **Nhà tài trợ** | MongoDB, Inc. & Datadog, Inc. |
| **Chủ đề** | **Real-time Operations** — Ứng dụng tự phát hiện, điều tra và xử lý sự cố vận hành |
| **Hình thức** | Online toàn bộ |
| **Quy mô đội** | 1 – 3 thành viên (chỉ định 1 trưởng đội; cần email công việc để kích hoạt Datadog trial) |
| **Tổng giải thưởng** | **1.500 USD** (30.000.000 VNĐ tiền mặt + quà tặng Top 8 + voucher thi chứng chỉ MongoDB) |
| **Website chính thức** | [mini-hackathon-sep-2026.mugvn.com](https://mini-hackathon-sep-2026.mugvn.com) \| [Thể lệ chi tiết (/terms)](https://mini-hackathon-sep-2026.mugvn.com/terms) |

---

## 2. Lịch trình quan trọng (ICT - UTC+7)

| Mốc thời gian | Hoạt động | Ghi chú |
| :--- | :--- | :--- |
| **25/09/2026** | Mở cổng đăng ký & công bố thể lệ | Form Google chính thức |
| **12/10 (12:00–13:00)** | **Lunch & Learn: Datadog Workshop** | Diễn giả: Bang Truong (Datadog) |
| **13/10 (12:00–13:00)** | **Lunch & Learn: MongoDB Workshop** | Diễn giả: Jackson Nguyen (MongoDB) |
| **12/10/2026, 23:59** | **Đóng đăng ký đội** | Đăng ký sau giờ này không nhận được link nộp bài |
| **17/10 – 31/10/2026** | **Thời gian Build MVP & kích hoạt Datadog Trial** | Phát triển giải pháp cốt lõi |
| **31/10/2026, 23:59** | **Hạn chót nộp bài dự thi (Submission Deadline)** | Chốt commit cuối cùng |
| **01/11 – 04/11/2026** | Vòng chấm sơ loại (Dự kiến) | Ban giám khảo chấm bài hợp lệ |
| **05/11/2026** | Công bố Top 8 đội vào Chung kết (Dự kiến) | Email và Fanpage MUGVN |
| **08/11/2026** | **Vòng Chung kết Online & Trao giải (Dự kiến)** | Pitching, Q&A với ban giám khảo |

---

## 3. Đề bài & Luồng kịch bản vận hành (The Challenge)

### 3.1. Đề bài mở
Tự do chọn bài toán và lĩnh vực (Web app, API, data pipeline, microservices, LLM Gateway/Agent, IoT, Fintech, Thương mại điện tử, Game backend,...).  
**Yêu cầu cốt lõi:** Xây dựng ứng dụng dùng **MongoDB** làm nền tảng dữ liệu và **Datadog** để quan sát, phát hiện, điều tra và xử lý sự cố.

### 3.2. Chu trình vận hành bắt buộc (Loop 3 bước)
Bài thi phải trình diễn trọn vẹn 1 kịch bản sự cố trên dữ liệu thực tế của hệ thống:
1. **Phát hiện (Detect):** Monitor & Alert phát hiện sớm lỗi, suy giảm hiệu năng hoặc rủi ro trước người dùng.
2. **Điều tra (Investigate):** Tương quan dữ liệu (metrics, logs, traces, APM context) để khoanh vùng chính xác root-cause.
3. **Phản ứng & Phục hồi (Respond):** Khắc phục sự cố (tự động hoặc can thiệp) và chứng minh bằng dữ liệu/metrics rằng hệ thống đã hồi phục bình thường.

---

## 4. Yêu cầu kỹ thuật tối thiểu (Minimum Technical Requirements)

> [!IMPORTANT]
> Bài thi không đáp ứng đủ các tiêu chí bắt buộc dưới đây sẽ **không được chấm sơ loại**.

### 4.1. MongoDB
- **Bắt buộc:**
  - MongoDB là nền tảng dữ liệu vận hành chính của ứng dụng.
  - Data model hợp lý và access pattern hiệu quả.
  - Sử dụng **Aggregation Pipeline** để phân tích dữ liệu phục vụ bài toán.
  - Việc sử dụng MongoDB phải gắn chặt với bài toán vận hành đã chọn.
- **Khuyến khích (tùy bài toán):**
  - **Time Series Collections** cho telemetry, metric, chuỗi thời gian.
  - **Window functions** để phân tích xu hướng hoặc hành vi.
  - **TTL Index (`expireAfterSeconds`)** quản lý vòng đời và thời gian lưu trữ dữ liệu.
  - **Change Streams**, Atlas Search, Vector Search, Geospatial, event-driven processing.

### 4.2. Datadog
- **Bắt buộc:**
  - Tối thiểu **1 Dashboard** thể hiện tín hiệu vận hành và sức khỏe hệ thống.
  - Tối thiểu **1 Monitor hoặc Alert** gắn với lỗi, suy giảm hoặc rủi ro vận hành có ý nghĩa.
  - Tối thiểu **1 năng lực bổ sung:** Log Management, APM, Distributed Tracing, RUM, Anomaly Detection, hoặc Agent Observability.
  - **Kết nối (correlate):** Metrics, logs, traces và operational context để phục vụ điều tra/xử lý.
- **Khuyến khích:**
  - AI Observability & Agent Observability.

---

## 5. Danh mục hồ sơ nộp bài (12 mục checklist)

Hạn chót: **23:59 ngày 31/10/2026**

1. Tên dự án và mô tả bài toán
2. Thông tin đội và đầu mối liên hệ (Team Leader)
3. Kiến trúc giải pháp và ứng dụng (System Architecture)
4. Kiến trúc dữ liệu và Data Model trên MongoDB
5. Kiến trúc Observability trên Datadog
6. Link Repository mã nguồn và hướng dẫn cài đặt *(Public hoặc Private cấp quyền cho giám khảo đến hết 22/11/2026; chấm theo commit cuối trước deadline)*
7. **README:** Yêu cầu môi trường, cách triển khai, cấu hình, các bước kiểm thử
8. Bản MVP chạy được hoặc link demo truy cập được
9. Video demo kịch bản vận hành
10. Slide thuyết trình chung kết
11. Bản mô tả kịch bản sự cố vận hành được trình diễn (Incident Scenario)
12. Bản khai báo thành phần tái sử dụng, dataset bên ngoài và công cụ AI đã dùng

---

## 6. Tiêu chí chấm điểm (Judging Rubric)

| Tiêu chí | Trọng số | Nội dung đánh giá |
| :--- | :---: | :--- |
| **Sáng tạo (Creativity)** | **30%** | Tính độc đáo của ý tưởng, cách tiếp cận bài toán và cách ứng dụng MongoDB / Datadog. |
| **Kỹ thuật (Technical)** | **30%** | Kiến trúc hệ thống, chất lượng triển khai MongoDB (data model, aggregation) và độ sâu Observability trên Datadog. |
| **Tác động (Impact)** | **30%** | Giá trị vận hành / kinh doanh thực tế; kịch bản Phát hiện – Điều tra – Phục hồi trọn vẹn, thuyết phục. |
| **Trình bày (Presentation)**| **10%** | Chất lượng MVP, tài liệu (README/Docs), video demo và bài thuyết trình chung kết. |

---

## 7. Quy định & Thể lệ bắt buộc

- **Tính nguyên bản:** Được sử dụng thư viện/template mã nguồn mở và code sẵn có, nhưng **phải khai báo**. Phần giải pháp cốt lõi phải được xây dựng trong giai đoạn build (**17/10 – 31/10/2026**).
- **Công cụ AI:** Cho phép dùng AI hỗ trợ lập trình (Cursor, Antigravity, Copilot,...) nhưng phải khai báo; đội thi phải nắm và giải thích được toàn bộ giải pháp.
- **Bảo mật & Dữ liệu:**
  - **TUYỆT ĐỐI KHÔNG** đưa dữ liệu thật của công ty, dữ liệu cá nhân, thông tin nhạy cảm (PII), dữ liệu y tế, tài chính mật lên hệ thống. Sử dụng **Synthetic Data** hoặc **Public Dataset**.
  - **TUYỆT ĐỐI KHÔNG** commit API Keys, secrets, credentials vào repo hay quay trong video demo.
- **Sở hữu trí tuệ:** Đội thi sở hữu 100% bản quyền dự án. MUGVN, MongoDB và Datadog có quyền quảng bá, trích dẫn cho hoạt động cộng đồng.
- **Ngôn ngữ:** Tiếng Việt hoặc Tiếng Anh.
