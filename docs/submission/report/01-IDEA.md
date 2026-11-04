# 01 — Bối Cảnh, Mục Tiêu & Giải Pháp: Giám Sát và Xử Lý Lỗi Nội Dung Trong Ứng Dụng AI

## 1. BỐI CẢNH: KHOẢNG MÙ TRONG VẬN HÀNH GenAI THỜI GIAN THỰC

### 1.1. Khi LLM bước vào luồng dữ liệu nghiệp vụ nhịp độ cao
Nếu như năm 2023, Generative AI đa phần dừng lại ở mức "chatbot hỏi đáp giải trí" — nơi người dùng sẵn sàng chờ 5–10 giây cho một câu trả lời — thì bước sang 2025–2026, các mô hình ngôn ngữ lớn (LLM) đã trở thành một mắt xích xử lý trực tiếp trong luồng nghiệp vụ lõi (mission-critical path):
- **Trích xuất đơn hàng thương mại điện tử:** Khách gửi tin nhắn tự do trên app; LLM phải parse tức thì thành JSON cấu trúc chuẩn để hệ thống kho trừ tồn kho và cổng thanh toán lock tiền.
- **Trợ lý giao dịch tài chính & CSKH:** Tương tác thời gian thực qua luồng stream tokens; độ trễ sinh từ đầu tiên (TTFT) phải được giữ ổn định ở mức mili-giây.

Trong môi trường này, **tính sẵn sàng thời gian thực (Real-time Availability)** không còn là một khái niệm trừu tượng, mà đo đếm trực tiếp bằng doanh thu và trải nghiệm người dùng trên từng giây.

### 1.2. Nỗi đau thực tế: "The Silent Brownout" — Lỗi im lặng
Khi vận hành cụm Gateway kết nối các nhà cung cấp như OpenAI, Anthropic hay các cụm vLLM tự host, chúng tôi nhận ra một sự thật: **Những sự cố khó phát hiện nhất của LLM không bao giờ làm sập máy chủ.**

Trong các hệ thống phân tán truyền thống, khi dịch vụ backend quá tải hoặc database deadlock, chúng ta nhận về HTTP 500, 502 hoặc 504. Các công cụ giám sát (APM, Prometheus, Datadog) sẽ ngay lập tức chuyển sang màu đỏ rực và kích hoạt chuông báo PagerDuty.

Nhưng trong thế giới LLM, hơn **90% sự cố nghiêm trọng diễn ra trong sự im lặng**:
1. **Mã HTTP vẫn trả về 200 OK:** Về mặt kết nối mạng và proxy, request hoàn toàn thành công.
2. **Độ trễ (Latency) vẫn nằm trong ngưỡng an toàn:** Biểu đồ P95/P99 trên màn hình giám sát vẫn là một đường màu xanh êm ả.
3. **Nhưng nội dung câu trả lời bên trong bị phá hủy hoàn toàn:**
   - **Đứt cụt giữa chừng (Early Truncation):** Luồng stream đang chạy được 60% thì dừng đột ngột do lỗi buffer của nhà cung cấp hoặc server-side max tokens regression.
   - **Vỡ cấu trúc (Corrupt JSON Schema):** Dữ liệu trả về thiếu dấu đóng ngoặc nhọn `}`, sai định dạng kiểu số sang chuỗi, khiến parser của các microservices tiếp theo crash ngay lập tức (`SyntaxError: Unexpected end of JSON input`).
   - **Từ chối ngầm (Silent Refusal):** Mô hình bất chợt trả về chuỗi rỗng `""` hoặc một câu thông báo từ chối máy móc mà không hề có mã lỗi.

**Nghịch lý vận hành:** Dashboard của đội SRE hiển thị 100% Uptime, lãnh đạo nhìn báo cáo thấy hệ thống "xanh mượt", nhưng người dùng thực tế đang nhận về toàn dữ liệu rác, hàng loạt đơn hàng bị treo và khách hàng rời bỏ dịch vụ. Chúng tôi gọi đây là hiện tượng **Silent Brownout (Sự cố suy giảm ngấm ngầm)**.

## 2. MỤC TIÊU KỸ THUẬT: ĐƯA REAL-TIME MONITORING VÀO TỪNG TOKEN

Để giải quyết bài toán cốt lõi của đề tài **Real-time Operations**, chúng tôi không thể tiếp tục dùng cách đo lường "thô" của hạ tầng mạng cũ. Hệ thống phải đạt được 4 mục tiêu thiết kế khắt khe:

1. **Giám sát thời gian thực ở cấp độ ngữ nghĩa (In-Flight Semantic Monitoring):**
   - Đánh giá chất lượng của từng response ngay trên đường bay của dữ liệu (in-flight validation) mà không làm tăng độ trễ của khách hàng. Mức overhead trễ cho phép tối đa của Gateway chỉ được dao động từ **1–3 mili-giây**.
