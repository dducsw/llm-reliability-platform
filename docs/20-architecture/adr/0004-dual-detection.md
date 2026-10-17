# ADR-0004 — Dual detection, một incident

**Trạng thái:** Accepted

## Bối cảnh
Thể lệ yêu cầu monitor Datadog. Nhưng Delivered SLO (tính trên dữ liệu Mongo) và quality SLI là năng lực cốt lõi nằm ngoài Datadog. Hai nguồn có thể cùng bắn cho một sự cố.

## Quyết định
- `dedup_key = sha1(slo_id | target | route)`.
- `incidents` có trường `is_open: true` khi chưa resolved. Thêm **partial unique index** `{dedup_key: 1}` với `partialFilterExpression: {is_open: true}`.
- Mở incident bằng `insertOne`. Nếu gặp `E11000` thì `updateOne({dedup_key, is_open:true}, {$push: {signals: …}})`. Cách này idempotent và không có race.
- Có một monitor riêng cho detector disagreement: một nguồn alert mà nguồn kia im lặng quá N phút.

## Hệ quả
- Incident ghi lại *nguồn nào phát hiện trước*, từ đó so được MTTD của Datadog và của Sentinel.
