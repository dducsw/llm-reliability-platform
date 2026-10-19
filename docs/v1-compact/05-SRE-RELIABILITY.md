# 05 — Độ Tin Cậy & Bộ Não Tự Chữa Lành

Trong kỹ nghệ độ tin cậy hệ thống (SRE - Site Reliability Engineering), mục tiêu cao nhất không phải là ngăn chặn 100% các sự cố (bởi vì các nhà cung cấp bên thứ ba chắc chắn sẽ có lúc bị lỗi), mà là **tự động phát hiện sớm, khoanh vùng thiệt hại và tự động phục hồi trong thời gian ngắn nhất**.

---

## 1. Khái niệm cốt lõi: Quality SLI và Sổ Cái Kép (Dual Ledger)

### A. Chỉ số chất lượng phản hồi (Quality SLI)
Trước đây, các hệ thống thường chỉ đo lường chỉ số SLI (Service Level Indicator) dựa trên mã trạng thái HTTP: Nếu trả về 200 thì tính là "Tốt" (Good), nếu trả về 500 hoặc 504 thì tính là "Xấu" (Bad). 

Như đã giải thích ở bài viết số 01, cách đo này hoàn toàn bất lực trước các mô hình AI. Vì vậy, Reflex định nghĩa ra **Quality SLI**: Một request chỉ được tính là "Tốt" khi và chỉ khi thỏa mãn đầy đủ cả hai điều kiện:
1. **Thành công về mặt kỹ thuật mạng:** Trả về mã HTTP 200 trong ngưỡng thời gian cho phép (ví dụ dưới 3 giây).
2. **Thành công về mặt chất lượng nội dung:** Vượt qua toàn bộ các bài kiểm tra tự động của Gateway:
   - Cấu trúc JSON không bị thiếu dấu ngoặc, đúng các trường bắt buộc của nghiệp vụ.
   - Trạng thái kết thúc không phải là do bị cắt cụt (`finish_reason` không phải là `length`).
   - Nội dung không phải là chuỗi rỗng và không chứa các câu từ chối mẫu của mô hình.

### B. Cơ chế Sổ Cái Kép (Dual-Ledger SLO)
Hệ thống ghi nhận và duy trì song song hai cuốn "sổ cái" đo lường chất lượng:
- **Sổ cái Nhà cung cấp (Provider SLO):** Đo chất lượng dịch vụ gốc do OpenAI hoặc Anthropic cung cấp. Khi các bên này bị quá tải hoặc lỗi mạng, cuốn sổ này sẽ ghi nhận chất lượng tụt dốc không phanh (ví dụ chỉ còn 60%).
- **Sổ cái Người dùng nhận được (Delivered SLO):** Đo chất lượng cuối cùng mà khách hàng thực sự trải nghiệm trên màn hình ứng dụng của họ.
- Nhờ có cơ chế tự động thử lại có chọn lọc (Quality-Aware Retry) và gọi song song dự phòng (Hedging) của Reflex, cuốn sổ cái thứ hai này vẫn duy trì vững vàng ở mức **trên 99.5%**. Khi trình bày bài thi, việc đặt hai biểu đồ này cạnh nhau sẽ chứng minh trực quan cho ban giám khảo thấy giá trị kinh tế khổng lồ của nền tảng.

---

## 2. Quy trình bốn bước của Bộ máy tự chữa lành (Recovery Engine)

Khi sự cố xảy ra, việc tự động can thiệp vào hệ thống cần phải cực kỳ cẩn trọng. Nếu để AI tự do thay đổi cấu hình mà không có sự kiểm soát, AI có thể đưa ra quyết định sai lầm làm sập toàn bộ hệ thống. Reflex thiết kế một quy trình 4 bước chặt chẽ, loại bỏ hoàn toàn rủi ro:

### Bước 1: Đề xuất hành động (Propose)
- Khi nhận được cảnh báo từ Datadog, AI Agent Cortex sẽ tiến hành điều tra và đề xuất một hành động cụ thể từ danh mục các hành động an toàn đã được định nghĩa sẵn.
- Các hành động an toàn bao gồm:
  - `shift_weight`: Chuyển bớt tỷ lệ phần trăm truy cập từ nhà cung cấp đang lỗi sang nhà cung cấp dự phòng.
  - `set_rate_limit`: Tạm thời bóp bớt lưu lượng gọi tới nhà cung cấp đang bị quá tải để họ kịp hồi phục.
  - `toggle_hedging`: Bật cơ chế gọi đồng thời 2 nhà cung cấp cho các khách hàng VIP để giảm tối đa độ trễ.

### Bước 2: Kiểm duyệt rào chắn an toàn (Guardrails)
- Trước khi hành động được thực thi, nó bắt buộc phải đi qua một bộ lọc kiểm duyệt quy tắc an toàn nghiêm ngặt (Policy Engine):
  - **Kiểm tra trần chi phí:** Hành động này có khiến hóa đơn tiền điện toán đám mây vượt quá ngân sách cho phép không?
  - **Kiểm tra sức chứa của đích đến:** Nếu dồn 80% lưu lượng sang nhà cung cấp B, nhà cung cấp B có đủ sức chịu tải không, hay lại gây ra sự cố sập dây chuyền (Cascading Failure)?
  - **Kiểm tra tính đảo ngược:** Hành động này có dễ dàng hoàn tác lại được không nếu gặp sự cố?
