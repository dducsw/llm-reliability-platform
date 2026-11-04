# 06 — Chaos Engineering Cho Hệ Thống AI: Giả Lập Sự Cố "Silent Brownout" & Cơ Chế Chống Gian Lận Thực Chiến

## 1. NGHỊCH LÝ KHI KIỂM THỬ HỆ THỐNG AI TỰ CHỮA LÀNH

Khi xây dựng một nền tảng với tuyên bố: *"Hệ thống có khả năng tự động phát hiện và xử lý sự cố trong thời gian thực"*, câu hỏi đầu tiên mà bất kỳ giám khảo hay chuyên gia kiểm thử nào cũng sẽ đặt ra là:  
**"Lấy đâu ra sự cố thật để hệ thống chứng minh khả năng tự chữa lành ngay trước mắt chúng tôi?"**

Nếu chúng ta chỉ gọi API thật tới OpenAI hay Anthropic, có thể trong suốt buổi thuyết trình 15 phút, các nhà cung cấp này đều hoạt động ổn định. Khi đó, toàn bộ các tính năng thông minh của chúng ta — ngắt mạch, phát hiện cháy ngân sách lỗi, AI Cortex điều tra, và chuyển vùng dự phòng — sẽ hoàn toàn không có cơ hội được kích hoạt. Ngược lại, chúng ta cũng không thể yêu cầu OpenAI cố tình làm sập máy chủ của họ để phục vụ bài thuyết trình.

Để giải quyết bài toán này một cách khoa học và thuyết phục, chúng tôi xây dựng một hạ tầng **Chaos Engineering chuyên nghiệp**, kết hợp hài hòa giữa **bộ dữ liệu đo đạc thực tế trong 60 ngày** và **công cụ bơm lỗi có kiểm soát (Chaos Proxy)**.

## 2. BỘ DỮ LIỆU THỰC TẾ: `llm-bench-data` VÀ ĐƯỜNG CONG TẢI CƠ SỞ (BASELINE)

