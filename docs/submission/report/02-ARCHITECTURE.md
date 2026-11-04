# 02 — Kiến Trúc Hệ Thống & Những Quyết Định Kỹ Thuật (ADRs)

## 1. NGUYÊN TẮC CỐT LÕI: PHÂN TÁCH RẠCH RÒI DATA PLANE VÀ CONTROL PLANE

Một trong những sai lầm phổ biến nhất khi các kỹ sư bắt đầu xây dựng hệ thống AI tự chữa lành (Self-Healing AI Systems) là: **Nhồi nhét logic phân tích và suy luận AI trực tiếp vào đường đi của request.**

Hậu quả của thiết kế này là một thảm họa về hiệu năng: Mỗi request của người dùng phải chờ gateway truy vấn cơ sở dữ liệu, chờ mô hình AI suy luận, đẩy độ trễ từ vài mili-giây lên thành vài giây. Chưa kể, nếu dịch vụ AI phân tích bị lỗi hoặc cạn quota, toàn bộ cổng thanh toán và giao dịch của khách hàng sẽ bị kéo sập theo.

Để đảm bảo tính sẵn sàng cấp doanh nghiệp (Enterprise-Grade Reliability), Reflex phân tách hệ thống thành hai thế giới biệt lập:

![Sơ đồ Kiến trúc Phân tách Data Plane và Control Plane (Reflex Two-Speed Architecture)](images/two-speed-loop.svg)

### 1.1. Reflex Data Plane (Thư mục `apps/gateway`) — "Nhanh, Tinh gọn, Không Nghẽn"
Data Plane là bề mặt tiếp xúc trực tiếp với người dùng và các client app (ShopMate) thông qua chuẩn giao thức quen thuộc của OpenAI (`POST /v1/chat/completions`):
- **Routing & Scoring hoàn toàn trên RAM:** Bảng định tuyến và trọng số của các nhà cung cấp (OpenAI, Anthropic, Mock) được tính toán sẵn và nạp trên bộ nhớ RAM. Gateway không bao giờ thực hiện câu lệnh `find()` hay `aggregate()` vào MongoDB trên đường đi của request.
- **In-Flight Quality Validators (< 2ms):** Ngay khi dòng stream dữ liệu trả về từ LLM, các hàm kiểm định ngữ nghĩa siêu tốc đọc nội dung: kiểm tra tính hợp lệ của JSON Schema, cờ kết thúc `finish_reason` và lọc bỏ các mẫu câu từ chối ngầm.
- **Circuit Breaker & Fallback tức thì:** Nếu phát hiện câu trả lời bị hỏng hoặc nhà cung cấp ném lỗi mạng, Gateway lập tức ngắt mạch và gọi sang nhà cung cấp dự phòng tiếp theo. Người dùng luôn nhận được kết quả hợp lệ với độ trễ tối thiểu.
- **Hàng đợi đo đạc bất đồng bộ (In-Memory Telemetry Queue):** Dữ liệu đo đạc (độ trễ từng chặng, số lượng token, chi phí ước tính) được ném vào một hàng đợi RAM. Một luồng nền (background worker) sẽ gom lô (batch) và ghi bất đồng bộ sang MongoDB Time Series và Datadog DogStatsD. Nhờ đó, việc thu thập dữ liệu đo đạc chi tiết có chi phí trễ là **0 mili-giây đối với người dùng**.

