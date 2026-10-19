# 04 — Kiến Trúc Giám Sát Datadog

Datadog là nền tảng giám sát công nghiệp (Observability) hàng đầu thế giới hiện nay. Trong dự án này, Datadog đóng vai trò là "đôi mắt và đôi tai" của hệ thống, giúp người vận hành quan sát toàn bộ những gì đang diễn ra từ mức độ chi tiết của từng dòng code cho đến bức tranh toàn cảnh về chất lượng dịch vụ.

---

## 1. Khái niệm cơ bản: Ba trụ cột của Observability và Chuẩn gắn nhãn (Unified Tagging)

Để hiểu cách Datadog hoạt động, chúng ta cần nắm rõ 3 loại dữ liệu giám sát chính:
- **Chỉ số (Metrics):** Là những con số biến đổi theo thời gian, ví dụ như: số lượng request mỗi giây, thời gian phản hồi trung bình (latency), tỷ lệ lỗi phần trăm. Metrics giúp ta vẽ ra các biểu đồ trực quan để nhìn thấy xu hướng tăng giảm.
- **Dấu vết phân tán (Distributed Traces / APM):** Mỗi khi khách hàng gửi một yêu cầu, yêu cầu đó phải đi qua rất nhiều chặng (từ máy khách ➔ qua Gateway ➔ qua bộ lọc kiểm tra ➔ gọi sang API OpenAI ➔ nhận kết quả). APM Trace ghi lại chính xác từng chặng đó mất bao nhiêu mili-giây, giúp ta biết ngay chặng nào đang bị nghẽn cổ chai.
- **Nhật ký (Logs):** Là những dòng chữ chi tiết ghi lại nội dung cụ thể khi có sự kiện diễn ra, ví dụ: "Request ID 123 bị nhà cung cấp A từ chối vì lý do quá tải hạn mức".

### Sức mạnh của Chuẩn gắn nhãn hợp nhất (Unified Tagging)
Nếu metrics, traces và logs nằm riêng rẽ, người kỹ sư sẽ mất rất nhiều thời gian để đối chiếu xem dòng log này thuộc về biểu đồ nào. Datadog giải quyết vấn đề này bằng cơ chế gắn nhãn (tags). Trong dự án Reflex, mọi dữ liệu gửi lên Datadog đều bắt buộc phải mang chung một bộ nhãn chuẩn:
- `env: demo`: Cho biết dữ liệu này thuộc môi trường demo của bài thi.
- `service: reflex-gateway`: Định danh mã nguồn thuộc dịch vụ cổng Gateway.
- `route: order.extract`: Cho biết request này đang phục vụ tính năng trích xuất đơn hàng.
- `target: vendorA:large`: Cho biết request này đang gọi tới mô hình cụ thể nào của nhà cung cấp nào.
- `incident_id: INC-2026-10-01`: Mã định danh sự cố. Nhờ có mã này, khi nhìn thấy một biểu đồ bị tụt trên Dashboard, người kỹ sư chỉ cần nhấp chuột một cái là Datadog sẽ tự động lọc ra toàn bộ các dòng log và trace của đúng sự cố đó.

---

## 2. Các tính năng giám sát nâng cao được triển khai

### A. Giám sát ngân sách lỗi theo chuẩn Google SRE (Multi-Window Multi-Burn-Rate)
Trong cách làm cũ, người ta thường đặt cảnh báo theo kiểu: "Nếu tỷ lệ lỗi vượt quá 5% thì hú còi báo động". Cách làm này có nhược điểm chí mạng là sinh ra rất nhiều cảnh báo ảo (false positive). Ví dụ: Có 1 request bị lỗi ngẫu nhiên trong lúc lưu lượng thấp cũng làm tỷ lệ lỗi vọt lên 10% trong vài giây, đánh thức kỹ sư dậy nửa đêm dù hệ thống không có vấn đề gì nghiêm trọng.

