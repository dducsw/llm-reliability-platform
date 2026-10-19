# 07 — Phân Chia Công Việc & Kế Hoạch Triển Khai 2 Tuần

Một trong những nguyên nhân hàng đầu khiến các đội thi hackathon bị thất bại không phải do thiếu ý tưởng hay kỹ năng kém, mà là do **phân chia công việc không rõ ràng dẫn đến việc giẫm chân lên nhau, hoặc cố làm quá nhiều thứ cùng lúc để rồi đến hạn chót vẫn không có một sản phẩm chạy hoàn chỉnh để nộp**.

Kế hoạch dưới đây được thiết kế riêng cho **nhóm 2 người**, diễn ra trong giai đoạn từ ngày 17/10 đến 31/10/2026, tuân thủ nguyên tắc sống còn: **"Bất kỳ thời điểm nào cũng luôn có một bản sản phẩm chạy được để sẵn sàng nộp bài"**.

---

## 1. Phân chia vai trò rành mạch giữa hai thành viên

Hai thành viên được phân chia theo hai mặt phẳng độc lập đã thiết kế ở bài viết số 02, làm việc song song và giao tiếp với nhau qua các định dạng dữ liệu (contracts) đã được chốt trước:

### Thành viên A: Kỹ sư Hạ tầng, Mạng & Giám sát (Data Plane & Datadog)
- **Khu vực phụ trách:** Chịu trách nhiệm về luồng di chuyển của các request từ khi khách hàng gọi vào cho đến khi nhận được kết quả, đảm bảo độ trễ cực thấp và đo đạc đầy đủ lên Datadog.
- **Các nhiệm vụ cụ thể cần code:**
  - Xây dựng cổng Gateway bằng FastAPI (`apps/gateway`): nhận request chuẩn OpenAI, xử lý luồng streaming, kết nối các adapter gọi mô hình giả lập và mô hình thật.
  - Viết thư viện lõi `packages/reflex-core`: lập trình thuật toán chấm điểm chọn nhà cung cấp (Router), cơ chế ngắt mạch khi lỗi (Circuit Breaker) và các hàm kiểm tra chất lượng nội dung siêu tốc (Quality Validators).
  - Xây dựng công cụ giả lập và bơm lỗi (`apps/simulation`): lập trình công cụ sinh tải ShopMate và công cụ bơm lỗi có chủ đích Chaos Proxy.
  - Thiết lập hệ thống giám sát Datadog bằng mã nguồn Terraform (`infra/terraform`): cấu hình toàn bộ các chỉ số đo đạc, các biểu đồ trên Dashboard và 11 bộ cảnh báo Monitors theo chuẩn Google SRE.

### Thành viên B: Kỹ sư Dữ liệu, Trí tuệ Nhân tạo & Giao diện (Control Plane, MongoDB & AI)
- **Khu vực phụ trách:** Chịu trách nhiệm về "bộ não" phân tích dữ liệu ở phía sau, quản lý cơ sở dữ liệu MongoDB Atlas, xây dựng AI Agent điều tra sự cố và giao diện bảng điều khiển cho người vận hành.
- **Các nhiệm vụ cụ thể cần code:**
  - Thiết kế và quản lý cơ sở dữ liệu MongoDB (`packages/reflex-mongo`): viết các tệp di chuyển dữ liệu (migrations) để tạo 4 Time Series collections, cấu hình chỉ mục tự xóa TTL và viết 16 câu lệnh tổng hợp nâng cao (Aggregation Pipelines).
  - Xây dựng bộ phận gác cổng Sentinel (`apps/control-plane`): tính toán tốc độ tiêu tốn ngân sách lỗi theo từng phút và mở hồ sơ sự cố khi có vi phạm.
  - Xây dựng AI Agent Cortex (`apps/cortex`): lập trình quy trình điều tra nguyên nhân gốc rễ, tích hợp tính năng tìm kiếm sự cố tương tự bằng Vector Search và viết bộ phận kiểm định thống kê toán học (Recovery Proof).
  - Xây dựng giao diện bảng điều khiển Console (`apps/console`): làm giao diện web trực quan để hiển thị biểu đồ so sánh giữa chất lượng nhà cung cấp và chất lượng người dùng nhận được, kèm nút bấm duyệt hành động can thiệp.

---

## 2. Lộ trình ba mốc kiểm soát chất lượng (The Three Gates)

Để tránh rủi ro "cháy giờ" sát ngày nộp bài, toàn bộ 2 tuần thi được chia thành 3 mốc kiểm soát nghiêm ngặt. Mỗi khi vượt qua một mốc, nhóm đều tạo ra một phiên bản sản phẩm hoàn chỉnh có thể nộp được ngay lập tức:

### 🟢 Mốc 1: Gate G1 — Đạt chuẩn hợp lệ thể lệ (Hoàn thành trước ngày 23/10)
- **Mục tiêu:** Đáp ứng đầy đủ 100% các tiêu chí bắt buộc của ban tổ chức cuộc thi. Sau mốc này, bài thi chắc chắn hợp lệ và không bị loại.
- **Các hạng mục phải chạy được:**
  - Khung dự án chung (Monorepo `uv`, Docker Compose chứa MongoDB Atlas local và Datadog Agent) khởi động trơn tru bằng một câu lệnh `task up`.
  - Cổng Gateway nhận được request từ ShopMate, chuyển tiếp tới máy chủ giả lập và ghi nhận dữ liệu đo đạc thành công vào các bảng Time Series trong MongoDB.
  - Datadog ghi nhận được đầy đủ các chỉ số độ trễ, lưu vết APM và các dòng nhật ký.
  - Khi có sự cố xảy ra, người vận hành có thể gọi một lệnh API thủ công để chuyển hướng lưu lượng sang nhà cung cấp khác và nhìn thấy biểu đồ trên Datadog xanh trở lại.