### 1.2. Reflex Control Plane (Thư mục `apps/control-plane` & `apps/cortex`) — "Thông minh, Độc lập, An toàn"
Control Plane chạy hoàn toàn độc lập ngoài luồng dữ liệu (out-of-band / background process), tách biệt về tài nguyên CPU/RAM và vòng đời với Gateway:
- **Sentinel (Giám sát ngân sách lỗi):** Liên tục theo dõi tốc độ đốt ngân sách lỗi (Error Budget Burn Rate) theo từng giây. Khi phát hiện vi phạm SLO nghiêm trọng, Sentinel sẽ kích hoạt quy trình mở phiếu sự cố (Incident).
- **Cortex AI SRE Agent:** Đóng vai trò là một điều tra viên thông minh. Agent tự động truy vấn đa chiều: đọc logs và APM traces từ Datadog, thực hiện tìm kiếm vector trên MongoDB để tìm lại các sự cố tương đồng trong quá khứ, từ đó đưa ra chẩn đoán nguyên nhân gốc rễ và đề xuất hành động khắc phục.
- **Policy Actuator & Safety Guardrails:** Trước khi bất kỳ đề xuất nào của AI được áp dụng, nó bắt buộc phải đi qua một bộ rào chắn an toàn (Guardrails): Kiểm tra trần chi phí gọi API, kiểm tra khả năng chịu tải của cụm đích (đề phòng sập dây chuyền - cascading failure). Chỉ khi vượt qua toàn bộ các rào chắn này, Actuator mới cập nhật chính sách mới vào MongoDB.
- **Statistical Verifier:** Sau khi chính sách mới được kích hoạt, Verifier theo dõi số liệu trong 3–5 phút tiếp theo và áp dụng các công thức kiểm định toán học thống kê để chứng minh hệ thống đã thực sự hồi phục, trước khi ra quyết định đóng sự cố hoặc tự động rollback.

**Cam kết Fail-Safe:** Nếu cụm Control Plane hoặc AI Agent Cortex gặp sự cố sập nguồn, Gateway Data Plane vẫn tiếp tục định tuyến lưu lượng bình thường dựa trên chính sách ổn định gần nhất trong RAM. Hệ thống không bao giờ có điểm nghẽn đơn lẻ (Single Point of Failure).

## 2. TRỤ CỘT CÔNG NGHỆ: VÌ SAO LÀ MONGODB VÀ DATADOG TRONG BÀI TOÁN REAL-TIME?

Khi kiến trúc một hệ thống giám sát và vận hành thời gian thực (Real-time Operations) cho các ứng dụng GenAI nhịp độ cao, thách thức lớn nhất nằm ở việc **hài hòa giữa tốc độ thu thập số liệu mili-giây và khả năng phân tích ngữ nghĩa sâu sắc**. Chúng tôi lựa chọn MongoDB Atlas và Datadog làm hai trụ cột công nghệ nền tảng dựa trên các cơ sở lý thuyết và năng lực kiến trúc chuyên sâu:

### 2.1. Vì sao là MongoDB Atlas? Lý thuyết nền tảng & Vai trò trong kiến trúc

Hệ thống vận hành AI tự chữa lành phát sinh 3 dạng dữ liệu với đặc thù truy cập riêng biệt:
1. *Dữ liệu trạng thái cấu hình (Operational Policies):* Cần tính toàn vẹn cao, hỗ trợ giao dịch ACID và schema linh hoạt để lưu trữ luật điều phối động.
2. *Dòng dữ liệu chuỗi thời gian (High-Throughput Telemetry):* Hàng triệu data points đo lường in-flight validation, token count, độ trễ từng chặng với tần suất ghi liên tục.
3. *Bộ nhớ tri thức ngữ nghĩa (Incident Signatures):* Không gian vector đa chiều đại diện cho hình thái toán học của các sự cố để tra cứu tương đồng.

Nếu sử dụng kiến trúc phân mảnh truyền thống (RDBMS cho cấu hình + InfluxDB/Prometheus cho chuỗi thời gian + Pinecone cho vector), hệ thống sẽ gánh chịu sự phức tạp vận hành rất lớn, chi phí đồng bộ dữ liệu cao và rủi ro lệch pha (Data Inconsistency / Split-Brain). MongoDB Atlas giải quyết triệt để bài toán này nhờ hợp nhất 3 lý thuyết nền tảng trong cùng một động cơ lưu trữ:

- **Lý thuyết Oplog & Change Streams (Distributed Event Sourcing):**
  - *Bản chất kỹ thuật:* MongoDB Oplog (Operations Log) là một capped collection tuần tự ghi nhận toàn bộ biến đổi dữ liệu trên primary node của Replica Set. Tính năng Change Streams mở ra một tailable cursor lắng nghe trực tiếp trên Oplog, phát tán sự kiện thay đổi đến các node kết nối với độ trễ dưới 1 giây (sub-second).
  - *Ứng dụng trong Reflex:* Biến MongoDB thành một Message Bus sự kiện thời gian thực mà không cần triển khai thêm Kafka hay Redis Pub/Sub. Khi Control Plane cập nhật chính sách mới vào collection `policies`, toàn bộ cụm Gateway lập tức nhận tín hiệu và hot-reload bộ nhớ RAM tức thì.
