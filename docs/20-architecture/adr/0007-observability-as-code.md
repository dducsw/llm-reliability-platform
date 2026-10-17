# ADR-0007 — Observability-as-code

**Trạng thái:** Accepted

## Quyết định
Dùng Terraform provider `DataDog/datadog` để quản lý dashboard, monitor, SLO, webhook, log pipeline/facet, log-based metric và synthetic (nếu dùng). Phía Mongo, collection, index, validator và search index được tạo bằng script migration idempotent (`reflex-mongo migrate`).

## Hệ quả
- Giám khảo dựng lại được toàn bộ trên Datadog trial của họ chỉ bằng `task infra:datadog:apply`.
- Dashboard JSON nằm trong git, review được qua diff.
