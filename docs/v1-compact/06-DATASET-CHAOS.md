# 06 — Dữ Liệu & Giả Lập Sự Cố (Chaos Engineering)

Trong một cuộc thi công nghệ về chủ đề "Hệ thống tự phát hiện và tự xử lý sự cố", một câu hỏi then chốt được đặt ra là: **Lấy đâu ra sự cố để hệ thống chứng minh khả năng tự chữa lành trước ban giám khảo?**

Nếu chúng ta chỉ gọi API thật tới OpenAI hay Anthropic, có thể trong suốt buổi thuyết trình 15 phút, các nhà cung cấp này đều hoạt động hoàn hảo 100%. Khi đó, toàn bộ các tính năng thông minh của chúng ta (phát hiện lỗi, chuyển vùng dự phòng, AI điều tra) sẽ hoàn toàn không có cơ hội được kích hoạt để ban giám khảo nhìn thấy. Ngược lại, chúng ta cũng không thể yêu cầu OpenAI cố tình làm sập server của họ để chúng ta biểu diễn.

Chính vì vậy, dự án xây dựng một hệ thống giả lập sự cố chuyên nghiệp, kết hợp hài hòa giữa **dữ liệu lịch sử thực tế** và **công cụ bơm lỗi có kiểm soát**.

---

## 1. Dữ liệu thực tế: Bộ dữ liệu công khai `llm-bench-data`