- **Lý thuyết Time Series Collections (Columnar Bucketing & Compression):**
  - *Bản chất kỹ thuật:* Khác với collection thông thường ghi từng document đơn lẻ (gây phân mảnh I/O và phình to B-Tree index), MongoDB Time Series tự động gom các bản ghi có chung `metaField` trong một khoảng thời gian vào các bucket nén dạng cột (columnar format) bằng thuật toán zstandard/snappy.
  - *Ứng dụng trong Reflex:* Thu thập hàng triệu điểm đo telemetry từ Gateway với dung lượng đĩa giảm hơn 70%, tốc độ nén ghi cực cao và tối ưu hóa các truy vấn tổng hợp theo khoảng thời gian (`$bucket`, `$group`) phục vụ tính toán SLO và Rollup dữ liệu.
- **Lý thuyết Atlas Vector Search (Integrated HNSW Indexing):**
  - *Bản chất kỹ thuật:* Sử dụng cấu trúc đồ thị Hierarchical Navigable Small World (HNSW) tích hợp trực tiếp trên dữ liệu document. Vector đặc trưng và toàn bộ thông tin ngữ cảnh nghiệp vụ (metadata, root cause, action đã áp dụng) cùng nằm trong một bản ghi duy nhất.
  - *Ứng dụng trong Reflex:* Khi sự cố nổ ra, Cortex Agent trích xuất vector chuỗi thời gian 64 chiều và thực hiện `$vectorSearch` để tìm lại các sự cố tương đồng trong quá khứ chỉ mất **dưới 20ms**. Không có độ trễ đồng bộ mạng sang vector DB bên thứ ba, bảo đảm tính toàn vẹn thông tin.

### 2.2. Vì sao là Datadog? Lý thuyết nền tảng & Vai trò quan sát thời gian thực

Đối với bài toán Real-time Monitoring cho ứng dụng AI, việc chỉ theo dõi các chỉ số hạ tầng truyền thống (CPU, RAM, HTTP status) tạo ra một "khoảng mù" nguy hiểm (The Silent Brownout). Datadog được chọn làm trung tâm thần kinh giám sát thời gian thực nhờ 4 nền tảng lý thuyết tiên tiến:

- **Lý thuyết Multi-Window Multi-Burn-Rate (Tiêu chuẩn Google SRE cho Alerting):**
  - *Bản chất kỹ thuật:* Phương pháp cảnh báo truyền thống dùng ngưỡng tĩnh (Static Threshold, ví dụ: "tỷ lệ lỗi > 2% trong 5 phút") tồn tại nhược điểm lớn: vừa dễ gây báo động giả khi có nhiễu ngắn hạn (Alert Fatigue), vừa phản ứng quá chậm chạp trước các đợt sụt giảm chất lượng nghiêm trọng.
  - *Ứng dụng trong Reflex:* Datadog hỗ trợ thiết lập giám sát Multi-Burn-Rate theo đúng chuẩn sách trắng Google SRE. Hệ thống đánh giá đồng thời trên hai cửa sổ trượt: cửa sổ ngắn (Short Window: 2–5 phút) để phát hiện tốc độ tiêu hao ngân sách lỗi đột biến, và cửa sổ dài (Long Window: 30–60 phút) để xác nhận xu hướng suy giảm bền vững. Phép toán logic `AND` giữa hai cửa sổ giúp triệt tiêu hơn 95% báo động giả, đồng thời bảo đảm thời gian phát hiện sự cố (MTTD) chỉ trong vòng **30 đến 90 giây**.
- **Lý thuyết Unified Observability & Distributed Tracing:**
  - *Bản chất kỹ thuật:* Tích hợp chặt chẽ 3 trụ cột dữ liệu (Metrics, Traces, Logs) dưới một quy chuẩn gắn nhãn hợp nhất (Unified Service Tagging: `env`, `service`, `version`). Mỗi request đi qua hệ thống đều được tiêm ngữ cảnh truy vết phân tán (`x-datadog-trace-id`, `x-datadog-parent-id`).
  - *Ứng dụng trong Reflex:* Cho phép kỹ sư SRE và AI Agent bóc tách chi tiết biểu đồ thác nước (Waterfall Trace): phân định chính xác bao nhiêu mili-giây tiêu tốn tại Gateway, bao nhiêu mili-giây tại đường truyền mạng RTT, và thời gian sinh token đầu tiên (TTFT) của upstream LLM là bao nhiêu. Khi có lỗi, vết APM liên kết trực tiếp tới log chi tiết của request tương ứng.
