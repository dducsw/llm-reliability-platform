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

### Change Stream chưa từng chạy (PyMongo async)

`AsyncCollection.watch()` trả về **coroutine** → phải `async with await coll.watch(...)`. Thiếu `await` →
mỗi 2s log `'coroutine' object does not support the asynchronous context manager protocol` và
không bao giờ nhận event. Unit test không bắt được vì dùng fake. Đã sửa:

| Nơi | Hậu quả trước khi sửa |
| :--- | :--- |
| `gateway/policy_store.py` | Hot-reload policy (SE-1.5) không chạy — gateway chỉ thấy policy lúc khởi động |
| `control-plane/actuator/apply.py` | Actuator không nhận action `proposed`/`approved` nào qua stream; thêm `full_document="updateLookup"` vì approve là `update` |
| `simulation/chaos_proxy/runs_watcher.py` | Chaos-proxy không áp fault từ scenario; thêm: tính lại fault từ mọi `chaos_runs` active → run kết thúc (`update_many`) thì hết fault |
| **`reflex-mongo/streams.py` (DE-1.1)** | `StreamConsumer` cùng lỗi — Đức review giúp |

Có integration test trên Change Stream thật: `apps/gateway/tests/test_policy_hot_reload_it.py`,
`apps/simulation/tests/test_runs_watcher.py`.

### Data path mock chưa từng đúng route

| Lỗi | Hậu quả | Sửa |
| :--- | :--- | :--- |
| `.env` dev thiếu `CHAOS_PROXY_URL` → gateway trong container gọi `localhost:8070` | Mọi attempt lỗi kết nối → breaker mở → shed | compose đặt mặc định URL nội bộ cho mọi service Python |
| Adapter `openai_compat` không gửi `x-reflex-route`; mock adapter đọc `target["route"]` nhưng không ai set | chaos-proxy/mock trả câu chat cho **mọi** route → `order.extract`/`support.triage` luôn quality fail; fault theo route không áp đúng | Orchestrator gắn `route` vào target; adapter gửi header |
| Mock `support.triage` thiếu `department` (bắt buộc trong `triage_v1`) | Route luôn fail | Sửa output (reflex-core, `mock_outputs.py`) |
| **Contract:** `cortex_output` bắt `hypotheses`+`recommendation` ở top-level, nhưng agent trả `{"tool"}` ở lượt trung gian và `{"final": …}` ở lượt cuối | Mỗi lượt gọi tool của Cortex bị gateway coi là quality fail → retry/rescue sang vendor khác (tốn tiền, sai số liệu SLI của `cortex.reason`) | Schema `oneOf` tool-turn \| final; mock output theo cùng giao thức — **Đức review** (eval harness của Đức có đọc output mock cũ không) |

Test chặn hồi quy: `packages/reflex-core/tests/test_validators.py::test_mock_outputs_pass_seeded_route_validators`.

**Còn mở (SE-2.1):** chaos-proxy hiện **tự sinh** response, không forward tới vendor thật hay mock-llm.
Với stack `demo` (vendor thật đi qua chaos-proxy) cần thêm chế độ forward theo `base_url` thật của vendor.

### Hiệu năng gateway (phát hiện khi load test SE-9.2)

Lần chạy 50 rps đầu tiên: gateway chỉ kịp ~7 rps, hàng nghìn request treo, p99 overhead > 1s.

| Lỗi | Hậu quả | Sửa |
| :--- | :--- | :--- |
| Adapter `openai_compat`/`anthropic` tạo `httpx.AsyncClient` **mỗi request** (SSLContext + TCP mới) | ~20–40ms CPU/request → gateway bão hòa ~25 rps; 25 rps wall p50 ~340ms | `SharedClient` dùng chung pool theo adapter (timeout theo request), đóng ở lifespan → p50 ~13ms |
| Healthcheck mongo chạy `mongosh` (Node) mỗi 5s | Mongo "idle" vẫn ~1 core, tranh CPU với gateway trong VM Docker → kéo p99 | `interval: 60s` + `start_interval: 3s` lúc khởi động |
| Container mongo không có `hostname` cố định | `atlas-local` đặt tên replica set = hostname (container id) → **recreate container (đổi config) là mất primary**, runner panic | `hostname: mongo`. Volume cũ cần đổi `_id`/`members[0].host` trong `local.system.replset` sang `mongo` (Lợi đã làm cho volume của mình) |

Đo CPU/request một tiến trình gateway ở 25 rps: khi còn mongo local tranh CPU, `ddtrace-run` = 19ms vs không ddtrace = 9ms;
sau khi bỏ mongo khỏi VM, `ddtrace-run` đầy đủ chỉ còn **8ms**, p99 overhead ~12ms → chi phí chủ yếu do tranh CPU, không phải ddtrace.