- **Hành động bảo hiểm bắt buộc:** Ngay khi hoàn thành mốc G1, nhóm **quay ngay một video demo dự phòng dài 3 phút**. Kể cả trong trường hợp xấu nhất những ngày sau nhóm gặp trục trặc kỹ thuật, nhóm vẫn có sẵn video và mã nguồn hợp lệ này để nộp bài.

### 🟢 Mốc 2: Gate G2 — Khác biệt hóa & Sáng tạo đỉnh cao (Hoàn thành trước ngày 28/10)
- **Mục tiêu:** Hiện thực hóa toàn bộ các tính năng sáng tạo độc đáo để giành trọn 30% điểm Sáng tạo và 30% điểm Kỹ thuật của ban giám khảo.
- **Các hạng mục phải chạy được:**
  - Kịch bản sự cố chính **Silent Brownout (S1)** chạy tự động hoàn hảo từ đầu đến cuối:
    - Máy bơm lỗi làm hỏng định dạng JSON và cắt cụt câu trả lời.
    - Gateway lập tức phát hiện thông qua Quality SLI và tự động gọi mô hình dự phòng.
    - AI Agent Cortex tự động mở phiên điều tra, dùng tính năng Vector Search trên MongoDB để tìm lại kinh nghiệm xử lý trong quá khứ và đề xuất đổi chính sách điều phối.
    - Bộ phận Verifier thực hiện phép kiểm định toán học thống kê chứng minh hệ thống đã hồi phục trước khi chính thức đóng sự cố.
  - Giao diện web Console hiển thị mượt mà biểu đồ kép: chứng minh chất lượng nhà cung cấp tụt xuống 61% nhưng chất lượng người dùng vẫn giữ vững ở mức 99.6%.
- **Hành động:** Quay video demo chính thức phiên bản 2, ghi nhận lại toàn bộ dòng chảy tự chữa lành tự động của hệ thống.

### 🟢 Mốc 3: Gate G3 — Đóng gói hồ sơ & Trình diễn (Từ ngày 29/10 đến 31/10)
- **Mục tiêu:** Đảm bảo hồ sơ nộp bài chỉn chu, chuyên nghiệp như một sản phẩm thương mại thực thụ.
- **Các hạng mục hoàn thiện:**
  - Hoàn thiện tính năng Cỗ máy thời gian (Time Machine) để xuất ra bảng đối chứng tiết kiệm chi phí và ngân sách lỗi.
  - Chạy thử nghiệm ngâm tải liên tục trong 24 giờ (soak test) với một nhà cung cấp thật (OpenAI) để các biểu đồ trên Datadog có lịch sử số liệu thực tế đẹp mắt.
  - Rà soát toàn bộ mã nguồn bằng công cụ quét bảo mật `gitleaks` để đảm bảo 100% không có mã khóa bí mật (API Keys) hay thông tin cá nhân nào bị lộ lên GitHub.
  - Soạn thảo tài liệu hướng dẫn khởi động nhanh (README.md) thật rõ ràng để ban giám khảo có thể tự chạy thử dự án trên máy của họ chỉ bằng 2 câu lệnh.
  - Cấp quyền truy cập vào cụm cơ sở dữ liệu MongoDB Atlas và tài khoản Datadog cho ban giám khảo đến hết thời hạn chấm thi.

---

## 3. Lời khuyên vàng cho nhóm 2 người trong 2 tuần thi

1. **Tuyệt đối không thay đổi cấu trúc dữ liệu tùy tiện:** Vào ngày đầu tiên, hai thành viên phải ngồi lại cùng nhau và chốt cứng định dạng của 3 cấu trúc dữ liệu: bản ghi đo đạc `RequestEvent`, bản ghi cấu hình `Policy` và bản ghi hành động `ActionSpec` trong thư viện `reflex-core`. Một khi đã chốt, cả hai người cứ thế tự tin code phần việc của mình mà không sợ bị xung đột.
2. **Ưu tiên code chạy được hơn là code hoàn hảo:** Đừng mất quá nhiều ngày để tối ưu hóa một dòng code chạy nhanh hơn vài micro-giây. Hãy tập trung làm cho toàn bộ vòng tròn khép kín (Phát hiện ➔ Điều tra ➔ Tự chữa lành ➔ Chứng minh) chạy thông suốt từ đầu đến cuối trước, sau đó mới quay lại làm đẹp code nếu còn thời gian.
3. **Luôn giữ tinh thần kiểm tra chéo:** Thành viên A sau khi viết xong kịch bản bơm lỗi thì bàn giao cho thành viên B dùng thử; thành viên B sau khi viết xong giao diện web thì nhờ thành viên A kiểm tra tính tiện dụng. Sự phối hợp ăn ý và tinh thần kỷ luật theo các mốc Gate chính là chìa khóa chắc chắn nhất để đưa nhóm đến chiến thắng.
