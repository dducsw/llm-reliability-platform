# ADR-0001 — Python backend, TypeScript console, monorepo

**Trạng thái:** Accepted

## Bối cảnh
Bản nháp v0 mâu thuẫn giữa Python/FastAPI và Go/Gin. Đội có 2–3 người, gồm một Data Engineer và một Software Engineer. Các tích hợp quan trọng nhất là `ddtrace` (APM + **LLM Observability SDK**), PyMongo Async và Anthropic/OpenAI SDK. Ở các tích hợp này, Python là ngôn ngữ được hỗ trợ đầy đủ nhất.

## Lựa chọn
| Phương án | Ưu | Nhược |
| :--- | :--- | :--- |
| **Python toàn bộ** | Một ngôn ngữ; LLMObs SDK chính thức; data engineer viết pipeline thoải mái; Pydantic dùng chung model | Throughput mỗi process thấp hơn Go |
| Go gateway + Python còn lại | Gateway nhanh | Hai ngôn ngữ, model bị định nghĩa trùng; LLMObs cho Go hạn chế hơn |
| Node/TS toàn bộ | Một ngôn ngữ với console | Data engineering trên Node kém tiện |

## Quyết định
- Backend dùng **Python 3.12**, `asyncio`, **FastAPI** + **uvicorn**, **httpx** (HTTP/2), **PyMongo Async API** (`AsyncMongoClient`; Motor đã deprecated), **Pydantic v2**, `ddtrace`, `datadog` (DogStatsD).
- Console dùng **TypeScript + React + Vite**.
- Monorepo: workspace **uv** cho Python, **pnpm** cho console, **Taskfile** làm entrypoint chung.

## Hệ quả
- Tải demo (≤ 50 rps) thấp hơn nhiều so với khả năng của uvicorn với 2 worker. Không có rủi ro hiệu năng.
- Model như `RequestEvent`, `Policy`, `ActionSpec` được định nghĩa một lần trong `packages/reflex-core`. Từ đó sinh JSON Schema cho Mongo validator và TypeScript type cho console.