2. **Cảnh báo sớm theo tốc độ đốt ngân sách lỗi (Multi-Window Multi-Burn-Rate):**
   - Không dùng ngưỡng tĩnh lạc hậu (ví dụ: "lỗi > 5% thì hú còi" — cách này sinh ra vô số cảnh báo giả). Phải đo lường tốc độ tiêu hao ngân sách lỗi (Error Budget Burn Rate) theo thời gian thực trên cả hai cửa sổ ngắn và dài theo đúng chuẩn Google SRE. Phát hiện sự cố chất lượng trong vòng **30–90 giây** đầu tiên.
3. **Vòng lặp tự chữa lành khép kín theo thời gian thực (Zero-Human-Delay Closed-Loop SRE):**
   - Khoảng thời gian từ lúc phát hiện suy giảm, khoanh vùng rủi ro, AI điều tra nguyên nhân gốc rễ, cho đến khi nạp chính sách điều phối mới xuống toàn bộ cụm Gateway phải diễn ra **dưới 1 giây** qua cơ chế đẩy dữ liệu thời gian thực của MongoDB Change Streams.
4. **Lượng hóa giá trị kinh tế minh bạch (Quantifiable Business Impact):**
   - Tách biệt rạch ròi chất lượng nhà cung cấp thô (Provider SLO) và chất lượng thực tế bàn giao (Delivered SLO). Cung cấp khả năng "tua lại thời gian" (Counterfactual Replay) để chứng minh giải pháp tự động cứu được bao nhiêu phần trăm đơn hàng trước ban giám khảo.

## 3. GIẢI PHÁP: CUNG PHẢN XẠ HAI TỐC ĐỘ (THE TWO-SPEED LOOP)

### 3.1. Cảm hứng sinh học: Tủy sống và Não bộ
Khi thiết kế kiến trúc cho **Reflex**, chúng tôi tìm về một cơ chế tự bảo vệ tự nhiên: hệ thần kinh con người.

Khi bạn vô tình chạm tay vào một thanh kim loại nóng bỏng:
- **Tủy sống** không hề chờ tín hiệu truyền lên tận vỏ não để suy nghĩ xem thanh kim loại đó là gì. Nó kích hoạt ngay một **cung phản xạ tức thời (Fast Reflex)**, giật tay bạn lại trong vài phần nghìn giây để cứu các mô tế bào khỏi bị bỏng nặng.
- Ngay sau đó, **não bộ (Slow Cortex)** mới tiếp nhận cơn đau, phân tích nguyên nhân vì sao thanh kim loại đó nóng, tra cứu kinh nghiệm quá khứ, và ra lệnh dán biển cảnh báo hoặc tắt nguồn nhiệt để bảo vệ bạn trong tương lai.

Áp dụng chính xác triết lý này, Reflex phân tách thành hai vòng lặp vận hành khép kín:

![Kiến trúc Cung phản xạ hai tốc độ Reflex](images/two-speed-loop.svg)

### 3.2. Vòng lặp phản xạ nhanh: Reflex Data Plane (< 2ms)
Nằm trực tiếp trên đường truyền của các request tại Gateway. Nó được thiết kế với tiêu chí: **Đơn giản, cực nhanh và không bao giờ nghẽn**.
- Khi một câu trả lời từ upstream LLM trả về, nó đi qua bộ kiểm định chất lượng siêu nhẹ (`fastjsonschema` + length checks) với chi phí chưa đầy 1.5ms.
- Nếu phát hiện JSON vỡ hoặc câu trả lời bị đứt cụt, Circuit Breaker lập tức kích hoạt cơ chế **Quality-Aware Retry**, chuyển hướng gọi sang một mô hình dự phòng lành lặn đã được chấm điểm sẵn trong bộ nhớ RAM.
- Toàn bộ dữ liệu đo đạc (telemetry) được ném vào hàng đợi RAM bất đồng bộ để luồng nền ghi theo lô vào MongoDB Atlas và Datadog, hoàn toàn không cản trở dù chỉ 1 mili-giây của khách hàng.

### 3.3. Vòng lặp suy luận chậm: Cortex Control Plane (Giây đến Phút)
Là một AI SRE Agent tự hành chạy nền (background service, out-of-band), chỉ kích hoạt khi nhận được cảnh báo từ hệ thống giám sát Datadog.
- Khi Sentinel và Datadog phát hiện tốc độ đốt ngân sách lỗi vượt ngưỡng an toàn (ví dụ: burn-rate $\ge 14.4\times$), Cortex sẽ mở cuộc điều tra toàn diện: truy vấn Datadog Logs, kiểm tra các span APM và truy vấn MongoDB.
- Cortex đối chiếu hình dạng biểu đồ lỗi hiện tại với các sự cố trong quá khứ nhờ cơ chế tìm kiếm vector (Vector Search) trên MongoDB Atlas, nhanh chóng kết luận nguyên nhân gốc rễ và đề xuất chính sách điều phối (ví dụ: chuyển 90% tải sang Vendor B).
- Sau khi vượt qua các rào chắn kiểm duyệt chi phí (Safety Guardrails), chính sách mới được ghi vào MongoDB và bắn tín hiệu qua **Change Streams** để toàn bộ cụm Gateway cập nhật bộ nhớ trong **chưa tới 1 giây**.