- Nếu thỏa mãn toàn bộ các rào chắn này, hệ thống sẽ **tự động phê duyệt** trong tích tắc. Nếu có rủi ro lớn, hệ thống sẽ gửi thông báo lên bảng điều khiển để chờ kỹ sư con người bấm nút duyệt.

### Bước 3: Thực thi chính sách mới (Actuate)
- Bộ phận Actuator sử dụng giao dịch an toàn (ACID Transaction) trong MongoDB để cập nhật cấu hình chính sách mới, đồng thời ghi lại nhật ký kiểm toán và gửi một sự kiện (Event) lên dòng thời gian của Datadog.
- Cổng Gateway lập tức nạp cấu hình mới qua Change Streams trong thời gian dưới 1 giây mà không làm gián đoạn các kết nối đang chạy.

### Bước 4: Kiểm định toán học chứng minh hồi phục (Recovery Proof)
- Đây là một trong những điểm độc đáo nhất của dự án. Hệ thống **không bao giờ đoán mò** xem sự cố đã hết hay chưa bằng cảm tính.
- Sau khi đổi cấu hình, bộ phận Verifier sẽ thu thập dữ liệu trong 3 đến 5 phút tiếp theo và áp dụng các công thức toán học thống kê chặt chẽ:
  - **Phép kiểm định tỷ lệ hai mẫu (Two-proportion z-test):** So sánh tỷ lệ request thành công trước và sau khi can thiệp để chứng minh sự cải thiện này có ý nghĩa thống kê thực sự, không phải do may rủi ngẫu nhiên.
  - **Khoảng tin cậy Wilson (Wilson Score Interval):** Đảm bảo với độ tin cậy 95%, tỷ lệ thành công của hệ thống đã quay trở về vùng an toàn của mục tiêu cam kết.
- **Quyết định sau thẩm định:**
  - Nếu kết quả kiểm định là `FAIL` (chất lượng không cải thiện): Hệ thống lập tức tự động **hoàn tác (Rollback)** về cấu hình trước đó để tránh làm tình hình tồi tệ hơn.
  - Nếu kết quả kiểm định là `PASS` (chất lượng đã hồi phục): Hệ thống mới chính thức đóng hồ sơ sự cố và bắt đầu quy trình chuyển dần lưu lượng trở lại trạng thái ban đầu theo từng bước có kiểm soát (Failback từng nấc: 10% ➔ 50% ➔ 100%).

---

## 3. Trí nhớ sự cố (Incident Memory) và Cỗ máy thời gian (Time Machine)

### Trí nhớ sự cố (Incident Memory)
- Khi một sự cố được giải quyết thành công, toàn bộ thông tin về dạng biểu đồ lỗi (vector 64 chiều), nguyên nhân gốc rễ và hành động đã xử lý thành công sẽ được đóng gói và lưu vào bộ nhớ dài hạn trong MongoDB Atlas.
- Lần sau, khi có một sự cố mới phát sinh, hệ thống chỉ mất chưa tới 50 mili-giây để tra cứu trong kho ký ức bằng tính năng Vector Search. Cortex sẽ biết ngay: *"Sự cố này giống 92% với sự cố tuần trước, lần trước chuyển 80% tải sang nhà cung cấp B đã giải quyết dứt điểm sau 2 phút, tỷ lệ thành công là 100%"*. Điều này giúp rút ngắn thời gian xử lý sự cố (MTTR) từ hàng chục phút xuống chỉ còn vài giây.

### Cỗ máy thời gian (Time Machine — Mô phỏng đối chứng)
- Để tạo ra một màn trình diễn ấn tượng nhất trong buổi thuyết trình, tính năng Time Machine cho phép người vận hành chọn một sự cố đã xảy ra trong quá khứ và bấm nút "Chạy lại phản thực tế" (Counterfactual Replay).
- Thuật toán mô phỏng sự kiện rời rạc (Discrete-Event Simulation) sẽ lấy lại toàn bộ dòng truy cập thực tế của khách hàng tại thời điểm đó, rồi cho chạy song song qua các thuật toán điều phối khác nhau.
- Kết quả được xuất ra thành một bảng số liệu so sánh rõ ràng:
  - Nếu để ứng dụng tự gọi thẳng nhà cung cấp: Hệ thống bị lỗi 1.247 đơn hàng, cháy sạch 100% ngân sách lỗi.
  - Nếu dùng cơ chế chuyển vùng tĩnh của các Gateway thông thường: Hệ thống vẫn bị lỗi 1.239 đơn hàng vì không phát hiện được lỗi cắt cụt JSON.
  - Khi dùng Reflex: Hệ thống chỉ bị lỗi đúng 21 đơn hàng đầu tiên, bảo toàn được 95.9% ngân sách lỗi và tiết kiệm hàng ngàn đô-la tiền bồi thường dịch vụ.
