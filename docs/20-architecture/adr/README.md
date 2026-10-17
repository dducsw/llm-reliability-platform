# Architecture Decision Records

Mỗi ADR ghi lại **một** quyết định: bối cảnh, lựa chọn đã cân nhắc, quyết định cuối và hệ quả. ADR không bị sửa lại về sau. Khi đổi quyết định thì viết ADR mới với trạng thái `Supersedes ADR-xxxx`.

| ADR | Quyết định | Trạng thái |
| :--- | :--- | :--- |
| [0001](0001-python-monorepo.md) | Python 3.12 cho toàn bộ backend, TypeScript cho console, monorepo `uv` + `pnpm` | Accepted |
| [0002](0002-mongodb-atlas.md) | MongoDB Atlas (8.x) làm nền tảng chính; `mongodb-atlas-local` cho dev | Accepted |
| [0003](0003-modular-control-plane.md) | Control plane là modular monolith | Accepted |
| [0004](0004-dual-detection.md) | Hai detector (Datadog + Sentinel) hội tụ về một incident qua dedup key | Accepted |
| [0005](0005-change-streams-not-on-timeseries.md) | Change Streams chỉ dùng trên collection thường; event real-time lấy từ ingest layer | Accepted |
| [0006](0006-bounded-agent-actions.md) | Cortex chỉ đề xuất action trong catalog có giới hạn; policy engine mới là nơi quyết định | Accepted |
| [0007](0007-observability-as-code.md) | Dashboard, monitor và SLO của Datadog quản lý bằng Terraform | Accepted |
