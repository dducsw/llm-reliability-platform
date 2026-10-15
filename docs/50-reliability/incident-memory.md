# Incident Memory — Vector Search trên hình dạng sự cố

## 1. Ý tưởng

Một SRE nhiều kinh nghiệm nhìn biểu đồ là nói được: *"Cái này giống vụ tuần trước, lần đó chuyển sang vendor B là xong."* Incident Memory làm đúng việc đó bằng dữ liệu:

1. **Encode:** mỗi sự cố được chuyển thành một vector 64 chiều mô tả *hình dạng* của 4 tín hiệu quanh thời điểm phát hiện ([A9](../30-data/aggregation-catalog.md#a9)).
2. **Recall:** `$vectorSearch` tìm các sự cố đã resolved có hình dạng gần nhất ([A10](../30-data/aggregation-catalog.md#a10)).
3. **Rank actions:** gộp kết quả theo loại action, có trọng số similarity, để tính *tỉ lệ thành công đã được kiểm chứng* (Recovery Proof) và thời gian hồi phục trung vị.
4. **Learn:** khi resolved, incident mới cùng kết quả action của nó trở thành ký ức cho lần sau.

Không cần model embedding và không cần LLM. Vector là đặc trưng có thể giải thích được: Console vẽ lại vector thành 4 sparkline để người xem *thấy* vì sao hai sự cố giống nhau.

## 2. Thiết kế vector (signature v2)

```
vec = [ c1(t−12) … c1(t+3) | c2(t−12) … c2(t+3) | c3(…) | c4(…) ]   // 4 × 16 = 64
c1 = availability bad ratio        ∈ [0,1]
c2 = quality bad ratio             ∈ [0,1]
c3 = log2(p95 / baseline) / 3      ∈ [−1,1]
c4 = log2(ttft_p95 / baseline) / 3 ∈ [−1,1]
```

- **Bất biến theo target và traffic:** dùng ratio và log-ratio so với baseline, không dùng giá trị tuyệt đối.
- **Cosine similarity:** so *hình dạng và tỉ lệ giữa các kênh* (ví dụ: "quality xấu, latency bình thường" khác hẳn "mọi thứ xấu").
- **Lệch thời gian:** cửa sổ neo tại `detected_at`. Hai sự cố cùng kiểu nhưng tốc độ phát hiện khác nhau có thể lệch 1–2 phút. Để bớt nhạy, khi lưu thì làm mượt (moving average 3 điểm). Tùy chọn: khi query thì thêm 2 vector dịch ±1 phút rồi lấy max similarity.
- **Versioning:** `signature.v`. Khi thay đổi công thức thì backfill bằng job tính lại từ `sli_1m` (còn dữ liệu trong 45 ngày) và lọc theo `v` khi search.

## 3. Cold start — ký ức ban đầu

Một hệ thống mới không có ký ức. Hai nguồn để khởi tạo:

| Nguồn | Cách làm | Khai báo |
| :--- | :--- | :--- |
| **Game days tự động** | `task memory:bootstrap` chạy 40–60 biến thể scenario (seed, target, cường độ khác nhau) ở chế độ `--fast` trên mock. Hệ thống tự phát hiện, tự xử lý, tự ghi kết quả. Một số biến thể cố tình dùng action *sai* để memory có cả ví dụ FAIL | `synthetic: true`, ghi trong submission declarations |
| **Sự cố thật từ dataset** | A15 tìm các cửa sổ lỗi trong `bench_ts`, rồi replay hình dạng (S6) qua hệ thống để sinh incident có action và outcome | Nguồn CC0 |

Khi demo, Console ghi rõ: "Memory: 52 incidents (48 game-day, 4 replay-from-public-data)".

## 4. Hybrid recall (tùy chọn T3)

- **Shape:** `$vectorSearch` trên `incidents.signature.vec`.
- **Text:** Atlas Search trên `postmortems` (root cause, tags) với query sinh từ context (`"truncation order.extract vendorA"`).
- Kết hợp: dùng `$rankFusion` nếu cluster hỗ trợ (cần kiểm chứng trên tier đã chọn). Nếu không thì dùng Reciprocal Rank Fusion ở tầng app.

## 5. Đánh giá

- **Recall@3 theo cause_class:** với mỗi game-day incident (leave-one-out), kiểm tra xem 3 kết quả gần nhất có cùng `cause_class` không. Mục tiêu ≥ 0.8. Kết quả được đưa vào slide.
- **Action uplift:** so sánh tỉ lệ PASS của action đầu tiên khi Cortex có và không có Memory (ablation).

## 6. Index

```json
{
  "name": "incident_signature",
  "type": "vectorSearch",
  "definition": {
    "fields": [
      { "type": "vector", "path": "signature.vec", "numDimensions": 64, "similarity": "cosine" },
      { "type": "filter", "path": "status" },
      { "type": "filter", "path": "sli" },
      { "type": "filter", "path": "scope" },
      { "type": "filter", "path": "signature.v" }
    ]
  }
}
```
