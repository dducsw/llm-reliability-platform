# 03 — MongoDB Atlas Trong Hệ Thống Vận Hành Thời Gian Thực: Kiến Trúc Dữ Liệu & Bài Học Thực Chiến

## 1. MONGODB ATLAS: TRUNG TÂM DỮ LIỆU CHUỖI THỜI GIAN & TRÍ TUỆ NHÂN TẠO

Trong hầu hết các đồ án hoặc bài thi hackathon, người ta thường coi cơ sở dữ liệu chỉ là một "kho chứa tĩnh" (Passive Storage) — nơi ghi dữ liệu vào rồi thỉnh thoảng query ra vài bản ghi.

Nhưng trong kiến trúc của **Reflex**, chúng tôi tiếp cận **MongoDB Atlas** với tư duy của một **Active Data Engine (Hệ thống dữ liệu chủ động)**:
- Nơi thu nạp dòng chảy đo đạc (telemetry ingestion) với tốc độ hàng ngàn sự kiện mỗi giây.
- Nơi tự động dọn dẹp và nén dữ liệu theo cơ chế chuỗi thời gian phân tầng.
- Kênh truyền tin thời gian thực cực nhanh (Sub-second Event Bus) qua tính năng Change Streams.
- Kho tri thức sự cố thông minh với năng lực tìm kiếm tương đồng đa chiều thông qua Atlas Vector Search.

Để làm được điều đó mà không biến database thành "bãi rác dữ liệu", toàn bộ mô hình dữ liệu phải được thiết kế với sự kỷ luật cao độ.

## 2. KIẾN TRÚC PHÂN TẦNG DỮ LIỆU THEO "NHIỆT ĐỘ" (DATA TIERING)

Dữ liệu đo đạc của các ứng dụng AI sinh ra liên tục với khối lượng rất lớn. Nếu lưu trữ toàn bộ dữ liệu thô vào một collection duy nhất mãi mãi, cụm cơ sở dữ liệu sẽ nhanh chóng phình to hàng trăm Gigabytes, đẩy chi phí RAM/IOPS lên trời và kéo sập tốc độ truy vấn của hệ thống.

Chúng tôi áp dụng mô hình phân tầng dữ liệu 3 mức nhiệt độ (Multi-temperature Data Lifecycle):

![Kiến trúc Phân tầng Dữ liệu MongoDB Atlas](images/mongo-data-tiering.svg)

### Tầng dữ liệu Nóng (Hot Tier — Time Series Collections)
- **Đặc điểm:** Chứa dữ liệu chi tiết của từng request vừa mới diễn ra: độ trễ từng chặng, thời gian sinh chữ đầu tiên (TTFT), số lượng prompt/completion tokens, thông tin từng lần thử lại.
- **Tần suất truy vấn:** Rất cao trong 1–2 giờ đầu tiên để phục vụ giám sát và điều tra nguyên nhân gốc rễ.
- **Cơ chế tự dọn dẹp (TTL):** Thiết lập chỉ mục TTL tự động xóa sau **14 ngày** (`expireAfterSeconds: 1209600`). Sau 14 ngày, dữ liệu thô này không còn cần thiết cho việc xử lý sự cố trực tiếp và được MongoDB tự động dọn dẹp để giải phóng dung lượng.

### Tầng dữ liệu Ấm (Warm Tier — Standard Collections qua `$merge`)
- **Đặc điểm:** Không để mất xu hướng dài hạn khi dữ liệu thô bị xóa, hệ thống chạy các pipeline tổng hợp định kỳ (Rollup Pipelines) bằng toán tử `$merge` của MongoDB.
- **Cấu trúc lưu trữ:**
  - Collection `sli_1m`: Gộp dữ liệu theo từng phút, lưu trữ phân phối độ trễ P50, P90, P99, tổng số request và số lỗi. Được giữ trong **45 ngày**.
  - Collection `sli_1h`: Gộp dữ liệu theo từng giờ, lưu trữ báo cáo ngân sách lỗi dài hạn, xu hướng trôi dạt chi phí và năng lực đáp ứng của các nhà cung cấp. Được giữ trong **400 ngày**.

### Tầng Tham khảo & Tri thức Vận hành (Operational & Knowledge Tier)
- **Đặc điểm:** Bao gồm danh mục cấu hình hệ thống (`targets`, `policies`), nhật ký sự cố (`incidents`), lịch sử các hành động can thiệp (`actions`) và bộ nhớ sự cố (`incident_memory`).
- **Thời hạn lưu trữ:** **Lưu trữ vĩnh viễn** trong các Standard Collection thông thường. Đây là tài sản tri thức quý giá dùng để đào tạo AI và tra cứu lịch sử vận hành.

