# ADR-0002 — MongoDB Atlas 8.x; atlas-local cho dev

**Trạng thái:** Accepted

## Bối cảnh
Cần: Time Series, `$percentile`/`$median` (7.0+), `$setWindowFields`, Change Streams (cần replica set), **Atlas Vector Search** và Atlas Search.

## Quyết định
- **Demo/prod**: MongoDB Atlas, bản 8.x. Đầu tiên thử tier miễn phí (M0) hoặc Flex. Nếu vướng giới hạn (số search index, throughput, ops/s) thì nâng lên M10 trong thời gian Build.
- **Dev/CI**: Docker image `mongodb/mongodb-atlas-local`. Image này là replica set một node, có sẵn Atlas Search và Vector Search, nên code giống hệt môi trường Atlas.
- Schema validator (`$jsonSchema`) bật ở mức `moderate` cho collection thường.

## Hệ quả
- **Cần kiểm chứng sớm (spike ở Phase 0):** giới hạn search index và Change Streams trên tier đã chọn; `$rankFusion` (hybrid search) có hỗ trợ không. Nếu không có thì merge kết quả ở tầng app.
- Online Archive cần M10+, nên chỉ mô tả trong thiết kế lifecycle (cold tier) chứ không bắt buộc demo.