- **Lý thuyết Datadog LLM Observability (LLMObs):**
  - *Bản chất kỹ thuật:* Cung cấp mô hình dữ liệu quan sát phân tầng chuyên biệt cho Generative AI: `Workflow` $
ightarrow$ `Agent` $
ightarrow$ `LLM Call` $
ightarrow$ `Tool Call`. Tự động đo lường số lượng prompt/completion tokens, chi phí tính toán theo bảng giá từng nhà cung cấp và đánh giá chất lượng câu trả lời theo thời gian thực (In-flight Evaluations).
  - *Ứng dụng trong Reflex:* Minh bạch hóa toàn bộ quá trình tư duy, gọi công cụ truy vấn MongoDB và các bước suy luận của Cortex Agent khi điều tra sự cố. Người vận hành có thể theo dõi trực quan từng bước điều tra của AI trên giao diện LLM Observability của Datadog.
- **Kiến trúc Webhook-Driven Closed-Loop SRE:**
  - *Bản chất kỹ thuật:* Datadog không chỉ là một bảng điều khiển thụ động (Passive Dashboard) để người dùng ngồi quan sát, mà đóng vai trò là "cảm biến kích hoạt" (Active Trigger) cho chu trình điều khiển tự động.
  - *Ứng dụng trong Reflex:* Ngay khi composite monitor trên Datadog phát hiện tốc độ đốt ngân sách lỗi vượt ngưỡng an toàn, hệ thống lập tức phát đi một Alert Webhook mang theo đầy đủ ngữ cảnh sự cố (thời điểm, vendor vi phạm, loại lỗi) sang endpoint của Reflex Sentinel, kích hoạt vòng lặp tự chữa lành khép kín hoàn toàn tự động.

## 3. CƠ CHẾ HOT-RELOAD KHÔNG GIÁN ĐOẠN QUA MONGODB CHANGE STREAMS

Một trong những yêu cầu sống còn của các hệ thống High-Availability là: **Khi thay đổi luật điều phối giao thông, không được khởi động lại máy chủ (No Restart / Zero Downtime).**

Nếu mỗi lần Cortex ra quyết định chuyển 90% tải sang nhà cung cấp dự phòng mà Gateway phải restart, toàn bộ hàng ngàn kết nối WebSocket và HTTP Streaming đang dở dang của khách hàng sẽ bị ngắt kết nối (socket drop).

Reflex giải quyết bài toán này một cách tự nhiên và tinh tế nhờ tính năng **MongoDB Change Streams**:

![Cơ chế Hot-Reload qua MongoDB Change Streams](images/change-streams-hot-reload.svg)

1. **Ghi cấu hình có số phiên bản (Versioned Policies):** Khi Control Plane ra quyết định can thiệp, Actuator sử dụng giao dịch an toàn (ACID Transaction) để ghi một bản ghi cấu hình mới kèm số phiên bản tăng dần (`version: 17`) vào collection `policies`.
2. **Lắng nghe luồng thay đổi thời gian thực:** Tại mỗi node Gateway, có một tiến trình coroutine chạy nền liên tục duy trì một cursor mở với MongoDB Change Streams trên collection `policies`.
3. **Hoán đổi con trỏ nguyên tử (Atomic Pointer Swap):** Ngay khi sự kiện cập nhật được MongoDB bắn qua kết nối mạng, Gateway lập tức parse cấu hình qua Pydantic v2, thẩm định tính hợp lệ và hoán đổi con trỏ trỏ tới bảng định tuyến trong RAM.
4. **Hiệu quả thực nghiệm:** Toàn bộ quá trình từ lúc Control Plane ấn nút cập nhật đến khi tất cả các node Gateway trên toàn hệ thống áp dụng luật điều phối mới diễn ra trong **thời gian dưới 1 giây (Sub-second Propagation)** mà không có bất kỳ request nào bị rớt hay gián đoạn.