## 3. VÌ SAO CHÚNG TÔI TÁCH THÀNH 4 TIME SERIES COLLECTIONS RIÊNG BIỆT?

Một sai lầm rất kinh điển của nhiều kỹ sư khi lần đầu sử dụng MongoDB Time Series là: **Gom tất cả mọi loại sự kiện vào chung một collection đặt tên là `telemetry`.**

Tại sao đây lại là một thiết kế tồi?  
MongoDB Time Series nén dữ liệu thành các khối lưu trữ cột (columnar buckets) dựa trên hai tham số bắt buộc:
1. **Độ chi tiết của thời gian (`granularity`):** Cho biết tần suất dữ liệu sinh ra (`seconds`, `minutes`, hoặc `hours`).
2. **Trường định danh siêu dữ liệu (`metaField`):** Nhóm các sự kiện có cùng nhãn nhận dạng ít thay đổi vào chung một khối lưu trữ (bucket).

Nếu bạn gom các sự kiện có tần suất sinh khác nhau và có cấu trúc nhãn khác nhau vào chung một collection, MongoDB sẽ liên tục phải đóng và mở các bucket mới, làm vỡ cấu trúc nén, lãng phí bộ nhớ RAM và làm chậm nghiêm trọng tốc độ đọc.

Chính vì vậy, Reflex chia tách thành 4 Time Series Collections độc lập với các mục đích chuyên biệt:

```javascript
// 1. requests_ts: Đo lường chất lượng người dùng nhận được (Delivered SLO)
db.createCollection("requests_ts", {
  timeseries: {
    timeField: "ts",
    metaField: "meta", // { route: "order.extract", env: "demo" }
    granularity: "seconds"
  },
  expireAfterSeconds: 1209600 // TTL 14 ngày
});

// 2. attempts_ts: Đo lường chất lượng của từng nhà cung cấp (Provider SLO)
db.createCollection("attempts_ts", {
  timeseries: {
    timeField: "ts",
    metaField: "meta", // { target: "vendorA:large", model: "gpt-4o" }
    granularity: "seconds"
  },
  expireAfterSeconds: 1209600
});

// 3. probes_ts: Thăm dò định kỳ (Canary Probes) phân lập lỗi
db.createCollection("probes_ts", {
  timeseries: {
    timeField: "ts",
    metaField: "meta", // { probe_id: "probe-01", kind: "direct|gateway" }
    granularity: "seconds"
  },
  expireAfterSeconds: 1209600
});

// 4. bench_ts: Dữ liệu đo đạc lịch sử từ nguồn mở (llm-bench-data)
db.createCollection("bench_ts", {
  timeseries: {
    timeField: "ts",
    metaField: "meta", // { vendor: "openai", model: "claude-3-sonnet" }
    granularity: "hours" // Đo định kỳ mỗi giờ -> nén tối đa
  }
});
```

- **`requests_ts`:** Chỉ tập trung vào góc nhìn của khách hàng (User-Facing). Một request của khách hàng có thể phải thử lại 2 lần mới thành công, nhưng trong `requests_ts` chỉ ghi nhận 1 kết quả duy nhất mà người dùng thực tế nhận được.
- **`attempts_ts`:** Ghi nhận từng lần gọi mạng cụ thể. Bảng này giúp tính toán chính xác tỷ lệ lỗi thô của từng nhà cung cấp, độc lập hoàn toàn với việc người dùng có bị ảnh hưởng hay không.
- **`probes_ts`:** Định kỳ mỗi 15 giây, một canary probe được bắn song song: một đường đi qua Gateway và một đường gọi thẳng tới API của nhà cung cấp. So sánh kết quả của hai đường này giúp phân biệt ngay lỗi do nhà cung cấp hay do máy chủ Gateway nội bộ.
- **`bench_ts`:** Lưu trữ 60 ngày dữ liệu lịch sử từ bộ dữ liệu công khai. Vì dữ liệu này được đo đạc theo chu kỳ mỗi giờ một lần, chúng tôi cài đặt `granularity: "hours"`, giúp MongoDB đạt tỷ lệ nén dung lượng cao gấp nhiều lần so với cấu hình mặc định.

## 4. BA BÀI HỌC KỸ THUẬT NÂNG CAO THỰC CHIẾN VỚI MONGODB ATLAS

### Bài học 1: Hiểu rõ ranh giới kỹ thuật — "Time Series không hỗ trợ Change Streams"
Trong tài liệu chính thức của MongoDB, tính năng **Time Series Collection có các giới hạn rất nghiêm ngặt: Không hỗ trợ Change Streams, không hỗ trợ Triggers và không hỗ trợ Atlas Search.**

