# 04 — Quan Sát Hệ Thống GenAI Thời Gian Thực Với Datadog: Từ Multi-Burn-Rate Đến LLM Observability

## 1. THÁCH THỨC QUAN SÁT TRONG KỶ NGUYÊN GenAI

Trong các hệ thống phân tán truyền thống, việc giám sát xoay quanh ba trụ cột quen thuộc: **Metrics, Traces và Logs**. Nhưng khi đưa các mô hình ngôn ngữ lớn (LLM) vào chuỗi xử lý, bài toán quan sát trở nên phức tạp hơn gấp nhiều lần:
- Một request không chỉ có trạng thái "thành công hay thất bại", mà nội dung câu trả lời bên trong có thể biến đổi không thể đoán trước (non-deterministic).
- AI Agent không còn chạy theo các dòng mã lệnh tĩnh (if/else), mà tự suy luận, tự quyết định gọi công cụ (tool calling), và có thể lặp lại nhiều vòng trước khi ra quyết định cuối cùng.

Trong dự án **Reflex**, chúng tôi chọn **Datadog** làm "hệ thần kinh quan sát trung tâm". Chúng tôi không chỉ dùng Datadog để vẽ các biểu đồ CPU/RAM thông thường, mà khai thác tối đa những công nghệ giám sát hiện đại nhất của nền tảng này: **Unified Service Tagging, Multi-Window Multi-Burn-Rate SLOs, Composite Monitors** và giải pháp chuyên biệt **Datadog LLM Observability**.

## 2. CHUẨN GẮN NHÃN HỢP NHẤT (UNIFIED SERVICE TAGGING): KẾT NỐI MỌI TÍN HIỆU

Một trong những vấn đề gây đau đầu nhất cho các kỹ sư trực chiến (On-call Engineers) là: **Nhìn thấy một biểu đồ độ trễ bị tăng vọt trên dashboard, nhưng không biết tìm dòng log hay trace nào liên quan giữa hàng triệu sự kiện mỗi phút.**

Datadog giải quyết bài toán này triệt để bằng cơ chế gắn nhãn (tags). Trong mã nguồn của Reflex, mọi dữ liệu gửi lên Datadog (từ span APM, dòng log `structlog` cho đến metric DogStatsD) đều bắt buộc phải mang chung một bộ nhãn chuẩn hóa:

```python
# Ví dụ cấu hình Unified Tagging trong thư viện reflex-telemetry
COMMON_TAGS = {
    "env": "demo",
    "service": "reflex-gateway",
    "version": "1.0.0",
    "route": "order.extract",
    "target": "vendorA:large",
    "incident_id": current_incident_id or "none"
}
```

Nhờ chuẩn gắn nhãn hợp nhất này, chúng tôi tạo ra trải nghiệm điều tra mượt mà (Seamless Triage Workflow):
- Đang nhìn biểu đồ tỷ lệ lỗi của route `order.extract` trên Dashboard D1, kỹ sư chỉ cần nhấp chuột vào đỉnh nhọn bất thường.
- Datadog lập tức mở ra danh sách các **Distributed Traces** đúng trong khung giờ đó.
- Nhấp vào một Trace cụ thể, ta nhìn thấy toàn bộ hành trình của gói tin: từ lúc Gateway nhận request, thời gian kiểm tra JSON schema (mất 1.2ms), thời gian chờ OpenAI phản hồi (mất 1450ms) cho đến span của lần retry sang Anthropic.
- Dưới chân của Trace đó là toàn bộ các dòng **Logs liên quan**, với mã lỗi và thông tin `finish_reason: length`. Không cần bất kỳ thao tác tìm kiếm hay gõ câu lệnh lọc phức tạp nào.

## 3. CẢNH BÁO CHÁY NGÂN SÁCH LỖI THEO CHUẨN GOOGLE SRE (MULTI-WINDOW MULTI-BURN-RATE)

Trong cách cài đặt cảnh báo cũ, người ta thường dùng ngưỡng tĩnh: *"Nếu tỷ lệ lỗi trong 5 phút qua > 5% thì hú còi báo động"*.

Là một kỹ sư SRE, bạn sẽ hiểu ngay nhược điểm lớn của cách làm này:
- **Cảnh báo giả (False Positive) vào ban đêm:** Khi lưu lượng truy cập ban đêm xuống thấp (chỉ có 2 request/phút), chỉ cần 1 request lỗi ngẫu nhiên là tỷ lệ lỗi vọt lên 50%, còi báo động réo inh ỏi đánh thức kỹ sư dậy, dù hệ thống không hề gặp sự cố hệ thống.
- **Phát hiện quá chậm khi có sự cố lớn:** Khi lưu lượng ban ngày rất lớn (100 req/s), một sự cố nghiêm trọng diễn ra nhưng chỉ làm tăng tỷ lệ lỗi lên 4.5% (dưới ngưỡng 5%), còi báo động sẽ im bặt suốt nhiều giờ, trong khi hàng ngàn khách hàng đã bị ảnh hưởng và toàn bộ ngân sách lỗi của tháng bị đốt sạch.

Chúng tôi áp dụng phương pháp chuẩn mực của **Google SRE Book**: Theo dõi tốc độ tiêu hao ngân sách lỗi (**Burn Rate**) đồng thời trên **hai cửa sổ thời gian (Multi-Window)**:

$$\text{Burn Rate} = \frac{\text{Tỷ lệ lỗi thực tế}}{\text{Tỷ lệ lỗi tối đa cho phép theo SLO}}$$

