# 03 — Thiết Kế Cơ Sở Dữ Liệu MongoDB

Trong dự án Reflex, cơ sở dữ liệu MongoDB Atlas không chỉ đóng vai trò là nơi lưu trữ thông tin đơn thuần, mà còn là nền tảng xử lý dữ liệu và kích hoạt thời gian thực. Thiết kế cơ sở dữ liệu tuân thủ chặt chẽ các bài học từ hội thảo chuyên sâu của MongoDB (MongoDB Workshop).

---

## 1. Phân tầng dữ liệu theo "nhiệt độ" và cơ chế tự dọn dẹp (TTL)

Dữ liệu đo đạc (telemetry) sinh ra liên tục với số lượng rất lớn. Nếu lưu trữ tất cả vào một chỗ mãi mãi, cơ sở dữ liệu sẽ nhanh chóng bị phình to, làm chậm tốc độ truy vấn và tốn kém chi phí lưu trữ. Do đó, hệ thống chia dữ liệu thành 3 tầng nhiệt độ:

### Tầng dữ liệu Nóng (Hot Data — Dùng Time Series Collection)
- Đây là dữ liệu đo đạc chi tiết của từng request vừa mới diễn ra (độ trễ từng mili-giây, số lượng token, thông tin từng lần thử).
- Dữ liệu này cần ghi cực nhanh và được truy vấn liên tục trong vài giờ đầu để phục vụ việc phát hiện sự cố tức thì.
- **Thời gian sống tự động (TTL):** Thiết lập tự động xóa sau **14 ngày**. Sau 14 ngày, dữ liệu thô này không còn cần thiết cho việc xử lý sự cố trực tiếp nữa và sẽ được MongoDB tự động dọn dẹp để giải phóng dung lượng.

### Tầng dữ liệu Ấm (Warm Data — Dùng Standard Collection tổng hợp)
- Thay vì để mất hoàn toàn dữ liệu sau 14 ngày, hệ thống chạy các tiến trình tổng hợp định kỳ (Rollup) bằng lệnh `$merge` của MongoDB.
- Nó gộp các sự kiện thô thành các bản ghi tổng hợp theo từng phút (lưu trong collection `sli_1m`) và theo từng giờ (lưu trong collection `sli_1h`). Các bản ghi này chứa các thông tin tóm tắt như: tổng số request, số request lỗi, phân phối độ trễ P50, P90, P99.
- **Thời gian sống tự động (TTL):** Bảng tổng hợp theo phút được giữ trong **45 ngày**; bảng tổng hợp theo giờ được giữ trong **400 ngày** để phục vụ báo cáo xu hướng dài hạn.

### Tầng dữ liệu Tham khảo và Vận hành (Operational & Reference Data)
- Bao gồm danh mục cấu hình hệ thống (`targets`, `policies`), danh sách các sự cố đã từng xảy ra (`incidents`), lịch sử các hành động sửa chữa (`actions`) và dữ liệu đo đạc công khai trong quá khứ (`bench_ts`).
- Các dữ liệu này được lưu trữ trong các collection thông thường và không cài đặt thời gian tự động xóa vì cần lưu trữ vĩnh viễn làm tài liệu tham khảo và đào tạo.

---

## 2. Vì sao chia thành bốn Time Series Collection riêng biệt?

Một sai lầm rất phổ biến của nhiều người khi dùng MongoDB Time Series là gom tất cả mọi sự kiện vào chung một collection (ví dụ đặt tên là `telemetry`). Hội thảo của MongoDB chỉ ra rằng đây là cách làm sai, vì Time Series tối ưu hóa dung lượng dựa trên **tần suất xuất hiện của nguồn dữ liệu (granularity)** và **trường định danh ít thay đổi (metaField)**.

Do đó, Reflex tách thành 4 collection Time Series độc lập:

### Collection 1: `requests_ts` (Đo lường chất lượng người dùng nhận được)
- **Ý nghĩa:** Mỗi khi một khách hàng gửi request tới cổng Gateway và nhận được kết quả cuối cùng, một bản ghi sẽ được ghi vào đây.
- **Tần suất ghi (granularity):** Cài đặt ở mức giây (`seconds`).
- **Trường metadata (`meta`):** Chỉ chứa các nhãn ít thay đổi dùng để lọc, bao gồm tên nghiệp vụ (`route: order.extract`) và môi trường (`env: demo`). Nhờ vậy, MongoDB có thể gom nhóm các request của cùng một nghiệp vụ vào cùng một khối lưu trữ (bucket), giúp truy vấn cực nhanh khi cần kiểm tra xem nghiệp vụ đặt hàng đang hoạt động ra sao.

### Collection 2: `attempts_ts` (Đo lường chất lượng của từng nhà cung cấp)
- **Ý nghĩa:** Một request của khách hàng có thể phải gọi 2 lần (lần 1 gọi nhà cung cấp A bị lỗi, lần 2 gọi nhà cung cấp B thành công). Mỗi lần gọi nhà cung cấp cụ thể như vậy sẽ được ghi nhận một dòng vào `attempts_ts`.
- **Tần suất ghi (granularity):** Cài đặt ở mức giây (`seconds`).
- **Trường metadata (`meta`):** Chứa thông tin về nhà cung cấp cụ thể (`target: vendorA:large`). Bảng này phục vụ việc tính toán xem nhà cung cấp A đang cung cấp dịch vụ tốt hay xấu, độc lập hoàn toàn với việc người dùng cuối có bị ảnh hưởng hay không.

