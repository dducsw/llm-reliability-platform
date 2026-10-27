# Handover SE → DE (Lợi → Đức) — 2026-10-27

Branch: `loibui` (đã push). Phạm vi: toàn bộ task SE còn delay theo [team-plan](../team-plan.md).
Mọi commit có mã task trong message; `git log origin/main..loibui` để xem đầy đủ.

## 1. Cần Đức review / quyết định

| # | Thay đổi | File | Vì sao cần Đức |
| :--- | :--- | :--- | :--- |
| R1 | **Contract:** thêm `ProposedBy.confidence: float \| None` | `packages/reflex-core/reflex_core/actions.py` | Contract chung; guardrail `confidence` đọc trường này (trước đây luôn pass) |
| R2 | Runner ghi thêm `time_scale` vào mỗi phase `chaos_runs` | `apps/simulation/reflex_sim/scenario/runner.py` | Code DE-2.2; Console demo clock ("DEMO TIME ×N") cần giá trị này |
| R3 | `conftest.py` ở root: đặt rỗng `REFLEX_*_TOKEN` trong unit test | `conftest.py` | `Settings()` đọc `.env` thật → API test trả 401 khi chạy pytest ở root |
| R4 | **Khoảng trống spec:** khi Cortex chết, chưa có fallback rule-based ở control-plane (system-architecture §4) | — | `rules.classify` thuộc DE; control-plane không được import cortex (import-linter). Đề xuất: chuyển `rules.py` sang `reflex-core` hoặc để Sentinel gọi; cần thống nhất |
| R5 | Fixture `it_db` (reflex-mongo) dùng `dropDatabase` → user Atlas cần role có quyền này | `packages/reflex-mongo/tests/conftest.py` | Lợi đã cấp role cho user mình; ai chạy integration test trên Atlas cũng cần |

## 2. Đã hoàn thành (SE)

| Task | Nội dung | Điểm chính |
| :--- | :--- | :--- |
| SE-4.4 | `LengthValidator` + spec `length:min-max` | `reflex_core/validators/length.py` |
| SE-3.2 | Webhook Datadog: `webhooks.tf`, nginx envsubst token, allowlist IP Datadog | `$TAGS` string → list; `Recovered` không mở incident |
| SE-7.5 | Postmortem generator | Sự kiện dựng deterministic từ Mongo; LLM chỉ viết tường thuật (lỗi LLM → vẫn có postmortem) |
| SE-7.6 | Cortex → policy engine + test prompt injection | Tool output bọc `<untrusted_data>`; action của Cortex/rules đi qua `Actuator.handle_proposed` |
| SE-7.4 | LLMObs spans | agent `cortex.investigate` / workflow / task / tool / llm; gateway llm span mỗi attempt |
| SE-5.2 | 5 guardrail còn stub | `cooldown`, `flap_guard`, `capacity`, `cost_ceiling`, `blast_radius` — đọc `actions`, `sli_1m`, `targets`, `policies`, `incidents`, `health_state`. Thiếu dữ liệu → pass kèm `detail` |
| SE-8.1 | Time Machine API + màn hình; Memory map | `POST /api/replays` chạy job nền (tối đa 2), SSE topic `replays`; `GET /api/memory/map` chiếu PCA 2D (không phải UMAP) |
| SE-6.6 | Present mode | `?present=1`: che chuỗi giống secret, narration ribbon, demo clock (`GET /api/demo`) |
| SE-9.1 | `task chaos:self` | Dừng mongo / datadog-agent / cortex / control-plane / gateway-1, đo success ratio |
| SE-9.2 | `task loadtest` + header `x-reflex-overhead-ms` | Open-loop, client failover giữa 2 gateway, ghi dbStats Mongo trước/sau |
| SE-9.3 | `task demo:reset`, `task demo:record` | Reset mặc định dry-run; giữ 50 incident bootstrap (`synthetic: true`); policy về seed với version tăng tiếp |

### Liên quan trực tiếp tới phần của Đức

- **Guardrail đọc dữ liệu DE:** `capacity`/`cost_ceiling` cần `sli_1m` scope `route` và `target` có `total`, `cost_usd`, `tokens_in`, `tokens_out` (5 phút gần nhất). `blast_radius` đọc `incidents.severity`, `incidents.routes`, `health_state["route:<r>"].budget_remaining`. Nếu rollup/health writer đổi tên field, guardrail sẽ "pass do thiếu dữ liệu" — cần báo Lợi.
- **`HealthWriter` hiện chưa ghi `budget_remaining`** → bậc nới blast radius theo budget chưa kích hoạt trên dữ liệu thật.
- **Time Machine:** API gọi `run_replay(incident_key, variants, k, seed, db, replay_id)` của Đức; job mới lưu `requested` thay cho `variants`/`seeds` lúc queued (kết quả `variants` vẫn do `run_replay` ghi).
- **Memory:** `/api/memory/similar` nhận cả `key` lẫn `_id`, truyền `current_id=incident["_id"]` vào A10.

## 3. Sửa khi dựng stack bằng Docker (ảnh hưởng mọi image Python)

Lần đầu `docker compose up`, mọi service Python restart liên tục với
`exec /app/.venv/bin/ddtrace-run: no such file or directory`.

| Lỗi | Nguyên nhân | Sửa |
| :--- | :--- | :--- |
| Script trong `.venv/bin` không chạy | venv build ở `/src/.venv` rồi copy sang `/app/.venv`; shebang vẫn là `#!/src/.venv/bin/python` | Build stage dùng `WORKDIR /app` (trùng runtime) |
| Import workspace package sẽ hỏng | `uv sync` mặc định cài workspace member dạng editable → trỏ về `/src/packages/...` không có trong runtime | `uv sync --no-editable` |
| Gateway/CP/sim không thấy `seeds/`, `scenarios/` | Code đọc đường dẫn tương đối, runtime chỉ copy `.venv` | Copy `seeds/` và `scenarios/` vào image |
| `.env` (secret), `.git`, `node_modules` lọt vào build context | Không có `.dockerignore` | Thêm `.dockerignore` (root) và `apps/console/.dockerignore` |

Đức lưu ý: file data (prompt `.md`, pipeline JSON…) nằm trong package giờ phải được đóng vào wheel
(hatchling mặc định lấy mọi file trong thư mục package — nếu thêm file ngoài package thì cần khai báo).

## 4. Cách chạy lại

```bash
task up && task seed                    # stack local + dữ liệu
task chaos:self -- --out chaos.json     # SE-9.1
task loadtest -- --minutes 30 --out loadtest.json   # SE-9.2 (50 rps mặc định)
task demo:reset                         # dry-run; thêm `-- --yes` để xoá
task demo:record -- --reset             # quay video, console ?present=1
```

## 5. Kết quả

_(đang chạy)_

## 6. Còn mở

- Deploy `demo` lên VM + TLS + vendor thật (SE-9.3) — cần quyền hạ tầng.
- R4 (fallback khi Cortex chết) — cần thống nhất vị trí `rules`.
