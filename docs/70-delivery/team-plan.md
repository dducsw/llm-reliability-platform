# Phân công & Kế hoạch hiện thực cho 2 người

> Bổ sung cho [implementation-plan](implementation-plan.md): tài liệu đó sắp **phase theo phụ thuộc kỹ thuật**, tài liệu này chia các phase thành **hai làn chạy song song** cho hai thành viên, kèm điểm bàn giao giữa hai làn. Các sửa đổi thiết kế trước khi code nằm ở [design-review-v1](../00-strategy/design-review-v1.md) (mã `F*`, `I*`).
>
> | Vai | Người | Làn |
> | :--- | :--- | :--- |
> | **DE** — Data Engineer | Lê Đình Đức | `DE-*` |
> | **SE** — Software Engineer | Bùi Hữu Lợi | `SE-*` |
> | Cả hai | — | `J-*` (joint) |

---

## 1. Nguyên tắc chia việc

**Một câu:** *DE sở hữu mọi thứ biến dữ liệu thành con số và quyết định dựa trên con số. SE sở hữu mọi thứ nằm trên đường đi của request và process.*

| DE sở hữu | SE sở hữu |
| :--- | :--- |
| MongoDB: migrate, data model, index, validator, search index | Gateway: API, adapter, engine, telemetry writer, policy store |
| Pipeline A1–A18, read-model cho Console | `reflex-core` request-path: routing, breaker, retry, hedge, validators |
| SLO math, Sentinel, incident lifecycle, Verifier, thống kê | Control-plane runtime: app, BFF, SSE, webhook, actuator, policy engine |
| Workload & scenario: traffic-gen, scenario runner, expectations, bench import | Upstream giả lập: mock-llm, chaos-proxy, prober |
| Incident Memory, context pack, rule classifier, eval harness | Cortex runtime: agent loop, tools, evidence validator, LLMObs |
| Time Machine engine (world, DES, calibration) | Console (toàn bộ SPA) + màn hình Time Machine |
| Datadog-as-code: SLO, monitor, dashboard, log pipeline | Instrumentation: ddtrace, structlog, DogStatsD, LLMObs; webhook.tf |
| Benchmark, số liệu Impact cho slide | Hạ tầng: repo, CI, compose, deploy VM/TLS, resilience test |