Dự án áp dụng phương pháp chuẩn mực của Google SRE:
- Hệ thống định nghĩa một mục tiêu chất lượng (SLO), ví dụ: 99% request phải thành công trong vòng 30 ngày. Khoảng 1% còn lại được gọi là **Ngân sách lỗi (Error Budget)**.
- Hệ thống theo dõi tốc độ "đốt" ngân sách lỗi này (Burn Rate) trên hai cửa sổ thời gian đồng thời:
  - Cửa sổ nhanh (ví dụ 5 phút): Phát hiện các cú sập mạng bất thình lình làm cháy sạch ngân sách lỗi trong chốc lát.
  - Cửa sổ chậm (ví dụ 30 phút): Đảm bảo rằng sự cố này kéo dài liên tục và thực sự nghiêm trọng, chứ không phải một cú giật mạng thoáng qua.
- Chỉ khi cả hai cửa sổ thời gian này đều đồng loạt báo động rằng ngân sách lỗi đang bị tiêu tốn với tốc độ nguy hiểm, Datadog mới kích hoạt chuông báo động để mở sự cố. Cách làm này triệt tiêu hoàn toàn các cảnh báo giả.

### B. Màn hình giám sát kết hợp (Composite Monitor) để phân biệt nguồn gốc lỗi
Một câu hỏi nhức nhối khi hệ thống AI bị lỗi là: "Do máy chủ Gateway của mình bị quá tải, hay do nhà cung cấp bên ngoài (OpenAI/Anthropic) bị hỏng?". Nếu chẩn đoán sai, chúng ta sẽ đưa ra hành động sai (ví dụ: khởi động lại máy chủ của mình trong khi lỗi nằm ở phía đối tác).

Reflex giải quyết bài toán này bằng tính năng **Composite Monitor** của Datadog:
- Điều kiện 1: Tỷ lệ lỗi trên các request của khách hàng đang tăng cao bất thường.
- Điều kiện 2: Kiểm tra kết quả từ đường thăm dò định kỳ (Canary Probe) gọi thẳng tới máy chủ của nhà cung cấp bên ngoài cũng thấy bị lỗi.
- Khi cả hai điều kiện này cùng thỏa mãn, Datadog sẽ tự động đưa ra kết luận: "Lỗi bắt nguồn từ phía nhà cung cấp bên ngoài (Provider-Side Regression)", đồng thời gửi thông tin chẩn đoán chính xác này cho AI Agent để Agent không mất công điều tra nhầm chỗ.

### C. Giám sát mô hình ngôn ngữ lớn (Datadog LLM Observability)
Dự án không chỉ dùng Datadog để giám sát các dòng code thông thường, mà còn ứng dụng giải pháp chuyên biệt mới nhất của Datadog dành riêng cho AI: **Datadog LLM Observability**.

Tính năng này được cài đặt trực tiếp vào AI Agent Cortex:
- Nó ghi lại toàn bộ "dòng suy nghĩ" của AI Agent thành một chuỗi các bước rõ ràng: Agent nhận được câu hỏi gì, Agent quyết định gọi công cụ nào để tra cứu cơ sở dữ liệu, kết quả tra cứu trả về là gì, và Agent mất bao nhiêu token để đưa ra kết luận cuối cùng.
- Nhờ có màn hình này, ban giám khảo có thể nhìn thấu hoàn toàn hoạt động bên trong của AI Agent, chứng minh rằng Agent thực sự tự suy luận dựa trên dữ liệu thật chứ không phải được lập trình sẵn bằng những câu trả lời giả lập.

---

## 3. Quản lý toàn bộ cấu hình giám sát bằng mã nguồn (Terraform)

Thay vì phải lên giao diện trang web của Datadog để bấm tay tạo từng biểu đồ hay cấu hình từng cái chuông báo động (vốn rất dễ sót và không thể sao chép sang môi trường khác), toàn bộ hệ sinh thái giám sát của Reflex được viết bằng công cụ **Terraform**:
- Toàn bộ 3 bảng điều khiển (Dashboard) lớn: Dashboard Vận hành chung, Dashboard Quản lý ngân sách lỗi SLO, và Dashboard Theo dõi AI Agent Cortex.
- Toàn bộ 11 bộ giám sát (Monitors) và các đường truyền Webhook tự động kết nối về máy chủ.
- Tất cả đều nằm trong thư mục `infra/terraform/`. Khi cần triển khai sang một tài khoản Datadog mới, nhóm chỉ cần chạy một câu lệnh duy nhất (`terraform apply`) là toàn bộ hệ thống giám sát đồ sộ sẽ tự động được dựng lên hoàn chỉnh trong vòng vài giây.
