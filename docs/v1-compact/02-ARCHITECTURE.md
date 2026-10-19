# 02 — Kiến Trúc Hệ Thống & Lựa Chọn Công Nghệ

## 1. Khái niệm cơ bản: Phân tách Data Plane và Control Plane

Để hệ thống vừa phản hồi nhanh vừa có khả năng phân tích thông minh, kiến trúc được chia làm hai phần tách biệt: **Data Plane (Mặt phẳng dữ liệu)** và **Control Plane (Mặt phẳng điều khiển)**.

Có thể hình dung hai phần này giống như hệ thống giao thông đường bộ:
- **Data Plane giống như các làn xe trên đường cao tốc:** Xe cộ (các request của người dùng) phải lưu thông liên tục với tốc độ cao nhất có thể. Không thể đặt một trạm dừng phức tạp hay bắt xe phải chờ cảnh sát giao thông suy nghĩ tại từng ngã tư.
- **Control Plane giống như trung tâm điều hành giao thông:** Nằm ở trụ sở riêng, quan sát toàn bộ camera từ xa. Khi thấy một đoạn đường bị ùn tắc hoặc gặp tai nạn, trung tâm sẽ bấm nút đổi tín hiệu đèn giao thông hoặc mở lối thoát hiểm để các xe phía sau tự động chuyển hướng.

### Chi tiết về Data Plane (Cổng Gateway — thư mục `apps/gateway`)
- Đây là ứng dụng tiếp xúc trực tiếp với người dùng và các hệ thống bên ngoài thông qua chuẩn giao thức quen thuộc của OpenAI (`POST /v1/chat/completions`).
- Khi nhận được request, Gateway thực hiện các bước sau theo thứ tự:
  - **Chấm điểm và định tuyến (Routing & Scoring):** Dựa vào bảng cấu hình trong bộ nhớ, Gateway chấm điểm các nhà cung cấp khả dụng (dựa trên độ trễ trung bình, chi phí và tỷ lệ lỗi gần nhất) để chọn ra nhà cung cấp tốt nhất.
  - **Thực hiện cuộc gọi:** Gửi request đến nhà cung cấp đã chọn (OpenAI, Anthropic hoặc cụm máy chủ giả lập).
  - **Kiểm tra chất lượng tức thì (Quality Validators):** Ngay khi dữ liệu trả về, một hàm kiểm tra siêu tốc (< 2 mili-giây) sẽ đọc nội dung: kiểm tra xem JSON có hợp lệ không, câu trả lời có bị cụt hay rỗng không.
  - **Kích hoạt phản xạ bảo vệ (Circuit Breaker & Retry):** Nếu phát hiện lỗi hoặc chất lượng hỏng, Gateway lập tức gọi sang nhà cung cấp dự phòng điểm cao tiếp theo, đảm bảo khách hàng không nhận về lỗi.
  - **Đẩy dữ liệu đo đạc bất đồng bộ (Telemetry Queue):** Toàn bộ thông tin về độ trễ, số lượng token, trạng thái lỗi được ném vào một hàng đợi trong bộ nhớ RAM và được một luồng nền ghi theo lô (batch insert) vào MongoDB và Datadog. Nhờ xử lý bất đồng bộ, việc ghi dữ liệu này không làm chậm bất kỳ mili-giây nào của khách hàng.

### Chi tiết về Control Plane (Bộ não điều hành — thư mục `apps/control-plane` và `apps/cortex`)
- Chạy hoàn toàn độc lập ở phía sau, không nằm trên đường đi trực tiếp của request.
- Các thành phần chính bao gồm:
  - **Thành phần Sentinel (Người gác cổng):** Liên tục tổng hợp dữ liệu đo đạc theo từng phút để tính toán xem hệ thống đang tiêu tốn ngân sách lỗi (Error Budget) nhanh hay chậm. Nếu phát hiện tốc độ tiêu tốn vượt ngưỡng an toàn, Sentinel sẽ mở một hồ sơ sự cố (Incident).
  - **AI Agent Cortex (Điều tra viên thông minh):** Tự động đọc dữ liệu chi tiết từ Datadog và MongoDB, tra cứu các sự cố tương tự trong quá khứ để tìm nguyên nhân gốc rễ và đề xuất phương án giải quyết (ví dụ: chuyển bớt tải khỏi mô hình đang lỗi).
  - **Thành phần Actuator (Bộ phận thực thi):** Kiểm tra xem đề xuất của AI Agent có an toàn không (có vượt trần chi phí không, có làm quá tải mô hình đích không). Nếu an toàn, Actuator sẽ ghi chính sách mới vào cơ sở dữ liệu MongoDB.
  - **Thành phần Verifier (Bộ phận thẩm định):** Sau khi chính sách mới được áp dụng, Verifier sẽ theo dõi số liệu trong 3 đến 5 phút tiếp theo và dùng các công thức toán học thống kê để kiểm tra xem hệ thống đã thực sự hồi phục chưa. Nếu chưa hồi phục, nó sẽ tự động hoàn tác (rollback) về trạng thái cũ.