Vì sao chia như vậy:
1. **Ít điểm chạm.** Hai làn chỉ giao nhau qua **contract** (Pydantic event, collection, metric, pipeline registry, read-model). Không ai phải sửa file của người kia.
2. **Đúng sở trường, đúng rubric.** Giám khảo MongoDB chấm data model và pipeline (DE). Giám khảo Datadog chấm tagging, correlation và monitor; phần này chia đôi tự nhiên giữa instrumentation (SE) và monitor/dashboard (DE).
3. **Không ai bị chặn.** DE có fixture generator ([I2](../00-strategy/design-review-v1.md#improvements)) nên viết pipeline trước khi gateway tồn tại. SE có pipeline registry stub nên viết Cortex tool trước khi pipeline xong.

### Bảng sở hữu theo đường dẫn (reviewer = người còn lại)

| Đường dẫn | Owner | Ghi chú |
| :--- | :---: | :--- |
| `packages/reflex-core/{events,ids,policy,actions}.py` | SE | **Contract**, DE review bắt buộc |
| `packages/reflex-core/{routing,breaker,retry,hedge}.py`, `validators/` | SE | Pure, clock/rng inject ([I1](../00-strategy/design-review-v1.md#improvements)) |
| `packages/reflex-core/{sli,hist,stats}.py` | DE | |
| `packages/reflex-mongo/**` | DE | `streams.py`, `leases.py` giao sớm cho SE |
| `packages/reflex-telemetry/**` | SE | `metrics.py` (catalog tên metric) là contract |
| `apps/gateway/**` | SE | |
| `apps/control-plane/reflex_cp/{sentinel,incidents,verifier,timemachine}` | DE | |
| `apps/control-plane/reflex_cp/{api,hooks,actuator,policy_engine,outbox,main.py}` | SE | |
| `apps/cortex/reflex_cortex/{context_pack,rules}.py`, `eval/` | DE | |
| `apps/cortex/reflex_cortex/{agent,evidence,main}.py`, `tools/`, `prompts/` | SE | |
| `apps/sim/reflex_sim/{traffic,scenario,bench}` | DE | |
| `apps/sim/reflex_sim/{mock_llm,chaos_proxy,prober}` | SE | |
| `apps/console/**` | SE | |
| `infra/mongo/**` | DE | |
| `infra/datadog/**` | DE | trừ `webhooks.tf` (SE) |
| `infra/compose/**`, `.github/**`, `Taskfile.yml` | SE | |
| `scenarios/**`, `seeds/**` | DE | `golden_prompts.yaml` làm chung |
| `tools/burn_calc.py`, `tools/fixturegen/` | DE | |

---

## 2. Bước 0 — Contract freeze (làm chung, trước mọi thứ)

Hai làn chạy độc lập được là nhờ bước này. Mỗi contract là **một file trong repo kèm test**, không phải thỏa thuận miệng.

| # | Contract | File | Người viết → người duyệt |
| :--- | :--- | :--- | :--- |
| J-0.1 | `RequestEvent`, `AttemptEvent`, `ProbeEvent` (có `v`, outcome enum theo [F2](../00-strategy/design-review-v1.md#f2)) | `reflex_core/events.py` | SE → DE |
| J-0.2 | `Policy` v2 (có `rescue` theo [F3](../00-strategy/design-review-v1.md#f3)), `ActionSpec`, `Action` | `reflex_core/policy.py`, `actions.py` | SE → DE |
| J-0.3 | Tên collection, shape `sli_1m` (3 scope: `target`, `route`, `target_route`), `health_state`, `incidents` | `reflex_mongo/collections.py` + `docs/30-data` | DE → SE |
| J-0.4 | Pipeline registry: `def build(params: AXXParams) -> list[dict]`, `PIPELINES: dict[str, PipelineSpec]` (id, params model, collection, mô tả) | `reflex_mongo/pipelines/registry.py` (stub trả `[]`) | DE → SE |
| J-0.5 | Catalog tên metric + tag chuẩn | `reflex_telemetry/metrics.py`, `tags.py` | SE → DE |
| J-0.6 | Read-model signature cho từng màn hình Console (hàm async trả Pydantic model) | `reflex_mongo/readmodels/__init__.py` (stub) | DE → SE |
| J-0.7 | `CLAUDE.md` ở root + mỗi package (quy ước, lệnh test, ranh giới import, "không sửa file của owner khác") | `CLAUDE.md` | Cả hai |

**Done khi:** stub import được, `pytest` xanh, JSON Schema export từ Pydantic chạy được. Sau mốc này, đổi contract phải qua PR có người kia duyệt.

---

## 3. Lộ trình theo phase — hai làn song song

Ký hiệu cột **Cần**: task phải xong trước. `⇄` là điểm bàn giao giữa hai làn.

### P0 — Foundations

| ID | Làn | Hạng mục | Cần | Done khi |
| :--- | :---: | :--- | :--- | :--- |
| SE-0.1 | SE | Monorepo uv + pnpm + Taskfile, Dockerfile multi-stage, compose (atlas-local, dd-agent), CI (ruff, mypy, pytest, gitleaks, import-linter) | — | `task up` xanh, PR mẫu xanh |
| SE-0.2 | SE | `reflex-telemetry.setup()`: ddtrace, structlog JSON, DogStatsD, LLMObs; service "hello" | SE-0.1 | Service hiện trong APM + Logs đúng tag |
| SE-0.3 | SE | Spike Datadog (ngoài repo): LLMObs trên trial, SLO burn alert, composite, webhook custom header, Cloudflare Tunnel | — | Ghi kết quả vào ADR mới |
| DE-0.1 | DE | `reflex-mongo migrate`: TS (granularity, TTL), index, validator sinh từ Pydantic, search index JSON; idempotent | J-0.3 | Chạy 2 lần không lỗi; integration test |
| DE-0.2 | DE | Spike Mongo: tier Atlas (M0/Flex/M10), Change Streams, giới hạn search index, `$vectorSearch` trên atlas-local, `$rankFusion`, `$percentile` | — | Addendum cho ADR-0002 |
| DE-0.3 | DE | **Fixture generator** (`tools/fixturegen`): sinh attempts/requests/probes có seed, inject fault giống chaos | J-0.1 | Sinh 10M doc; dùng cho test pipeline |
| DE-0.4 | DE | **`tools/burn_calc.py`** + test khóa timeline S1 ([F4](../00-strategy/design-review-v1.md#f4)) | — | In ra thời điểm alert theo lý thuyết cho cả 6 scenario |
| J-0.8 | J | Atlas cluster + Network Access; Datadog **org A** (dev); key scope tối thiểu | — | `.env` local, không commit |

### P1 — Data plane MVP ‖ Data foundation

| ID | Làn | Hạng mục | Cần | Done khi |
| :--- | :---: | :--- | :--- | :--- |
| DE-1.1 | DE | `streams.py` (Change Stream consumer, checkpoint, resume) + `leases.py` | DE-0.1 | Test kill/restart không mất event ⇄ **giao SE trước SE-1.5** |
| SE-1.1 | SE | Adapters `mock`, `openai_compat`, `anthropic`: stream + non-stream, chuẩn hóa `usage`, `finish_reason` | J-0.1 | Contract test bằng SDK `openai` chính thức |
| SE-1.2 | SE | mock-llm: deterministic theo `request_id`, output theo route, SSE, latency profile | SE-1.1 | Golden test; prior latency lấy từ DE-1.3 khi có |
| SE-1.3 | SE | Gateway engine v0 + `/v1/chat/completions` + header `x-reflex-*` + error envelope | SE-1.1 | `curl` stream chạy được |
| SE-1.4 | SE | Telemetry writer: bounded queue → `insertMany(ordered:false)` batch; DogStatsD; log; LLMObs llm span | SE-1.3, DE-0.1 | Overhead p99 < 3ms (benchmark) |
| SE-1.5 | SE | Policy store: load + Change Stream hot-reload + file snapshot | DE-1.1 | Update policy → đổi hành vi < 1s |
| DE-1.2 | DE | Seeds: `targets`, `policies`, `slos` **materialized** ([F5](../00-strategy/design-review-v1.md#f5)), golden prompts (cùng SE) | J-0.2 | `task seed` |
| DE-1.3 | DE | Bench importer (`bench_ts`) + A14 baselines + A15 tìm sự cố thật | DE-0.1 | 60 ngày đã import; top-10 cửa sổ sự cố thật ⇄ **giao prior latency cho SE-1.2** |
| DE-1.4 | DE | A1, A2 (3 scope, theo F1 & F2), A3 + watermark | DE-0.3 | Property test: rollup == tính trên raw |
| DE-1.5 | DE | Harness `test_explain.py` dùng chung cho mọi pipeline | DE-1.4 | TS có bucket filter; không COLLSCAN |

### P2 — Simulation & Chaos

| ID | Làn | Hạng mục | Cần | Done khi |
| :--- | :---: | :--- | :--- | :--- |
| SE-2.1 | SE | chaos-proxy + 11 fault + hot-reload `chaos_runs` + propagate trace | SE-1.2, DE-1.1 | Mỗi fault có unit test |
| SE-2.2 | SE | Prober `direct` / `via_gateway`, 15s | SE-2.1 | `probes_ts` có dữ liệu |
| DE-2.1 | DE | traffic-gen ShopMate: diurnal, mix, session, priority, prompt tiếng Việt synthetic | SE-1.3 | rps/mix cấu hình được |
| DE-2.2 | DE | Scenario runner: YAML schema, phase → `chaos_runs`, expectations checker, event `scenario.phase`, `--fast` | SE-2.1 | `reflex-sim run silent-brownout --fast` |
| DE-2.3 | DE | 6 scenario YAML kèm `ground_truth` (số kỳ vọng lấy từ `burn_calc`) | DE-0.4 | Chạy S1 *chưa có Reflex* thấy quality tụt |

### P3 — SLO engine + Datadog as code → 🟢 G1

| ID | Làn | Hạng mục | Cần | Done khi |
| :--- | :---: | :--- | :--- | :--- |
| DE-3.1 | DE | A4 sinh từ danh sách SLO (cửa sổ ngắn trên raw, F4), A5, A6, A7 (+`$unionWith` target kỳ vọng) | DE-1.4 | Golden + explain test |
| DE-3.2 | DE | Sentinel tick: lease, rollup, burn, `health_state`, gauge `reflex.slo.*`, mở incident | DE-3.1, SE-0.2 | Incident mở ở ≈ thời điểm `burn_calc` dự báo |
| DE-3.3 | DE | Incident repo: dedup (partial unique), signals merge, timeline | DE-0.1 | Race test: 2 nguồn → 1 incident |
| DE-3.4 | DE | Terraform: SLO objects, M1–M7, composite M9/M10, log pipeline + facets + log-based metric, dashboard D1 v1 | SE-1.4 | `terraform plan` sạch; `apply` lên org A |
| SE-3.1 | SE | Control-plane app: module loader, lease, outbox worker | DE-1.1 | Module khởi động theo leader |
| SE-3.2 | SE | `/hooks/datadog` (token, idempotent) + nginx/Tunnel + `webhooks.tf` | SE-3.1, DE-3.3 | Contract test payload mẫu |
| SE-3.3 | SE | `POST /api/actions` + actuator tối thiểu (`shift_weight`) | SE-1.5 | Action thủ công → policy đổi → dashboard hồi phục |

**🟢 G1 — Compliance gate (J-G1):** chạy S1 end-to-end; đối chiếu [competition-strategy §3](../00-strategy/competition-strategy.md#3-checklist-yêu-cầu-bắt-buộc--nơi-đáp-ứng); **quay video nháp**; teach-back lần 1 (mỗi người trình bày 10 phút phần của người kia).

### P4 — Reflex loop (SE) ‖ Investigate pipelines (DE)

| ID | Làn | Hạng mục | Cần | Done khi |
| :--- | :---: | :--- | :--- | :--- |
| SE-4.1 | SE | `routing.py`: eligibility + score + softmax + explore; `Q(t)` EWMA theo (target, route) | J-0.2 | Property test (xác suất = 1, không eligible → 0) |
| SE-4.2 | SE | `breaker.py` sliding window + backoff | — | State machine test với clock giả |
| SE-4.3 | SE | `retry.py`: phân loại, **hai budget** (transient + rescue, F3), backoff, Retry-After, deadline | — | S2 unit: retry ≤ 10%; S1 unit: rescue đủ chi phí |
| SE-4.4 | SE | Validators + quality rescue | — | Mỗi validator < 2ms |
| SE-4.5 | SE | Hedging + cancel + cost guard | SE-4.1 | Trace có 2 span song song |
| SE-4.6 | SE | Load shedding + brownout | SE-4.1 | Header + metric `sheds` |
| SE-4.7 | SE | `health_sync` (đọc `health_state` 10s) | DE-3.2 | — |
| DE-4.1 | DE | A8 (sinh theo SLI, F9), A11, A12 (+ lift so baseline), A13, A16, A17, A18 | DE-1.4 | Golden + explain test |
| DE-4.2 | DE | `stats.py` (Wilson, two-proportion, cỡ mẫu tối thiểu) + `hist.quantile` | — | Wilson coverage ≈ 95% trên 10k mô phỏng |
| DE-4.3 | DE | Dashboard D1 đầy đủ + D2 (dual-ledger theo rate, F7) | DE-3.4 | Widget "Delivered vs Provider" có số thật |

**Done P4 (J):** S1 có Delivered quality ≥ 99% khi **chưa có** action nào từ control plane; S2 có amplification ≤ 1.2.

### P5 — Incident → Action → Verify

| ID | Làn | Hạng mục | Cần | Done khi |
| :--- | :---: | :--- | :--- | :--- |
| SE-5.1 | SE | Action catalog + JSON Schema params | J-0.2 | — |
| SE-5.2 | SE | Policy engine + 10 guardrail | SE-5.1 | Bảng test pass/fail cho mỗi guardrail |
| SE-5.3 | SE | Actuator: optimistic concurrency, `policy_history`, outbox transaction, Datadog Events | SE-3.3 | Test xung đột version |
| DE-5.1 | DE | Verifier: 3 đại lượng (F6), INCONCLUSIVE → kéo dài, FAIL → rollback | DE-4.1, DE-4.2 | Unit test với số liệu đã biết |
| DE-5.2 | DE | Failback 10/50/100 có gate | DE-5.1, SE-5.3 | e2e S1 |
| DE-5.3 | DE | Rule-based classifier (fallback của Cortex) → `propose_action` | DE-4.1 | Không cần LLM vẫn chạy hết vòng |
| DE-5.4 | DE | KPI (MTTD/MTTA/MTTM/MTTR, impact) ghi vào incident | DE-4.1 | — |

**Done P5 (J):** S1, S2, S3, S5 chạy hết vòng **tự động** bằng rule engine, có Recovery Proof.

### P6 — Console (SE) ‖ Read models (DE)

| ID | Làn | Hạng mục | Cần |
| :--- | :---: | :--- | :--- |
| DE-6.1 | DE | Read-model cho Pulse, Incidents, War Room, Approvals, Policies (hàm query, SE chỉ gọi) ([I3](../00-strategy/design-review-v1.md#improvements)) | J-0.6 |
| DE-6.2 | DE | Metadata cho Query Explorer: pipeline JSON, lần chạy cuối, explain summary | DE-1.5 |
| DE-6.3 | DE | UMAP 2D cho màn hình Memory (tính sẵn) | DE-7.1 |
| SE-6.1 | SE | BFF REST + SSE (fan-out Change Streams, `Last-Event-ID`) + OpenAPI → TS types | DE-1.1 |
| SE-6.2 | SE | Pulse | DE-6.1 |
| SE-6.3 | SE | **War Room** (signals + overlay, timeline, actions, guardrails, proof, deep link) | DE-6.1 |
| SE-6.4 | SE | Approvals | SE-5.2 |
| SE-6.5 | SE | Policies timeline, Chaos Lab, Query Explorer | DE-6.2 |
| SE-6.6 | SE | Chế độ trình diễn (`?present=1`, narration ribbon, demo clock) | SE-6.3 |

### P7 — Cortex + Incident Memory → 🟢 G2

| ID | Làn | Hạng mục | Cần | Done khi |
| :--- | :---: | :--- | :--- | :--- |
| DE-7.1 | DE | A9 signature (làm mượt, vector dịch ±1 phút) + vector index + A10 | DE-4.1 | Integration test trên atlas-local |
| DE-7.2 | DE | `task memory:bootstrap`: 40–60 biến thể game day, có cả action sai | DE-5.3, DE-2.2 | ≥ 40 incident trong memory |
| DE-7.3 | DE | Context pack (deterministic) | DE-4.1, DE-7.1 | Snapshot test |
| DE-7.4 | DE | Eval harness `task cortex:eval` + recall@3 leave-one-out + ablation có/không Memory | DE-7.2 | `cortex-eval.md` |
| DE-7.5 | DE | Postmortem Atlas Search index + hybrid recall (`$rankFusion` hoặc RRF) | DE-0.2 | — |
| DE-7.6 | DE | Dashboard D3 + M13 (Terraform) | SE-7.4 | — |
| SE-7.1 | SE | Tools: `mongo.run_pipeline` (allowlist từ registry), `dd.*` client + sanitizer, `propose_action` | J-0.4 | Contract test cho từng tool |
| SE-7.2 | SE | Agent loop **qua gateway** (route `cortex.reason`), structured output, giới hạn tool call và thời gian, fallback sang rules | SE-7.1, DE-7.3 | — |
| SE-7.3 | SE | Evidence validator + hạ confidence | SE-7.2 | Test với output giả có ref sai |
| SE-7.4 | SE | LLMObs: agent / workflow / tool / llm span | SE-7.2 | Trace đầy đủ trên LLMObs |
| SE-7.5 | SE | Postmortem generator | SE-7.2, DE-7.5 | — |
| SE-7.6 | SE | Test prompt injection (log độc hại) | SE-7.3 | Policy engine chặn |

**🟢 G2 — Differentiation gate (J-G2):** S1 chạy hết vòng với Cortex; recall@3 ≥ 0.8; video bản 2; teach-back lần 2.

### P8 — Time Machine

| ID | Làn | Hạng mục | Cần |
| :--- | :---: | :--- | :--- |
| DE-8.1 | DE | World builder (attempts_ts + probes_ts, cửa sổ 5s; đánh dấu "low confidence" chỗ thiếu dữ liệu) | DE-4.1 |
| DE-8.2 | DE | DES engine + 5 variant + Monte Carlo K seed + calibration error | DE-8.1, SE-4.1…4.3 (pure) |
| DE-8.3 | DE | Capacity model fit từ S5 | DE-8.2 |
| SE-8.1 | SE | `POST /api/replays` (job + SSE) + màn hình Time Machine + bảng ablation | DE-8.2 |

*(Bước refactor 8.1 cũ đã bỏ, vì `reflex-core` pure từ đầu, theo I1.)*

### P9 — Hardening & Demo kit → 🟢 G3

| ID | Làn | Hạng mục |
| :--- | :---: | :--- |
| SE-9.1 | SE | Chaos lên chính Reflex: kill Mongo / agent / Cortex / 1 gateway; xác nhận fail-safe |
| SE-9.2 | SE | Load test 50 rps × 30 phút (overhead gateway) |
| SE-9.3 | SE | Deploy `demo`: VM + TLS + Atlas + vendor thật; `task demo:reset` |
| DE-9.1 | DE | Benchmark pipeline 10M doc → `docs/30-data/benchmarks.md` |
| DE-9.2 | DE | Soak 24h: kiểm tra rollup, TTL, chi phí Mongo; chốt số Impact cho slide |
| DE-9.3 | DE | Datadog **org B** (demo/chấm điểm, F8): `terraform apply` + kiểm tra mọi monitor |
| J-9.1 | J | **`task judge:verify`** → Proof Report ([I4](../00-strategy/design-review-v1.md#improvements)) |
| J-9.2 | J | README quickstart, declarations, `THIRD_PARTY.md` |
| J-9.3 | J | Kịch bản video + quay + dựng; slide; Q&A bank |

**🟢 G3 — Submission gate:** checklist 12 mục ([submission-kit](submission-kit.md)); quyền truy cập cho giám khảo đến 22/11/2026; teach-back cuối (mỗi người trả lời toàn bộ Q&A bank).

---

## 4. Điểm bàn giao (⇄) — ai chờ ai, và cách không phải chờ

| Bàn giao | Từ → đến | Nếu chưa có thì làm gì |
| :--- | :--- | :--- |
| `streams.py`, `leases.py` | DE → SE (policy store, BFF, chaos) | DE làm **đầu tiên** trong P1. SE tạm dùng polling 1s sau một interface chung |
| Event thật từ gateway | SE → DE (pipeline) | DE dùng fixture generator (DE-0.3) |
| Pipeline registry | DE → SE (Cortex tools, Query Explorer) | Stub trả `[]` từ J-0.4 |
| Read-model | DE → SE (Console) | Stub trả dữ liệu fixture cố định |
| Router / breaker / retry pure | SE → DE (Time Machine) | DE dựng DES với policy `naive` trước |
| Metric thật trên Datadog | SE → DE (Terraform) | DE viết monitor theo catalog J-0.5; `plan` chạy được, chỉ `apply` cần metric |
| Context pack | DE → SE (agent loop) | SE dùng context pack snapshot từ test |

---

## 5. Làm việc với AI (Claude Code) — để nhanh mà vẫn hiểu

1. **`CLAUDE.md` là luật chung** (J-0.7): stack, lệnh test, ranh giới import, owner của từng thư mục, quy ước commit. Agent nào cũng đọc file này trước.
2. **Mỗi task một git worktree, một branch** (`de/3.1-burn-rate`, `se/4.3-retry`). Nhiều agent chạy song song mà không giẫm chân nhau.
3. **Prompt cho agent = ID task + link tài liệu + Done-khi.** Ví dụ: *"Làm DE-3.1 theo docs/30-data/aggregation-catalog.md#a4 và design-review-v1 F4; done khi golden test và explain test xanh."* Thiết kế đã đủ chi tiết, nên agent không cần đoán.
4. **Test trước, code sau** với các phần có toán (`sli`, `stats`, `hist`, router, breaker): người viết test, agent viết implementation. Test là bằng chứng rằng người hiểu.
5. **Cross-review bắt buộc:** PR của DE do SE duyệt và ngược lại. Mục đích chính là để **mỗi người hiểu phần của người kia** trước vòng Q&A.
6. **Không merge thứ mình không giải thích được.** Thể lệ yêu cầu khai báo AI, và declaration ghi "đội hiểu toàn bộ giải pháp". Teach-back ở mỗi gate là cách kiểm tra.
7. **Tài liệu đi cùng code:** pipeline mới thì cập nhật catalog, monitor mới thì cập nhật runbook, đổi contract thì viết ADR mới.

---

## 6. Definition of Done theo vai (cộng thêm DoD chung ở [implementation-plan](implementation-plan.md#definition-of-done-chung-mọi-hạng-mục))

| DE | SE |
| :--- | :--- |
| Pipeline có golden test + explain test, ID đã đăng ký trong registry | Code request-path có property test; không chặn I/O trên request path |
| Số liệu trong docs và slide sinh từ code (burn_calc, judge:verify), không gõ tay | Span, metric, log đúng catalog tag (J-0.5) |
| Monitor mới có runbook, có `terraform plan` sạch | Endpoint mới có trong OpenAPI, types của Console đã sinh lại |
| Thay đổi data model đã cập nhật validator và migration | Service mới có healthcheck trong compose và chạy được bằng `task up` |
