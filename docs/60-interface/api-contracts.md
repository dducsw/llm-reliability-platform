# API Contracts

## 1. Gateway (data plane) — OpenAI-compatible

`POST /v1/chat/completions`: body theo chuẩn OpenAI Chat Completions (`model`, `messages`, `stream`, `max_tokens`, `response_format`…).

| Header request | Ý nghĩa |
| :--- | :--- |
| `x-reflex-route` (bắt buộc) | Route logic, ví dụ `order.extract`. Quyết định policy, validator và SLO |
| `x-priority` | `0`–`2`, mặc định 1 |
| `x-reflex-session` | Hash phiên (blast radius) |
| `x-reflex-deadline-ms` | Ghi đè deadline (≤ policy) |
| `traceparent` | Trace context |

`model` trong body được **bỏ qua** khi route có policy, vì router quyết định target. Giá trị `model: "reflex/auto"` là mặc định trong tài liệu. Có thể ép target bằng `model: "target:vendorB:large"`; khi ép thì các check eligibility vẫn chạy.

| Header response | Ý nghĩa |
| :--- | :--- |
| `x-reflex-target` | Target cuối cùng |
| `x-reflex-attempts` | Số attempt |
| `x-reflex-policy-version` | Version policy đã dùng |
| `x-reflex-request-id` | Request id |
| `x-reflex-quality` | `pass` / `fail:<check>` |

Lỗi được trả theo envelope lỗi của OpenAI, thêm `reflex.reason` (`shed`, `deadline`, `all_targets_unavailable`, `quality_exhausted`).

Endpoint khác: `GET /healthz`, `GET /readyz` (đã load policy), `GET /v1/models` (liệt kê route).

## 2. Control plane (BFF) — REST + SSE

| Method | Path | Mô tả |
| :--- | :--- | :--- |
| GET | `/api/pulse` | Snapshot cho trang Pulse |
| GET | `/api/slos` · `/api/slos/:id` | SLO + budget + burn (A4, A5) |
| GET | `/api/incidents?status=&sli=&from=` | Danh sách |
| GET | `/api/incidents/:key` | Chi tiết + investigation + actions + memory (A10) |
| POST | `/api/incidents/:key/ack` | Acknowledge |
| POST | `/api/incidents/:key/false-positive` | Đánh dấu false positive (bị loại khỏi Memory) |
| GET | `/api/actions?state=awaiting_approval` | Hàng đợi duyệt |
| POST | `/api/actions/:id/approve` · `/reject` | Body `{reason}`; ghi `decided_by` |
| POST | `/api/actions` | Người tạo action thủ công (cũng phải qua guardrails) |
| GET | `/api/policies` · `/api/policies/:route/history` | Policy và lịch sử |
| POST | `/api/replays` | Chạy Time Machine `{incident_key, variants[], k}` |
| GET | `/api/replays/:id` | Kết quả |
| GET | `/api/memory/similar?incident=` | A10 trực tiếp |
| GET | `/api/pipelines/:id` | Định nghĩa pipeline + lần chạy gần nhất (Query Explorer) |
| POST | `/api/lab/scenarios/:name/run` | Chạy scenario (chỉ ở env `local` và `demo`, cần token) |
| GET | `/api/stream?topics=health,incidents,actions,policies,lab` | **SSE**: đa kênh, mỗi event gồm `{topic, op, doc}`; nguồn là Change Streams |
| POST | `/hooks/datadog` | Webhook ingest (token header) |

**Auth:** demo dùng một token cho Console (cookie httpOnly), đủ cho phạm vi cuộc thi. Thiết kế production dùng OIDC, ngoài phạm vi.

**SSE vs WebSocket:** luồng dữ liệu một chiều server → client, tự reconnect và gửi lại `Last-Event-ID` (map sang resume token). Lựa chọn này đơn giản hơn WebSocket mà đủ dùng.

## 3. Internal events (Pydantic, `reflex-core`)

`RequestEvent`, `AttemptEvent`, `ProbeEvent`, `Policy`, `ActionSpec`, `Action`, `Incident`, `Investigation`, `Signal`, `VerificationResult`. JSON Schema được export vào `infra/mongo/validators/*.json`, TypeScript types được sinh cho console.
