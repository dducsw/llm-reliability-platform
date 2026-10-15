# ADR-0005 — Change Streams chỉ trên collection thường

**Trạng thái:** Accepted

## Bối cảnh
Slide workshop (trang 14): Time Series **không hỗ trợ** Change Streams, Atlas Triggers và Atlas Search. Bản nháp v0 không nhận ra giới hạn này.

## Quyết định
- Event real-time **không** lấy từ `requests_ts`. Thay vào đó:
  - Gateway tự phát metric và log lên Datadog (stream từ ingest layer, đúng khuyến nghị của workshop).
  - Sentinel upsert `health_state` (collection thường). Console watch `health_state`.
- Change Streams dùng trên: `policies` (hot-reload), `incidents` (Cortex + Console), `actions` (state machine), `health_state` (Console), `chaos_runs` (chaos-proxy).
- Resume token lưu trong `stream_checkpoints` theo `consumer_id`. Khi restart thì `resumeAfter`.

## Hệ quả
- Đây là điểm cần **nói rõ khi pitch**: đội hiểu giới hạn của Time Series và thiết kế theo đúng giới hạn đó.