Ví dụ: Với mục tiêu Quality SLO là **99%** trong chu kỳ đánh giá (tức tỷ lệ lỗi cho phép là 1%):
- Tốc độ đốt $1\times$ có nghĩa là ngân sách lỗi sẽ vừa vặn hết sạch sau đúng 30 ngày (trạng thái bình thường).
- Tốc độ đốt $14.4\times$ có nghĩa là hệ thống đang đốt sạch **2% toàn bộ ngân sách lỗi của cả tháng chỉ trong vòng 1 giờ đồng hồ**. Đây là sự cố cực kỳ khẩn cấp cần can thiệp ngay lập tức.

![Cơ chế Đánh giá Multi-Window Multi-Burn-Rate Datadog](images/multi-burn-rate-logic.svg)

Chỉ khi **cả hai cửa sổ thời gian** (cửa sổ ngắn xác nhận lỗi đang diễn ra dữ dội, và cửa sổ dài xác nhận lỗi có ý nghĩa thống kê và đang kéo dài liên tục) cùng vượt ngưỡng, Datadog mới kích hoạt còi báo động.  
Kết quả: **Triệt tiêu hoàn toàn các cảnh báo ảo**, đồng thời rút ngắn thời gian phát hiện sự cố nghiêm trọng xuống chỉ còn **30 đến 90 giây**.

## 4. COMPOSITE MONITORS: PHÂN LẬP NGUỒN GỐC LỖI TỰ ĐỘNG

Khi một ứng dụng AI gặp trục trặc, câu hỏi đầu tiên mà đội ngũ kỹ sư phải trả lời là: **"Lỗi do máy chủ Gateway của mình bị nghẽn, hay do đối tác bên ngoài (OpenAI/Anthropic) đang bị hỏng?"**

Nếu chẩn đoán sai, chúng ta sẽ đưa ra hành động sai lầm: Khởi động lại máy chủ Gateway của mình trong khi lỗi nằm ở phía đối tác, vừa không giải quyết được vấn đề lại vừa làm rớt các kết nối đang chạy.

Reflex giải bài toán này bằng tính năng **Composite Monitor (Monitor kết hợp)** của Datadog:
- **Tín hiệu 1 (Monitor M3):** Tỷ lệ vi phạm Quality SLI trên các request của khách hàng đang tăng cao bất thường.
- **Tín hiệu 2 (Monitor M8):** Tỷ lệ lỗi trên đường thăm dò định kỳ (**Canary Probe**) gọi thẳng từ một máy chủ độc lập tới API của nhà cung cấp bên ngoài cũng bị lỗi tương tự.

Monitor tổng hợp **M9** kết hợp hai tín hiệu này theo logic Boolean:
$$\text{M9} = \text{M3} \land \text{M8}$$

Khi M9 chuyển sang trạng thái cảnh báo, Datadog tự động gắn nhãn chẩn đoán: `diagnosis: provider_side_regression`. Thông tin này được đẩy qua Webhook tới AI Agent Cortex, giúp Cortex bỏ qua toàn bộ việc kiểm tra hạ tầng nội bộ và tập trung ngay vào việc điều phối lưu lượng sang nhà cung cấp khác.

## 5. DATADOG LLM OBSERVABILITY: SOI SÁNG TỪNG BƯỚC SUY LUẬN CỦA AI SRE AGENT

Một trong những lo ngại lớn nhất của các nhà quản lý khi giao quyền tự chữa lành hệ thống cho AI là hiện tượng **"Hộp đen" (Black-Box AI)**: Không ai biết AI đang nghĩ gì, tại sao nó lại đưa ra quyết định chuyển 90% lưu lượng sang nhà cung cấp khác, và liệu nó có bị ảo giác (hallucination) hay không.

Chúng tôi giải quyết triệt để sự hoài nghi này bằng giải pháp **Datadog LLM Observability**:

![Cấu trúc Distributed Trace trong Datadog LLM Observability](images/cortex-llmobs-trace.svg)

Trên Dashboard D3 (Cortex LLM Observability), ban giám khảo có thể nhìn thấu hoàn toàn dòng suy nghĩ của Agent:
- Thời gian thực thi của từng bước điều tra.
- Các câu truy vấn cụ thể mà Agent đã bắn vào cơ sở dữ liệu.
- Bằng chứng thực tế mà Agent đã thu thập được để bảo vệ cho kết luận của mình.
- Lượng token tiêu thụ và chi phí tài chính cho mỗi lần Agent thức giấc để xử lý sự cố.

Điều này biến AI SRE Agent từ một chiếc "hộp đen bí ẩn" thành một **hệ thống có thể kiểm toán toàn diện (Fully Auditable System)**.

## 6. QUẢN LÝ HẠ TẦNG GIÁM SÁT BẰNG MÃ NGUỒN (TERRAFORM)

Toàn bộ hệ sinh thái giám sát đồ sộ này không được tạo bằng cách "bấm chuột thủ công" trên giao diện web của Datadog (vốn rất dễ sót cấu hình và không thể tái lập).

Chúng tôi quản trị toàn bộ 100% cấu hình giám sát dưới dạng mã nguồn (Observability as Code) trong thư mục `infra/terraform/`:
- **4 Dashboards công nghiệp:** D1 Operations, D2 SLO & Error Budget, D3 Cortex LLMObs, D4 MongoDB Performance.
- **11 Monitors thông minh:** Bao gồm các bộ giám sát Multi-Burn-Rate, Canary Probes, và Composite Monitors.
- **Cấu hình Webhooks an toàn:** Tự động đăng ký endpoint với header bảo mật xác thực hai chiều.

Khi cần triển khai sang một cụm môi trường mới (staging, production hoặc demo), chúng tôi chỉ cần chạy một lệnh duy nhất:
```bash
task infra:datadog:apply
```
Toàn bộ hệ thống giám sát chuẩn mực sẽ được dựng lên hoàn chỉnh trong vòng chưa đầy 15 giây.