Để hệ thống không phải là một mô hình "ảo tưởng" trên dữ liệu bịa đặt, chúng tôi tích hợp bộ dữ liệu đo đạc mở uy tín từ cộng đồng:
- **Nguồn gốc:** Kho lưu trữ [Jwrede/llm-bench-data](https://github.com/Jwrede/llm-bench-data) (Giấy phép bản quyền công cộng CC0 1.0, phi lợi nhuận, hoàn toàn không chứa dữ liệu nhạy cảm PII).
- **Đặc điểm dữ liệu:** Tác giả đã duy trì một hệ thống máy chủ liên tục gửi câu lệnh thăm dò (probe) tới hàng loạt mô hình AI nổi tiếng (Claude 3.5, GPT-4o, Gemini 1.5, Llama 3) qua cổng OpenRouter đều đặn mỗi giờ một lần suốt nhiều tháng trời. Dữ liệu ghi nhận lại chính xác thời gian sinh từ đầu tiên (TTFT), tổng thời gian phản hồi (latency), số lượng token mỗi giây và trạng thái lỗi.
- **Ứng dụng trong Reflex:** Chúng tôi nạp 60 ngày dữ liệu này vào Time Series collection `bench_ts` trong MongoDB Atlas để:
  1. Xây dựng đường cong độ trễ cơ bản (Baseline Latency) theo từng khung giờ trong tuần (ví dụ: tối thứ Bảy mạng thường chậm hơn sáng thứ Ba do lượng truy cập toàn cầu tăng cao).
  2. Cung cấp các phân phối độ trễ thực tế cho máy chủ giả lập `mock-llm`, giúp các thử nghiệm giả lập sinh ra độ trễ y hệt như các nhà cung cấp thật ngoài đời.

## 3. ỨNG DỤNG KHÁCH SHOPMATE: MÔ PHỎNG HÀNH VI NGƯỜI DÙNG CHÂN THỰC

Một hiểu lầm rất dễ gặp khi mới tiếp cận dự án là nghĩ rằng "ShopMate" là một hệ thống cơ sở dữ liệu bán hàng. Thực chất, **ShopMate là một ứng dụng khách hàng giả định (Demo Client App)** được chúng tôi tạo ra để đóng vai trò là "bệnh nhân" cần được Gateway bảo vệ.

Công cụ `traffic-gen` đóng vai ShopMate, liên tục tạo ra các lượt truy cập giống như người dùng thật đang mua sắm trên một sàn thương mại điện tử:
- **Nhịp điệu tải ngày và đêm (Diurnal Curve):** Lưu lượng truy cập được mô phỏng theo hàm đồ thị hình sin kết hợp một chút biến thiên ngẫu nhiên (ban ngày đông khách, ban đêm vắng khách).
- **Bộ prompt tiếng Việt tự nhiên và sạch sẽ:** Toàn bộ câu lệnh gửi đi đều được sinh từ các mẫu câu bán hàng thực tế, không chứa thông tin nhạy cảm.

ShopMate mô phỏng 3 luồng nghiệp vụ AI cốt lõi:
1. **`order.extract` (Trích xuất đơn hàng):** Khách gửi tin nhắn tự do (ví dụ: *"Giao cho mình 2 hộp khẩu trang y tế màu xanh về số 10 Trần Hưng Đạo nhé, gọi trước khi giao"*). LLM phải trích xuất thông tin ra đúng định dạng JSON Schema. Đây là "chiến trường" chính để chúng tôi thử nghiệm phát hiện lỗi vỡ cấu trúc và đứt cụt câu trả lời.
2. **`chat.reply` (Trợ lý tư vấn sản phẩm):** Khách hỏi về tính năng sản phẩm hoặc chính sách bảo hành. LLM trả về câu trả lời dạng truyền luồng dữ liệu (streaming). Dùng để kiểm tra độ trễ TTFT và phát hiện luồng bị treo giữa chừng.
3. **`support.triage` (Phân loại khiếu nại):** Đọc nội dung khiếu nại để phân loại mức độ khẩn cấp và chuyển tiếp đến phòng ban phù hợp.

## 4. CHAOS PROXY: BỘ BƠM LỖI CÓ CHỦ ĐÍCH TRÊN ĐƯỜNG TRUYỀN

Để chủ động tạo ra các sự cố phục vụ cho việc chấm thi và kiểm thử độ bền, chúng tôi xây dựng thành phần **Chaos Proxy**. Thành phần này được đặt nằm ở giữa cổng Gateway và các nhà cung cấp mô hình (kể cả mô hình thật lẫn mô hình giả lập).

Khi một kịch bản thử nghiệm được kích hoạt, Chaos Proxy sẽ lắng nghe cấu hình từ MongoDB và bắt đầu "đầu độc" đường truyền một cách có kiểm soát:

![Kiến trúc Bơm lỗi của Chaos Proxy](images/chaos-injection-flow.svg)

- **Bơm lỗi cắt cụt (`truncate`):** Cố tình chỉ cho phép mô hình trả về 60% câu trả lời rồi cắt ngang dòng truyền, gắn nhãn kết thúc là do hết độ dài token (`finish_reason: length`). Đây là lỗi chính trong kịch bản *The Silent Brownout*.
- **Bơm lỗi vỡ cấu trúc (`corrupt_json`):** Cố tình xóa mất dấu ngoặc nhọn kết thúc `}` hoặc đổi một trường số thành chuỗi chữ, khiến cho parser của các ứng dụng đọc JSON phía sau bị crash.
- **Bơm lỗi quá tải (`rate_limit 429`):** Cố tình từ chối cuộc gọi và trả về mã HTTP 429 kèm tiêu đề `Retry-After: 2` để thử nghiệm cơ chế Retry Budget và bảo vệ khỏi hiện tượng Thundering Herd.
- **Bơm lỗi chậm mạng (`latency` & `ttft_shift`):** Cố tình làm trễ chữ đầu tiên thêm 3 đến 5 giây, tạo ra độ trễ đuôi (tail latency) rất lớn.
- **Bơm lỗi treo dòng truyền (`stall`):** Mô hình đang sinh được vài chữ thì đột nhiên dừng hẳn không gửi dữ liệu tiếp nữa, mô phỏng hiện tượng kết nối mạng bị đứt gãy giữa chừng.

## 5. TÍNH KHÁCH QUAN & CƠ CHẾ CHỐNG GIAN LẬN (ANTI-CHEAT DESIGN)

Một câu hỏi rất hay mà các giám khảo khó tính thường đặt ra là:  
*"Làm sao chúng tôi biết hệ thống của các bạn thực sự phát hiện ra lỗi nhờ quan sát thông minh, hay do các bạn tự gắn cờ thông báo ngầm từ máy bơm lỗi sang máy Gateway?"*

Chúng tôi giải quyết mối lo ngại này bằng một cơ chế thiết kế cực kỳ minh bạch và sòng phẳng:
1. **Cô lập thông tin hoàn toàn:** Khi Chaos Proxy cố tình làm hỏng một câu trả lời, nó có gắn một tiêu đề nội bộ là `x-chaos-fault: truncate` vào gói tin trả về.
2. **Gateway và Cortex hoàn toàn "mù" trước tiêu đề này:** Cổng Gateway và AI Agent Cortex được thiết kế không đọc tiêu đề này. Toàn bộ quá trình phát hiện lỗi của Gateway chỉ dựa trên việc chạy các hàm kiểm tra ngữ nghĩa nội dung thực tế (JSON có parse được không, câu văn có bị cụt không) và dựa trên việc phân tích các chỉ số vi phạm ngân sách lỗi trên Datadog.
3. **Tiêu đề chỉ dùng để chấm điểm đối chiếu:** Tiêu đề `x-chaos-fault` chỉ được ghi nhận lại trong dấu vết hệ thống (span tag) để sau khi kịch bản kết thúc, hệ thống đối chiếu và chấm điểm: *"Chaos Proxy đã bơm tổng cộng 100 lỗi, và Gateway đã tự phát hiện chính xác 100/100 lỗi đó mà không bỏ sót lỗi nào"*.

### Tính tái lập cao với Hạt giống ngẫu nhiên (Seed 42)
Toàn bộ kịch bản thử nghiệm được chạy bằng câu lệnh cố định hạt giống ngẫu nhiên:
```bash
task scenario -- silent-brownout
# Thực thi: reflex-sim run silent-brownout --seed 42
```
Nhờ cố định hạt giống số 42 (`--seed 42`), chuỗi thời gian xảy ra lỗi, các câu prompt được sinh ra và phản ứng tự chữa lành của hệ thống sẽ diễn ra **chính xác 100% giống nhau** trong mọi lần chạy. Điều này giúp chúng tôi tự tin quay video demo hoặc biểu diễn trực tiếp trước hội đồng giám khảo mà không sợ gặp sự cố bất ngờ do tính bất định của mô hình.