**Nguyên tắc cô lập then chốt:** Data Plane và Control Plane được tách rời hoàn toàn. Ngay cả khi AI Agent Cortex bị treo, hết quota API hay sập máy chủ, Gateway vẫn hoạt động trơn tru dựa trên bảng định tuyến gần nhất. Chúng tôi không bao giờ đánh đổi sự sống còn của hệ thống lõi vào tính ổn định của một Agent AI.

## 4. BỐN ĐIỂM NHẤN KỸ THUẬT NỔI BẬT

### Điểm nổi bật 1: Quality SLI — "Định nghĩa lại thế nào là một Request thành công"
Chúng tôi loại bỏ hoàn toàn khái niệm "HTTP 200 = Success". Trong Reflex, một request chỉ được tính là Đạt (Good Event) khi thỏa mãn trọn vẹn cả hai chiều:
1. *Tầng mạng:* HTTP 200 OK, latency < 3000ms.
2. *Tầng ngữ nghĩa:* JSON schema hợp lệ 100%, kết thúc trọn vẹn (`finish_reason != 'length'`), nội dung không rỗng và không chứa mẫu từ chối ngầm.

Chỉ số này được tính toán theo thời gian thực trên từng giây, biến các lỗi suy giảm chất lượng vô hình thành các đường cong vi phạm ngân sách lỗi cụ thể trên Datadog.

### Điểm nổi bật 2: Dual-Ledger SLO — Sổ cái kép chứng minh giá trị
Hệ thống tính toán song song hai chỉ số SLO độc lập:
- **Provider SLO:** Chất lượng dịch vụ thô do OpenAI/Anthropic cung cấp.
- **Delivered SLO:** Chất lượng thực tế mà người dùng cuối nhận được sau khi đi qua cơ chế tự chữa lành của Reflex.

Trong một sự cố sụt giảm chất lượng của nhà cung cấp, ban giám khảo có thể nhìn thấy trực quan trên Datadog Dashboard: Provider SLO rớt thảm hại xuống 61%, nhưng Delivered SLO vẫn đứng vững ở mức 99.6%. Khoảng cách 38.6% đó chính là bằng chứng xác thực nhất về giá trị của Reflex.

### Điểm nổi bật 3: Incident Memory — Trí nhớ sự cố bằng Vector 64 chiều trên MongoDB Atlas
Thay vì dùng LLM embedding văn bản chậm chạp và tốn chi phí, chúng tôi vector hóa chính các đường cong chuỗi thời gian:
- Lấy 16 điểm mẫu thời gian xung quanh thời điểm xảy ra sự cố.
- Mỗi điểm trích xuất 4 tham số: tỷ lệ lỗi mạng, tỷ lệ lỗi chất lượng nội dung, độ lệch latency P90 và độ lệch TTFT so với baseline.
- Nối lại thành một **vector đặc trưng 64 chiều (64D Signature Vector)** đại diện cho "hình dạng toán học" của sự cố.
- Khi sự cố mới nổ ra, MongoDB Atlas `$vectorSearch` tìm kiếm các vector có độ tương đồng Cosine cao nhất trong quá khứ chỉ mất **< 20ms**, giúp Cortex tái sử dụng ngay giải pháp đã từng thành công.

### Điểm nổi bật 4: Time Machine — Phản thực tế bằng mô phỏng sự kiện rời rạc
Một câu hỏi kinh điển của các chuyên gia kiến trúc: *"Làm sao bạn chứng minh hệ thống của bạn tốt hơn các proxy gateway thông thường ngoài thị trường?"*

Reflex giải bài toán này bằng công cụ Time Machine: Lấy lại toàn bộ nhật ký truy cập thực tế đã diễn ra trong vụ sự cố, rồi chạy thử nghiệm song song trên 3 kịch bản:
1. *Baseline:* Không can thiệp (gọi thẳng vendor).
2. *Static Gateway:* Chuyển vùng dự phòng kiểu cũ (chỉ chuyển khi gặp mã 5xx/429).
3. *Reflex Platform:* Tự chữa lành thông minh theo chất lượng nội dung.

Kết quả xuất ra một bảng so sánh đối chứng bằng số liệu cụ thể: Reflex đã cứu được bao nhiêu nghìn đơn hàng, tiết kiệm bao nhiêu phần trăm ngân sách lỗi và hạn chế tối đa chi phí gọi API.