**Chế độ Atlas** (`infra/compose/docker-compose.atlas.yml`, `task up:atlas`): không chạy container mongo, dùng
`MONGODB_URI` trong `.env`. Nhẹ hơn hẳn trên laptop (~600MB cho gateway×2 + chaos-proxy + mock-llm + agent). Lưu ý:
chỉ dùng cluster riêng của mình (M0 free: 512MB), thí nghiệm chaos `mongo` không áp dụng (`--only` các service khác).

### ddtrace × PyMongo

`ddtrace` 4.16 báo `failed to enable ddtrace support for pymongo: type object 'Server' has no attribute
'run_operation'` — không crash, chỉ mất span Mongo trong APM. Chờ ddtrace hỗ trợ PyMongo async mới,
hoặc tạm đặt `DD_TRACE_PYMONGO_ENABLED=false` để bớt log.

### Migrate: validator bị bỏ qua (DE)

`reflex-mongo migrate` trên `mongodb-atlas-local:8.0` báo
`Unknown $jsonSchema keyword: $defs` cho `actions`, `incidents`, `policies` → 3 validator **không được
cài**. `$jsonSchema` của MongoDB không hỗ trợ `$defs`/`$ref`; cần inline định nghĩa khi export schema
(`tools/export_schemas.py`).

Đức lưu ý: file data (prompt `.md`, pipeline JSON…) nằm trong package giờ phải được đóng vào wheel
(hatchling mặc định lấy mọi file trong thư mục package — nếu thêm file ngoài package thì cần khai báo).

## 4. Cách chạy lại

```bash
task up && task seed                    # stack local + dữ liệu
task up:atlas -- gateway-1 gateway-2 chaos-proxy mock-llm datadog-agent   # nhẹ, Mongo = Atlas
task chaos:self -- --out chaos.json     # SE-9.1
task loadtest -- --minutes 30 --out loadtest.json   # SE-9.2 (50 rps mặc định)
task demo:reset                         # dry-run; thêm `-- --yes` để xoá
task demo:record -- --reset             # quay video, console ?present=1
```

## 5. Kết quả (stack local, Docker Desktop trên macOS, Mongo `mongodb-atlas-local:8.0`)

Dữ liệu: `migrate` + `seed` + `bootstrap_memory` (50 incident). Chưa chạy `bench import --days 60`.

### Smoke

| Kiểm tra | Kết quả |
| :--- | :--- |
| 3 route qua gateway | `order.extract`, `chat.reply`, `support.triage`: 200, 1 attempt, quality pass |
| Hot-reload policy | `$set version` trên `chat.reply` → log `Hot-reloaded policy for chat.reply v2` |
| `nginx -t` (template demo) | OK; token render đúng; allowlist 9 dải IP webhook ap1 |
| Integration test (Mongo local) | 9 passed, 3 skipped |

### SE-9.1 — `tools/chaos_self.py` (10 rps × 60s mỗi thí nghiệm, client failover 2 gateway)

| Dừng | Baseline OK | OK khi dừng | Phục hồi | Kết quả |
| :--- | ---: | ---: | :--- | :--- |
| mongo | 100% | 100% (600/600) | ✓ | PASS |
| datadog-agent | 100% | 100% (600/600) | ✓ | PASS |
| cortex | 100% | 100% (600/600) | ✓ | PASS |
| control-plane | 100% | 100% (600/600) | ✓ | PASS |
| gateway-1 | 100% | 100% (600/600) | ✓ | PASS |

Sau khi mongo khởi động lại, gateway ghi telemetry tiếp (20/20 request vào `requests_ts`). Trace bị
drop trong lúc tắt datadog-agent là đúng thiết kế (fire-and-forget).

### SE-9.2 — `tools/loadtest.py` 50 rps × 30 phút

**Chưa có lần chạy đủ 30 phút hợp lệ trên laptop.** Lần tốt nhất (chế độ Atlas, sau khi sửa pool client):

| Chỉ số | Giá trị (17 phút đầu, 51 016 request) |
| :--- | :--- |
| Success | 51 016 / 51 016 (100%), không retry |
| p99 overhead gateway (luỹ kế) | ~37.5 ms — **chưa đạt** mục tiêu ≤ 10 ms |
| Bài ngắn 25 rps / 1 gateway, VM không có mongo | 8 ms CPU/request, p99 overhead ~12 ms |

Sau phút 17 request không còn tới gateway (gateway log: 1500 req/phút đều đặn tới 10:15 rồi 0) — trùng lúc máy bật
thêm stack khác trong Docker Desktop; máy swap ~5.9GB, load avg ~9 → số liệu không còn đại diện.
`loadtest.py` giờ có deadline mỗi request (`client_timeout`) và tự dừng khi in-flight > `rps × 60` (`aborted`),
không còn treo vô hạn như lần đầu.

Cần chạy lại trên VM (cùng đợt deploy SE-9.3) hoặc laptop rảnh để có số chốt.

## 6. Còn mở

- Deploy `demo` lên VM + TLS + vendor thật (SE-9.3) — cần quyền hạ tầng.
- R4 (fallback khi Cortex chết) — cần thống nhất vị trí `rules`.