Rất nhiều đội ngũ kỹ sư khi thiết kế hệ thống giám sát thời gian thực đã vấp phải "cái bẫy" này khi cố gắng bật Change Streams trực tiếp trên collection đo đạc chuỗi thời gian, dẫn đến việc ứng dụng báo lỗi crash ngay khi khởi động.

Chúng tôi giải quyết bài toán này chuẩn xác ngay từ thiết kế tầng kiến trúc:
- **Tách bạch kênh thu nạp và kênh kích hoạt:** Các bảng Time Series chỉ chuyên tâm vào một việc duy nhất: ghi dữ liệu đo đạc tốc độ cao bằng cơ chế ghi theo lô (bulk write).
- **Kích hoạt thời gian thực trên Standard Collections:** Các sự kiện cần phản ứng tức thì (như cập nhật chính sách, mở phiếu sự cố, kích hoạt hành động) được quản lý trên các collection thông thường (`policies`, `incidents`, `actions`). Gateway chỉ duy trì kết nối Change Streams trên collection `policies`. Đây là một điểm thiết kế thể hiện sự thấu hiểu sâu sắc tài liệu của MongoDB.

### Bài học 2: Incident Memory — Vector Search 64 chiều cho hình dạng sự cố
Khi một sự cố nổ ra, một kỹ sư SRE thường mất hàng chục phút để lùng sục logs và tìm lại xem vụ này giống sự cố nào trong quá khứ.

Chúng tôi giải bài toán này bằng tính năng **MongoDB Atlas Vector Search**:
1. **Vector hóa hình dạng đồ thị chuỗi thời gian:** Thay vì dùng mô hình ngôn ngữ lớn để biến đổi văn bản (vốn rất chậm và tốn kém), chúng tôi lấy mẫu 16 khung thời gian xung quanh thời điểm phát sinh sự cố (từ 12 phút trước đến 3 phút sau cảnh báo). Tại mỗi khung thời gian, ghi nhận 4 chỉ số tỷ lệ: tỷ lệ lỗi mạng, tỷ lệ vỡ schema, độ lệch P90 latency và độ lệch TTFT. Ghép lại thành một **mảng số học 64 chiều (64D Vector)**.
2. **Truy vấn độ tương đồng hình dạng đồ thị:** Khi có sự cố mới, hệ thống nén dữ liệu hiện tại thành vector 64D và bắn câu lệnh `$vectorSearch` với độ đo Cosine Similarity vào collection `incident_memory`.
```javascript
// Pipeline tra cứu sự cố tương đồng bằng Atlas Vector Search
[
  {
    $vectorSearch: {
      index: "incident_signature_index",
      path: "signature_vector",
      queryVector: current_64d_vector,
      numCandidates: 20,
      limit: 3
    }
  },
  {
    $project: {
      incident_id: 1,
      root_cause: 1,
      successful_action: 1,
      score: { $meta: "vectorSearchScore" }
    }
  }
]
```
Kết quả trả về chỉ trong **dưới 20 mili-giây** với độ tương đồng 91%, giúp Cortex Agent lập tức tái sử dụng phương án xử lý đã từng cứu hệ thống thành công trước đó.

### Bài học 3: Triệt tiêu sự cố trùng lặp bằng Partial Unique Index
Khi một nhà cung cấp bên ngoài gặp trục trặc, cả bộ phận Sentinel nội bộ và hệ thống cảnh báo Webhook của Datadog đều có thể phát hiện và đồng thời phát tín hiệu mở phiếu sự cố.

Nếu không xử lý tinh tế, hệ thống sẽ mở ra 2 hoặc 3 hồ sơ sự cố cùng lúc cho một vụ việc, khiến nhiều tiến trình tự chữa lành chạy đè lên nhau, gây ra tình trạng xung đột tài nguyên (race condition).

Chúng tôi sử dụng tính năng **Chỉ mục duy nhất một phần (Partial Unique Index)** của MongoDB trên collection `incidents`:
```javascript
db.incidents.createIndex(
  { dedup_key: 1 },
  { 
    unique: true, 
    partialFilterExpression: { 
      status: { $in: ["open", "investigating", "mitigating"] } 
    } 
  }
);
```
- Cơ chế này đảm bảo rằng: Trong khi một sự cố cho `vendorA:large|order.extract` đang được xử lý, mọi yêu cầu tạo sự cố mới có cùng `dedup_key` sẽ tự động bị MongoDB từ chối (Duplicate Key Error) một cách an toàn.
- Ngay khi sự cố được giải quyết và chuyển sang trạng thái `resolved`, trường `dedup_key` đó không còn nằm trong bộ lọc của chỉ mục nữa, sẵn sàng tiếp nhận một sự cố mới trong tương lai nếu có tái diễn.