---

## 2. Vì sao dự án quyết định chọn Python mà không dùng Go?

Trong các hệ thống Gateway truyền thống, nhiều người thường nghĩ ngay đến ngôn ngữ Go vì khả năng xử lý mạng cực nhanh. Tuy nhiên, đối với bài toán cụ thể của cuộc thi này, việc chọn **Python 3.12 Monorepo (quản lý bằng công cụ `uv`)** là quyết định tối ưu nhất vì những lý do sau:

### Lý do 1: Hỗ trợ trọn vẹn cho Datadog LLM Observability
- Cuộc thi chấm điểm rất cao việc ứng dụng các tính năng hiện đại của Datadog, đặc biệt là tính năng quan sát mô hình ngôn ngữ lớn (LLM Observability).
- Thư viện chính thức của Datadog (`ddtrace.llmobs`) hỗ trợ đầy đủ và mạnh mẽ nhất trên Python. Nó cho phép theo dõi chi tiết từng bước suy luận, từng lần gọi công cụ (tool call) của AI Agent. Trên ngôn ngữ Go, tính năng này của Datadog còn rất hạn chế.

### Lý do 2: Tránh trùng lặp code cho nhóm 2 người
- Dự án có rất nhiều cấu trúc dữ liệu chung: định dạng cấu hình chính sách (Policy), định dạng sự kiện đo đạc (RequestEvent), định dạng hành động sửa lỗi (ActionSpec).
- Khi dùng Python, nhóm viết toàn bộ các định dạng này một lần duy nhất trong thư viện dùng chung `packages/reflex-core` bằng thư viện Pydantic v2. Cả cổng Gateway, AI Agent Cortex và công cụ mô phỏng Time Machine đều import chung thư viện này để dùng.
- Nếu dùng Go cho Gateway và Python cho AI, nhóm sẽ phải định nghĩa và bảo trì hai bộ cấu trúc dữ liệu giống hệt nhau ở hai ngôn ngữ khác nhau, rất dễ phát sinh lỗi lệch pha khi thay đổi cấu trúc dữ liệu.

### Lý do 3: Tải thực tế của bài thi không đòi hỏi Go
- Mức tải thử nghiệm và trình diễn của bài thi chỉ dao động từ 8 đến 50 request mỗi giây (rps).
- Framework FastAPI kết hợp với máy chủ Uvicorn bất đồng bộ (asyncio) trong Python có thể xử lý mượt mà hàng trăm đến hàng nghìn request mỗi giây. Độ trễ cộng thêm của Gateway bằng Python chỉ dưới 3 mili-giây, hoàn toàn đáp ứng xuất sắc yêu cầu mà không cần sự phức tạp của Go.

### Lý do 4: Tận dụng hệ sinh thái AI và toán học phong phú
- Tầng điều khiển cần viết AI Agent gọi công cụ và cần thực hiện các phép kiểm định thống kê toán học (Two-proportion z-test, khoảng tin cậy Wilson).
- Trong Python, những việc này chỉ tốn vài dòng code nhờ các thư viện có sẵn như `scipy.stats` và bộ SDK chính thức của OpenAI/Anthropic. Nếu làm bằng Go, nhóm sẽ phải tự viết lại các thuật toán thống kê từ đầu, tốn rất nhiều thời gian quý báu của 2 tuần thi.

---

## 3. Cơ chế cập nhật chính sách không gián đoạn (Hot-Reload)

Một yêu cầu bắt buộc của các hệ thống có độ tin cậy cao là: Khi thay đổi luật điều phối (ví dụ: chuyển 80% lưu lượng sang nhà cung cấp khác), hệ thống **tuyệt đối không được khởi động lại (restart)** làm rớt các kết nối đang chạy của khách hàng.

Reflex thực hiện điều này một cách tự nhiên nhờ tính năng Change Streams của MongoDB:
1. Khi Control Plane quyết định thay đổi chính sách, nó sẽ ghi một bản ghi cấu hình mới kèm số phiên bản (version) tăng dần vào collection `policies` trong MongoDB.
2. Tại cổng Gateway, có một tiến trình nền chạy liên tục để lắng nghe các thay đổi trên collection `policies` thông qua MongoDB Change Streams.
3. Ngay khi có bản ghi mới được ghi nhận trong cơ sở dữ liệu, Gateway sẽ nhận được sự kiện ngay lập tức, kiểm tra tính hợp lệ của cấu hình và nạp đè lên bảng định tuyến đang nằm trong bộ nhớ RAM.
4. Toàn bộ quá trình từ lúc ghi cấu hình mới trên Control Plane đến khi Gateway áp dụng diễn ra trong thời gian **dưới 1 giây** mà không làm gián đoạn bất kỳ request nào của khách hàng.
