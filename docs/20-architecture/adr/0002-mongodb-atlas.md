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

---

## Addendum (Spike Kết quả Phase 0 — DE-0.2)

1. **Change Streams trên Time Series:**
   - Xác nhận: MongoDB không hỗ trợ Change Streams trực tiếp trên collection có kiểu Time Series (`requests_ts`, `attempts_ts`).
   - Giải pháp: Tuân thủ [ADR-0005](0005-change-streams-not-on-timeseries.md). Chỉ watch trên các operational collections thường: `policies`, `health_state`, `incidents`, `actions`, `chaos_runs`.
2. **Atlas Vector Search & Search Index Limits:**
   - Trên Atlas Free/Flex và `mongodb-atlas-local`: Giới hạn tối đa 3 search indexes trên mỗi cluster.
   - Thực thi thành công 2 indexes cốt lõi:
     - `incident_signature`: Vector Search (HNSW, 64 chiều, metric `cosine`) trên `incidents`.
     - `postmortems_text`: Full-text Search (lucene.standard) trên `postmortems`.
3. **Hybrid Search ($rankFusion):**
   - Atlas 8.x hỗ trợ `$rankFusion` (RRF). Đội ngũ đã có fallback tầng app tại `packages/reflex-mongo/reflex_mongo/repos/postmortems.py` để bảo đảm hoạt động ngay cả khi chạy local không có plugin search engine.
4. **Time Series Granularity & TTL Expire:**
   - Granularity chọn `seconds` cho `attempts_ts`, `requests_ts`, `probes_ts`. TTL bucket dọn dẹp tự động sau 14 ngày (1,209,600s) thông qua background thread WiredTiger mà không gây gián đoạn throughput ghi.