Để hệ thống có những con số đo đạc mang tính thực tế chứ không phải hoàn toàn là dữ liệu bịa đặt, dự án sử dụng bộ dữ liệu mã nguồn mở uy tín:
- **Nguồn dữ liệu:** Kho lưu trữ [Jwrede/llm-bench-data](https://github.com/Jwrede/llm-bench-data) (phát hành theo giấy phép hoàn toàn miễn phí CC0 1.0, không có bản quyền và không chứa bất kỳ thông tin cá nhân PII nào).
- **Bản chất của dữ liệu:** Tác giả của bộ dữ liệu này đã lập trình một hệ thống máy chủ liên tục gửi câu lệnh kiểm tra (probe) tới hàng loạt mô hình AI nổi tiếng (Claude, GPT, Gemini, Llama) qua cổng OpenRouter đều đặn mỗi giờ một lần suốt nhiều tháng trời. Dữ liệu ghi nhận lại chính xác thời gian sinh từ đầu tiên (TTFT), tổng thời gian phản hồi (latency), số lượng token mỗi giây và trạng thái thành công hay thất bại.
- **Cách dự án sử dụng:** Hệ thống nạp 60 ngày dữ liệu này vào Time Series collection `bench_ts` trong MongoDB Atlas. Dữ liệu này được dùng để:
  - Tính toán mức độ trễ cơ bản (baseline) của từng mô hình vào từng khung giờ trong tuần (ví dụ: tối thứ Bảy mạng thường chậm hơn sáng thứ Ba).
  - Cung cấp các phân phối độ trễ chuẩn xác để cài đặt cho máy chủ giả lập `mock-llm`, giúp máy chủ giả lập sinh ra độ trễ y hệt như các nhà cung cấp thật ngoài đời.

---

## 2. Ứng dụng khách hàng ShopMate: Nguồn tạo ra các lượt gọi LLM

Một hiểu lầm rất dễ gặp khi mới tiếp cận dự án là nghĩ rằng "ShopMate" là một hệ thống cơ sở dữ liệu bán hàng thông thường. Thực chất, **ShopMate là một ứng dụng khách hàng giả định (Demo Client App)** được chúng ta tạo ra để đóng vai trò là "bệnh nhân" cần được Gateway bảo vệ.

Trong dự án, công cụ `traffic-gen` sẽ đóng vai ShopMate, liên tục tạo ra các lượt truy cập giống như người dùng thật đang mua sắm trên một trang thương mại điện tử:
- Lưu lượng truy cập được mô phỏng theo nhịp điệu ngày và đêm (ban ngày đông khách, ban đêm vắng khách theo đồ thị hình sin kết hợp một chút biến thiên ngẫu nhiên).
- Toàn bộ các câu lệnh (prompts) gửi đi đều là tiếng Việt tự nhiên, được sinh ra từ các mẫu câu bán hàng sạch sẽ, không chứa thông tin nhạy cảm.

ShopMate mô phỏng 3 tính năng ứng dụng AI phổ biến nhất hiện nay:
1. **Tính năng trích xuất đơn hàng (`order.extract`):** Khi khách hàng gửi một đoạn tin nhắn tự do (ví dụ: *"Lấy cho mình 2 hộp khẩu phòng màu xanh về số 10 đường Trần Hưng Đạo nhé, nhớ gọi trước"*), ShopMate gửi prompt này tới LLM và yêu cầu LLM phải trích xuất thông tin ra đúng định dạng JSON cấu trúc (danh sách món hàng, số lượng, địa chỉ giao hàng). Đây là tính năng cốt lõi để chúng ta thử nghiệm bài toán kiểm tra tính toàn vẹn của JSON Schema.
2. **Tính năng trợ lý mua sắm (`chat.reply`):** Khách hàng hỏi tư vấn về tính năng sản phẩm hoặc chính sách bảo hành. LLM sẽ trả về các câu trả lời tiếng Việt dạng truyền luồng dữ liệu liên tục (streaming). Tính năng này dùng để kiểm tra độ trễ khi sinh chữ đầu tiên và phát hiện trường hợp luồng bị nghẽn giữa chừng.
3. **Tính năng phân loại hỗ trợ (`support.triage`):** Đọc nội dung khiếu nại của khách để phân loại mức độ khẩn cấp và chuyển tới phòng ban xử lý phù hợp.

---

## 3. Công cụ bơm lỗi có chủ đích: Chaos Proxy

Để chủ động tạo ra các sự cố phục vụ cho việc chấm thi, dự án xây dựng một thành phần gọi là **Chaos Proxy (Máy chủ bơm lỗi hỗn loạn)**. Thành phần này được đặt nằm ở giữa cổng Gateway và các nhà cung cấp mô hình (kể cả mô hình thật lẫn mô hình giả lập).

Khi một kịch bản thử nghiệm được kích hoạt, Chaos Proxy sẽ lắng nghe cấu hình từ MongoDB và bắt đầu "đầu độc" đường truyền một cách có tính toán:
- **Bơm lỗi cắt cụt (`truncate`):** Cố tình chỉ cho phép mô hình trả về 60% câu trả lời rồi cắt ngang dòng truyền, gắn nhãn kết thúc là do hết độ dài token. Đây là lỗi chính trong kịch bản Silent Brownout.
- **Bơm lỗi vỡ cấu trúc (`corrupt_json`):** Cố tình xóa mất dấu ngoặc nhọn kết thúc của chuỗi JSON hoặc đổi một trường số thành chuỗi chữ, khiến cho các ứng dụng đọc JSON phía sau bị sập.
- **Bơm lỗi quá tải (`rate_limit 429`):** Cố tình từ chối cuộc gọi và trả về mã HTTP 429 kèm tiêu đề thông báo phải chờ 5 giây mới được gọi lại.
- **Bơm lỗi chậm mạng (`latency` và `ttft_shift`):** Cố tình làm trễ dòng chữ đầu tiên thêm 3 đến 5 giây, hoặc tạo ra độ trễ đuôi rất lớn ở một số request nhất định.
- **Bơm lỗi treo dòng truyền (`stall`):** Mô hình đang sinh được vài chữ thì đột nhiên dừng hẳn không gửi dữ liệu tiếp nữa, mô phỏng hiện tượng đường truyền mạng bị đứt gãy giữa chừng.
- **Bơm lỗi sập toàn bộ (`error 500 / 503`):** Trả thẳng về lỗi máy chủ nội bộ để mô phỏng sự cố nhà cung cấp bị sập nguồn hoàn toàn.

---

## 4. Cơ chế chống gian lận (Anti-Cheat) để bảo đảm tính khách quan

Một câu hỏi rất hay mà các giám khảo khó tính thường đặt ra là: *"Làm sao biết hệ thống của các bạn thực sự phát hiện ra lỗi nhờ quan sát thông minh, hay do các bạn tự gắn cờ thông báo ngầm từ máy bơm lỗi sang máy Gateway?"*

Reflex giải quyết mối lo ngại này bằng một cơ chế thiết kế cực kỳ minh bạch:
- Khi Chaos Proxy cố tình làm hỏng một câu trả lời, nó có gắn một tiêu đề nội bộ là `x-chaos-fault: truncate` vào gói tin trả về.
- **Tuy nhiên, cổng Gateway và AI Agent Cortex được lập trình tuyệt đối không đọc tiêu đề này.** Toàn bộ quá trình phát hiện lỗi của Gateway chỉ dựa trên việc chạy các hàm kiểm tra ngữ nghĩa nội dung thực tế (JSON có parse được không, câu văn có bị cụt không) và dựa trên việc phân tích các chỉ số vi phạm ngân sách lỗi trên Datadog.
- Tiêu đề `x-chaos-fault` chỉ được ghi nhận lại trong dấu vết hệ thống (span tag) để sau khi kịch bản kết thúc, hệ thống đối chiếu và chấm điểm: *"Chaos Proxy đã bơm tổng cộng 100 lỗi, và Gateway đã tự phát hiện chính xác 100/100 lỗi đó mà không bỏ sót lỗi nào"*.

Đặc biệt, toàn bộ kịch bản được chạy bằng câu lệnh cố định hạt giống ngẫu nhiên: `reflex-sim run silent-brownout --seed 42`. Nhờ cố định hạt giống số 42, chuỗi thời gian xảy ra lỗi và phản ứng tự chữa lành của hệ thống sẽ diễn ra **chính xác 100% giống nhau** trong mọi lần chạy, giúp nhóm tự tin quay video demo hoặc biểu diễn trực tiếp mà không sợ gặp sự cố bất ngờ.
