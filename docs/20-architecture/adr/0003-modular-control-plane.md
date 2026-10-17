# ADR-0003 — Control plane dạng modular monolith

**Trạng thái:** Accepted

## Bối cảnh
Control plane gồm Sentinel, incident manager, actuator, verifier, webhook ingest, BFF và Time Machine. Tách mỗi module thành một microservice làm tăng số container, số trace hop và công sức deploy, trong khi đội nhỏ và chỉ có một môi trường demo.

## Quyết định
Một process `control-plane`, mỗi module là một package có interface riêng (`reflex_cp.sentinel`, `reflex_cp.incidents`…). Module giao tiếp với nhau **qua MongoDB** (document + Change Streams), không gọi hàm trực tiếp xuyên module. Job định kỳ chạy trên **leader** chọn bằng lease document (`leases` collection, `findOneAndUpdate` có `expires_at`).

## Hệ quả
- Tách module thành service riêng sau này **không đổi contract**, vì contract chính là collection.
- Trace vẫn rõ: mỗi module có `resource` riêng trong APM (`sentinel.tick`, `actuator.execute`…).