### Collection 3: `probes_ts` (Canary Probes thăm dò định kỳ)
- **Ý nghĩa:** Định kỳ mỗi 15 giây, hệ thống tự động gửi một câu lệnh kiểm tra mẫu (canary probe) tới từng nhà cung cấp theo hai đường: một đường đi qua Gateway và một đường gọi thẳng trực tiếp tới nhà cung cấp.
- **Tần suất ghi (granularity):** Cài đặt ở mức giây (`seconds`).
- **Mục đích:** Giúp so sánh kết quả để biết chính xác lỗi bắt nguồn từ nhà cung cấp bên ngoài hay do máy chủ Gateway nội bộ bị nghẽn.

### Collection 4: `bench_ts` (Dữ liệu lịch sử từ bộ dữ liệu công khai)
- **Ý nghĩa:** Chứa 60 ngày dữ liệu đo đạc thực tế từ bộ dữ liệu mã nguồn mở `llm-bench-data`.
- **Tần suất ghi (granularity):** Cài đặt ở mức giờ (`hours`), vì bộ dữ liệu gốc đo đạc với chu kỳ mỗi giờ một lần. Việc đặt đúng độ chi tiết ở mức `hours` giúp MongoDB nén dữ liệu tốt hơn gấp nhiều lần so với việc để mặc định.

---

## 3. Ba điểm kỹ thuật nâng cao gây ấn tượng với Ban Giám Khảo

### Điểm 1: Hiểu rõ giới hạn kỹ thuật của Time Series
- Trong tài liệu của MongoDB, tính năng Time Series **hoàn toàn không hỗ trợ** Change Streams, Triggers và Atlas Search.
- Nhiều đội thi không nắm được giới hạn này và thiết kế hệ thống cố gắng lắng nghe sự kiện trực tiếp từ bảng Time Series, dẫn đến việc ứng dụng bị lỗi khi chạy thực tế.
- Nhóm Reflex giải quyết bài toán này rất chuẩn mực: Các sự kiện thời gian thực cần kích hoạt hành động tức thì được đưa lên các collection thông thường (`policies`, `incidents`, `actions`), và Gateway chỉ bật Change Streams trên các collection thông thường này. Đây là điểm cộng rất lớn khi thuyết trình kỹ thuật.

### Điểm 2: Tìm kiếm vector cho hình dạng sự cố (Incident Memory Vector Search)
- Thay vì dùng mô hình AI để chuyển văn bản thành vector tốn kém và chậm chạp, Reflex tự tạo ra một vector toán học 64 chiều từ chính các biểu đồ đo đạc:
  - Lấy 16 điểm thời gian xung quanh thời điểm xảy ra lỗi (từ 12 phút trước đến 3 phút sau khi phát hiện).
  - Với mỗi điểm thời gian, ghi nhận 4 giá trị tỷ lệ: tỷ lệ lỗi mạng, tỷ lệ lỗi chất lượng nội dung, độ lệch thời gian phản hồi so với ngày thường và độ lệch thời gian sinh từ đầu tiên.
  - Ghép 4 giá trị này qua 16 mốc thời gian thành một mảng 64 con số đại diện cho "hình dạng đồ thị" của sự cố.
- Khi có sự cố mới, hệ thống dùng câu lệnh `$vectorSearch` với thuật toán khoảng cách Cosine trên MongoDB Atlas để tìm lại các sự cố trong quá khứ có hình dạng đồ thị tương tự nhất, giúp gợi ý ngay giải pháp đã từng thành công.

### Điểm 3: Chống trùng lặp sự cố bằng Partial Unique Index
- Khi một nhà cung cấp gặp sự cố, cả hệ thống cảnh báo của Datadog và bộ phận giám sát nội bộ Sentinel của chúng ta đều có thể phát hiện và cùng lúc gửi lệnh tạo hồ sơ sự cố.
- Nếu không xử lý khéo léo, hệ thống sẽ mở ra 2 hoặc 3 hồ sơ cho cùng một vụ việc, khiến nhiều tiến trình cùng nhảy vào xử lý đè lên nhau.
- Reflex sử dụng tính năng **Chỉ mục duy nhất một phần (Partial Unique Index)** của MongoDB trên trường `dedup_key` của collection `incidents`, với điều kiện lọc chỉ áp dụng cho các sự cố đang ở trạng thái "đang mở" hoặc "đang điều tra". Nhờ vậy, nếu có 10 nguồn cùng báo về một sự cố trong cùng một khoảng thời gian, MongoDB sẽ chỉ chấp nhận tạo duy nhất 1 bản ghi, các yêu cầu sau sẽ tự động bị bỏ qua an toàn.
