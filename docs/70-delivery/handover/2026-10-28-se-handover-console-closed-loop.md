# Handover SE — duyệt Console thật, sửa lỗi, nối vòng khép kín — 2026-10-28

Branch: `loibui` · PR #8. Phiên làm việc: dựng stack bằng `task up:atlas`, duyệt toàn bộ Console bằng
Chrome headless, sửa mọi lỗi gặp. Tiếp nối [handover 2026-10-27](2026-10-27-se-handover-duc.md) (§2b R4).

## 0. Trạng thái bàn giao

| Mục | Trạng thái |
| :--- | :--- |
| Unit test | 244 passed, 1 skipped (`task test`); e2e `tests/e2e` 1 passed; ruff, mypy `reflex-core`, `tsc`, lint-imports sạch |
| Chưa chạy | Integration test (`task test:integration`), `task lint` bản đầy đủ trong CI |
| Stack đang chạy | `task up:atlas` (gateway×2, chaos-proxy, mock-llm, control-plane, cortex, console, traffic-gen, prober). Cortex tôi có tắt để thử R4 rồi bật lại |
| Scenario | `silent-brownout` chạy lúc 10:27 (UTC) bị bỏ dở giữa chừng; tự đóng `chaos_runs` (`ends_at`), không cần dọn |
| Kết quả cuối của vòng khép kín | **Đã quan sát trọn vẹn trên stack thật** lúc 17:25 (xem §8) |

## 1. Lỗi đã sửa (mỗi dòng có test hoặc đã quan sát trên stack thật)

| # | Triệu chứng | Nguyên nhân | Sửa |
| :--- | :--- | :--- | :--- |
| 1 | Console trắng, `/api/*` 404/502 | Container `console` là nginx tĩnh, không proxy | `apps/console/nginx.conf.template`: proxy `/api` (+SSE, SPA fallback, token gắn ở nginx), resolver Docker để không 502 khi control-plane đổi IP |
| 2 | `/api/stream` 401 | `EventSource` không gửi được header | Route stream nhận `?token=`; Console thêm token vào URL |
| 3 | War Room crash | Incident seed không có `signals` | `inc.signals?.length` |
| 4 | Chaos Lab 500 | Image control-plane thiếu `reflex-sim` | Dockerfile thêm `--package reflex-sim` |
| 5 | `RollupJob` lỗi mãi → không có SLI mới | `ensure_indexes` so tên, không so `unique`; `sli_1h` thiếu unique index (cần cho `$merge`) | `migrate/indexes.py` drop + tạo lại khi khác `unique`; thêm index `sli_1h` |
| 6 | traffic-gen không tới gateway | CLI bỏ qua `GATEWAY_URL` | `cli.py` dùng `Settings().gateway_url` |
| 7 | Fault của scenario không bao giờ chạy | chaos-proxy không đọc `chaos_runs`; và selector `vendorA:large` không khớp URL `/vendorA` | Proxy tự kết nối Mongo; `injector._target_matches` khớp theo vendor |
| 8 | Incident/action mới **không hiện** ở Console (Approvals luôn trống) | Ghi `created_at`/`t.*` bằng `model_dump(mode="json")` → chuỗi; `sort(...).limit(50)` xếp Date trước String nên bản ghi mới bị cắt | Ghi `datetime` ở `incidents/service.py`, `cortex/tools/propose.py`, `watchdog.py`, `failback.py` |
| 9 | `IncidentService.transition` sẽ lỗi trên Mongo thật | `$push` nằm trong `$set` | Tách `$set` / `$push` |
| 10 | Scenario `--fast` không bao giờ phát hiện được | x60 nén pha lỗi còn 15s < cửa sổ burn thật (30s/180s); phase còn bị cắt 2s | `FAST_SCALE = 5` (≈9 phút); `run(scale=…)` cho test |
| 11 | `expectations` luôn PASS | Stub | Kiểm chứng thật trên Mongo (`incident`, `delivered_sli`); `monitor` Datadog → SKIP; `all_passed` coi SKIP là không-fail |
| 12 | Silent brownout vô hình | Rescue chéo vendor che lỗi: SLI route ~100%, chỉ ledger `target` thấy; seed chỉ có SLO route | Thêm SLO `target:vendorA:large:quality` (kèm `route`) vào `seeds/slos.yaml` |
| 13 | Báo động giả lúc baseline | Route lưu lượng thấp: 1 request lỗi lẻ → burn > 14.4 | `BurnEvaluator`: cần ≥5 mẫu (short) và ≥20 (long) mới fire |
| 14 | Gateway chặn vĩnh viễn (phải restart) | `health` là EWMA chỉ cập nhật khi có attempt; mọi candidate degraded → shed hết → health đứng yên | `SHED_PROBE_INTERVAL_S = 5`: đang shed vẫn cho 1 request thăm dò/route |
| 15 | `chaos_runs` kẹt `active` | Runner chỉ đóng sau khi chờ expectations; tiến trình chết thì không bao giờ đóng | Mỗi phase có `ends_at`; watcher bỏ fault hết hạn; runner đóng trong `finally` ngay sau pha cuối |

Dữ liệu cũ trong Atlas đã chuyển kiểu (8 incident, 10 action) — script một lần, không có trong repo.

## 2. Thay đổi hành vi cần review

- **R4 siết lại** (`guardrails._rules_bounded_reversible`): `actor=rules` chỉ tự áp dụng khi **có** `duration_s ≤ 300`.
  Trước đây `duration_s=None` vẫn qua → rules chuyển 100% traffic sang vendorB **vĩnh viễn** và gateway kẹt. Rules giờ gắn
  `duration_s=300` cho `shift_weight` (`ShiftWeightParams.duration_s` tùy chọn).
- **`ActionExpirer`** (`actuator/expiry.py`, mỗi 10s): action `shift_weight` có `duration_s` hết hạn → `Actuator.rollback`.
  Bỏ qua (và đặt `duration_s=0`) nếu policy đã bị action khác sửa tiếp để không ghi đè. **Đã quan sát thật:** action rules
  `duration_s=30` → policy v6 (vendorA 45%) → tự về 90/10 (v7) sau ~40s.
- **`MitigationLoop`** (`verifier/loop.py`, mỗi 10s) — mới, nối vào `main.py` (`MITIGATION_LOOP_ENABLED`):
  1. `mitigating` + action đã `succeeded`: sau `verify_after_s` (demo 60s / standard 300s) và ≥20 mẫu `sli_1m` route →
     `RecoveryVerifier.verify` bằng số liệu thật (baseline = 15 phút trước `detected_at`) → PASS: `mitigated`.
  2. `mitigated`: sau `failback_stable_s` và probe `probes_ts` của target gốc ổn định → `failback_step` 10 → 50 → 100
     (đi qua policy engine như mọi action; bước ≥50 cần ledger target gốc ≥99%). Bước 100 xong → `resolved`.
  - Transform `failback_step`: `pct` = tỷ trọng của target gốc (100% = trả hết cho target gốc, **không** về 90/10 baseline).
- Console container: token gắn bởi nginx (`REFLEX_CONSOLE_TOKEN`/`REFLEX_LAB_TOKEN` từ `.env`) → ai vào được `:5173` là có quyền
  API. Chỉ dùng cho stack local/dev; stack demo có nginx TLS riêng.

## 3. Đã kiểm chứng và chưa kiểm chứng

**Đã quan sát trên Atlas + trình duyệt thật:** mọi trang Console không lỗi, SSE kết nối; nút Chaos Lab; fault làm ledger
`vendorA:large` tụt (≈70%) trong khi SLI route vẫn 100%; sentinel mở incident từ SLO provider; Cortex đề xuất
`shift_weight` conf 0.4 → `awaiting_approval` → bấm **Duyệt** trên UI → `succeeded`, policy đổi; Cortex tắt → watchdog đề xuất
rules `duration_s=300` → tự áp dụng (10:21:36); `ActionExpirer` rollback thật.

**Chưa quan sát (chỉ unit test):** `MitigationLoop` đi hết verify → failback 10/50/100 → resolved; probe pass-through của
gateway trong lúc đang kẹt; ngưỡng số mẫu tối thiểu. Lần chạy cuối bị dừng giữa chừng. Lần chạy trước đó verifier phán `FAIL`
đúng vì gateway đang kẹt shed (lỗi #14, đã sửa sau đó).

**Cách chạy lại thí nghiệm sạch:** (1) `task up:atlas -- control-plane chaos-proxy gateway-1 gateway-2 cortex console traffic-gen prober`;
(2) đưa policy `order.extract` về baseline nếu đang lệch (xem `policy_history` v1); (3) mở `http://127.0.0.1:5173/lab` →
`silent-brownout` (hoặc `reflex-sim run silent-brownout --fast`); (4) theo dõi Incidents/Approvals, hoặc tắt Cortex để xem
đường rules. Dùng `127.0.0.1`, không phải `localhost` — nếu có `pnpm dev` giữ cổng IPv6 5173, `localhost` sẽ trỏ nhầm.

## 4. Nợ còn lại

| # | Việc | Ghi chú |
| :--- | :--- | :--- |
| D1 | ~~Verdict `FAIL` chưa kéo theo rollback/escalate~~ | **Xong** (`MitigationLoop._on_verify_failed`): rollback action, timeline `verify_failed:rolled_back`, đề xuất `page_human` vào Approvals. Mới có unit test |
| D2 | ~~Failback chất lượng xấu → dừng im lặng~~ | **Xong** (`_rollback_step`): rollback nấc vừa áp + timeline `failback_N:rolled_back`, cooldown `stable_s`. Mới có unit test |
| D3 | ~~`investigations`, `timeline`, `signals.at` ghi chuỗi ISO~~ | **Xong** (`reflex_mongo.serde.to_doc`). Lease `investigating_since` cố ý giữ chuỗi: là điều kiện CAS so sánh bằng, Mongo cắt datetime về ms nên không khớp |
| D4 | ~~Monitor Datadog trong `expectations` luôn SKIP~~ | **Xong**: `DatadogApi.find_monitors` + `_check_monitor` (poll `overall_state` theo `within` thật). SKIP khi thiếu key / monitor không tồn tại / API lỗi / **tất cả `No Data`** (agent tắt); FAIL chỉ khi monitor có dữ liệu mà không lên `Alert` |
| D5 | ~~Fault `vendorA:large` chạm cả `vendorA:small`~~ | **Xong**: orchestrator gắn `target_id`, adapter gửi `x-reflex-target`, chaos-proxy khớp theo target đầy đủ (client không gửi header vẫn khớp theo vendor) |
| D6 | ~~SLO provider chỉ có `vendorA:large`~~ | **Xong**: thêm `vendorB:large` (route `order.extract`), `vendorA:small` (route `support.triage`); đã upsert lên Atlas. Còn TODO availability/latency/ttft cho từng route |
| D7 | ~~Verifier mặc định `198/200`~~ | **Xong**: `RecoveryVerifier.verify` bắt buộc truyền số liệu |
| D8 | `reflex-mongo migrate` vẫn bỏ qua 3 validator (`$defs`) | Đã ghi ở handover 10-27 (DE) |
| D9 | ~~Cảnh báo `ddtrace … run_operation`~~ | **Xong**: compose đặt `DD_TRACE_PYMONGO_ENABLED=false` (đã xác nhận log hết) |

## 5. Thay đổi đã áp lên Atlas dùng chung

- `task migrate`: index `sli_1m` (`scope,key,env,ts`) tạo lại dạng **unique**; thêm unique index cho `sli_1h`.
- Thêm document SLO `target:vendorA:large:quality` vào collection `slos` (cùng nội dung `seeds/slos.yaml`). Không chạy lại
  `task seed` toàn bộ vì sẽ ghi đè policy.
- Chuyển kiểu `t.*` của 8 incident và `created_at`/`updated_at` của 10 action từ chuỗi sang `datetime`.
- Policy `order.extract` đã đưa về trọng số baseline (90/10) với version tăng tiếp (hiện v9+); nhiều incident test đã đặt
  `false_positive`, action chờ duyệt đã `rejected`, `chaos_runs` kẹt đã `completed`.

## 6. Bổ sung phiên 2026-10-28 (chiều)

- Atlas báo `TLSV1_ALERT_INTERNAL_ERROR` khi IP máy dev không nằm trong Network Access → thêm IP hiện tại.
- Prober trong container bỏ qua `Settings` (gọi `localhost`) → mọi probe fail `not_empty`; đã sửa `cli.py`.
- `MitigationLoop._resolve_expired`: mitigation do rules có `duration_s` bị `ActionExpirer` rollback → trước đây incident kẹt
  `mitigated` mãi; giờ `resolved` khi target gốc ổn định. **Đã quan sát thật** (INC-202610281032-1f63e6).
- D1/D2 xong (xem §4). **Chưa quan sát** đường failback 10/50/100 và D1/D2 trên stack thật (cần action Cortex được duyệt tay).
- D3/D5/D6/D7/D9 xong. Còn lại phía SE: D4 (monitor Datadog trong `expectations` luôn SKIP, cần Datadog API) và quan sát trên stack thật
  đường failback 10/50/100 + D1/D2 (cần action Cortex được duyệt tay). D8 và `HealthWriter.budget_remaining` thuộc DE.
- Build Docker gặp `Failed to bytecode-compile` khi build nhiều service song song → build từng service một.
- Integration test (`task test:integration`, 2026-10-28): 9 passed, 3 skipped (stub "chưa hiện thực" của DE: `test_explain`, `test_streams`, `tests/integration/test_migrate`), 0 fail.

## 7. Approvals lỗi 500, gateway nghẹt, Terraform (cuối ngày 2026-10-28)

- **Approvals 500** (`GET /api/actions`): action `page_human` do D1 chèn **không có `_id`** → Mongo gán `ObjectId` → pydantic
  không serialize được. `FailbackOrchestrator.advance` cùng kiểu lỗi (`_id: None`). Sửa: `reflex_core.actions.new_action_id()`
  dùng ở cả hai chỗ + test. Document hỏng trên Atlas đã đổi `_id` sang chuỗi. D1 **đã chạy thật** trên stack: rules `shift_weight`
  → verify FAIL (14/21) → rollback → `page_human` chờ duyệt.
- **Gateway nghẹt dưới traffic-gen (~10 rps)**: không có `datadog-agent` (chế độ Atlas) → mỗi gói DogStatsD resolve DNS thất bại
  ~14ms **ngay trên event loop** → healthz treo, latency 80–220ms, SLI route thưa (vài request/phút) nên verify ra FAIL oan.
  Sửa `reflex_telemetry.setup`: `disable_background_sender=False` (gửi ở thread riêng). Sau sửa p50 ≈ 10ms dưới tải.
  **Lần `silent-brownout` bị nghẹt này không dùng làm bằng chứng được — chạy lại.**
- **Terraform** (`infra/terraform`, state local, gitignored — chỉ nằm trên máy này): đã `apply -target` 4 monitor trên tài khoản
  Datadog (site `ap1`), `env=local`: `M3a`/`M3b` (id 15405613/14), composite `M3_quality_fast_burn` (15405616), `M7_retry_amplification` (15405615).
  Query M3 dựa metric mới `reflex.attempt.quality.{total,pass}` (gateway phát theo **attempt**, gắn target đã gọi — metric request-level
  `reflex.quality.*` gắn `final_target` nên bị rescue chéo vendor che, cùng lỗi #12). Ngưỡng 14.4 × 0.5% = 0.072.
  Chưa tạo webhook (chưa có URL công khai tới control-plane) → monitor chưa gọi được `@webhook-reflex-control-plane-local`.
  Monitor hiện `No Data` vì không có datadog-agent: chạy `task up:atlas -- datadog-agent` để metric tới Datadog.
  **Chưa làm** (thiếu metric nguồn): M6 và probe P_direct/P_via_gw (`reflex.probe.result` chưa được phát), M9/M10, M11
  (`reflex.telemetry.dropped`), M12, M13; M1/M2/M4 cần SLO object (`slos.tf`); dashboards/logs còn TODO.
  Chạy lại: `TF_VAR_env=local TF_VAR_dd_site=<site> TF_VAR_dd_api_key=… TF_VAR_dd_app_key=… terraform plan -target=datadog_monitor.m3`.

## 8. Vòng khép kín chạy trọn trên stack thật (2026-10-28 17:03–17:26 UTC)

`reflex-sim run silent-brownout --fast` với datadog-agent + traffic-gen, sau khi dọn dữ liệu cũ (2 incident → `false_positive`,
2 action → `rejected`, đúng theo ID). Incident `INC-202610281708-fcb2c4`:

| Giờ | Sự kiện |
| :--- | :--- |
| 17:08:19 | Sentinel mở incident (SLO provider `vendorA:large`); Cortex đề xuất `shift_weight` → `awaiting_approval` |
| 17:14:26 | **Người duyệt trên Console** → `succeeded`, policy v14 |
| 17:16:52 | Verify `INCONCLUSIVE` (mẫu ít) rồi `PASS` → `mitigated` |
| 17:17:05 | failback 10% tự áp dụng (policy engine cho qua) |
| 17:18:10 / 17:21:03 | failback 50% **bị rollback 2 lần** (D2): `vendorA:large` có attempt `timeout` 504 → ledger <99% |
| 17:24:21 | failback 50% thành công; 17:25:30 failback 100% |
| 17:25:41 | `resolved` |

- **M3 `Alert` PASS trên Datadog thật** (D4 đã kiểm chứng đầu-cuối). Expectation delivered_sli PASS (1.0000).
- Hai expectation `incident` FAIL **oan** do lỗi của chính ta: incident mới không có `created_at`, và `opened_by` lọc `source` ở cấp incident
  thay vì `signals[0].source`. Đã sửa (commit 52a0a25); **chưa chạy lại scenario để thấy 4/4 PASS**.
- **Policy sau failback 100% là `vendorA:large` 1.0 / `vendorB:large` 0.0** (theo thiết kế "100% = trả hết cho target gốc"), không về 90/10 baseline. Trước khi chạy lại cần đưa `order.extract` về baseline.
- Rollback D2 dựa ngưỡng cứng `good/n < 0.99` với n ≥ 10 → dễ rollback do nhiễu mẫu nhỏ (có timeout thoáng qua do Docker VM 1.9GB dùng chung với project khác). Chấp nhận được vì tự thử lại sau cooldown, nhưng có thể đổi sang cận Wilson.

## 9. Terraform + metric nguồn hoàn chỉnh (2026-10-29)

Metric mới được phát: `reflex.probe.result{target,path,route,result}` (prober), `reflex.telemetry.dropped` (queue gateway đầy),
`reflex.incident.open{source}` (control-plane), `reflex.attempt.quality.{total,pass}` (§7). Control-plane giờ có DogStatsD
(`reflex_telemetry.setup.make_statsd`).

Đã `apply` lên Datadog (site `ap1`, `env=local`, state local gitignored): SLO Delivered availability `chat.reply`, Delivered
quality `order.extract`, Provider quality ×3 target; monitor M1, M2, M3 (a/b + composite), M6, M7, M9, M10, M11, P_direct, P_via_gw.

Bài học từ API validate thật (HCL `validate` không bắt được): composite **không** được chứa composite (M9 dùng M3a && M3b thay vì M3);
burn-rate SLO bắt buộc cửa sổ dài 1h–2d (không có 5m cho demo); `apply -auto-approve` không qua `plan` bị chặn → luôn `plan -out` rồi apply file đó.

**Chưa làm:** M4 (cần gateway phát `reflex.request.under_threshold`), M5 (anomaly), M8 (cost), M12 (chỉ có nghĩa khi webhook Datadog đã nối
vào control-plane, nếu không sẽ báo liên tục), M13 (LLMObs), `datadog_webhook` (cần URL công khai tới control-plane), dashboards, log pipeline.
Expectation monitor của runner giờ theo dõi **song song** từ đầu scenario (trước đó đánh giá sau khi hết fault nên M3 đã về `OK`).

## 10. Lần chạy sạch 4/4 (2026-10-28 18:25–18:35 UTC)

`reflex-sim run silent-brownout --fast` → **ALL PASSED**: M3 `Alert` (Datadog thật), incident mở bởi sentinel, incident `resolved`, delivered_sli 1.0000.
Incident `INC-202610281829-1cb7d5`: Cortex đề xuất → người duyệt 18:30 → verify `PASS` 18:31:36 (không qua `INCONCLUSIVE`) → failback 10/50/100
(18:31:54 / 18:33:04 / 18:33:59, không rollback) → `resolved` 18:34:08.

Sau failback 100% policy `order.extract` là `vendorA:large` 1.0 / `vendorB:large` 0.0 (thiết kế "100% = trả hết cho target gốc"); chạy lại thí nghiệm
cần đưa về 90/10 (snapshot vào `policy_history`, version tăng, CAS) và dọn incident/action sót.

## 11. Việc còn lại (tổng hợp cuối phiên 2026-10-29)

| # | Việc | Chủ | Ghi chú |
| :--- | :--- | :--- | :--- |
| T1 | Webhook Datadog → control-plane (`datadog_webhook`) | SE | Cần URL công khai tới `/hooks/datadog` (nginx TLS của stack demo). Chưa có thì monitor chưa gọi được `@webhook-reflex-control-plane-<env>`; Sentinel vẫn là detector chính. Terraform có sẵn `webhooks.tf`, apply với `webhook_url`/`webhook_token` thật |
| T2 | M12 Detector disagreement | SE | Metric `reflex.incident.open{source}` đã phát. Chỉ tạo monitor sau T1, nếu không sẽ báo liên tục (không có incident nguồn `datadog`) |
| T3 | M4 TTFT SLO burn + SLO Delivered latency | SE | Cần gateway phát `reflex.request.under_threshold{route,threshold}` (xem `monitors-and-slos.md` §1) |
| T4 | M5 (anomaly p99), M8 (cost), M13 (LLMObs Cortex) | SE | M5/M8 dùng metric đã có (`reflex.attempt.latency`, `reflex.cost.usd`) nhưng cú pháp anomaly cần thử trên tài khoản thật (⚠ trong tài liệu); M13 cần xác định metric LLMObs |
| T5 | `dashboards.tf`, `logs.tf` (3 dashboard JSON đã có trong `infra/terraform/dashboards/`; log pipeline + facet) | SE | Vẫn là TODO(P3) |
| T6 | State Terraform nằm local, gitignored | SE | Cân nhắc backend từ xa (S3/Terraform Cloud) hoặc `terraform import` lại khi đổi máy; id hiện tại xem `terraform state list` |
| T7 | Gom 5 SLO của Datadog vào collection `slos.datadog` (output Terraform) | SE | `outputs.tf` còn TODO |
| T8 | Failback 100% để policy ở `vendorA:large` 1.0 / `vendorB:large` 0.0 | SE+DE | Theo thiết kế hiện tại. Cân nhắc trả về trọng số baseline của policy seed để secondary không bị bỏ đói (đổi `failback_step` transform) |
| T9 | D2 dùng ngưỡng cứng `good/n < 0.99`, n ≥ 10 | SE | Dễ rollback do nhiễu mẫu nhỏ; có thể chuyển sang cận Wilson. Hiện tự thử lại sau cooldown nên chưa gây hại |
| T10 | Docker VM 1.9GB dùng chung với project khác | Môi trường | Build song song hay thiếu CPU → `bytecode-compile` lỗi / gateway chậm. Build từng service một; cân nhắc tăng RAM Docker Desktop |
| T11 | ~~`reflex-mongo migrate` bỏ qua 3 validator `$defs` (D8)~~ | DE | **Xong (2026-10-31):** `tools/export_schemas.py` inline đệ quy toàn bộ `$defs`/`$ref` thành JSON Schema phẳng hợp lệ cho MongoDB `collMod`. Đã xuất lại `infra/mongo/validators/*.json` |
| T12 | ~~`HealthWriter` chưa ghi `budget_remaining`~~ | DE | **Xong (2026-10-31):** `BurnEvaluator` tính `budget_remaining` và `HealthWriter` ghi map `{sli: remaining}` vào document `health_state`. Đã có unit test `test_sentinel.py` |
| T13 | ~~3 integration test stub "chưa hiện thực"~~ | DE | **Xong (2026-10-31):** `test_explain` (commit 22314f1), `test_streams.py` (Change Stream consumer + resume token), `test_migrate.py` (idempotent migrate test) đều đã hoàn thiện và gỡ bỏ skip |
| T14 | ~~`rules.py` ở `reflex_core` do DE sở hữu nội dung; review R1–R5 & T8~~ | DE | **Xong (2026-10-31):** DE đã review và chấp thuận toàn bộ R1–R5 và T8. Nâng cấp guardrail `healthy_destination` chặn dứt điểm đề xuất vào target sự cố (§15). Xem §18 |

**Quy ước vận hành đã rút ra (để người sau không dẫm lại):** dùng `127.0.0.1` thay `localhost` cho Console; `terraform plan -out` rồi apply file đó (không `-auto-approve`);
composite Datadog không chứa composite; burn-rate SLO cửa sổ dài ≥ 1h; ghi vào Mongo luôn dùng `reflex_mongo.serde.to_doc` và `_id` chuỗi
(`reflex_core.actions.new_action_id`); thay đổi dữ liệu hàng loạt trên Atlas dùng chung phải theo ID cụ thể.

## 12. Cập nhật 2026-10-30 (đã apply lên Datadog; chưa chạy stack thật)

Đã qua unit test và **đã apply** lên Datadog (`ap1`, `env=local`); `plan` sau apply = `No changes`:
- T3: gateway phát `reflex.request.under_threshold{threshold:2000}`; SLO Delivered latency `chat.reply` và monitor M4 (burn latency, không phải TTFT cấp request); M10 giờ là `(M1 || M4) && !P_direct && P_via_gw`.
- T4: M5 (anomaly p99 `agile`), M8 (anomaly cost `basic`) — API Datadog đã nhận khi tạo. M13 dùng metric mới `reflex.cortex.investigation{status}` và `.duration` do `CortexAgent` phát (không dùng LLMObs).
- T5: `dashboards.tf` (3 dashboard JSON đã có widget), `logs.tf` (pipeline + log metric `reflex.log.finish_reason`; facet không có resource trong provider).
- T7: output `mongo_slo_links` (khóa = `_id` của `slos`) → `task infra:datadog:sync -- --yes` ghi `slos.datadog` (đã ghi 4 SLO).
  `task seed` ghi đè cả document `slos` → chạy lại sync sau mỗi lần seed. SLO availability/latency `chat.reply` chưa có bản Sentinel nên không được ghi.
- T9: rollback failback chỉ khi cận trên Wilson 95% < 0.99 (`confidently_degraded`).
- T8: `failback_step` mang `baseline` = trọng số target gốc trong snapshot `policy_history` (`version_before` của shift_weight cha);
  nấc pct trả về pct% baseline → 100% về đúng tỷ lệ trước sự cố (vd 90/10), không còn bỏ đói secondary. Thiếu snapshot → hành vi cũ (1.0).
  Thêm field tùy chọn vào `FailbackStepParams` (reflex_core) — tương thích ngược, nên báo DE.

- T1/T2: `datadog_webhook` `reflex-control-plane-local` trỏ tới ngrok static domain `https://lethargy-badly-reforest.ngrok-free.dev/hooks/datadog`
  (biến `REFLEX_WEBHOOK_URL` trong `.env`). Chỉ nhận được khi stack chạy **và** `ngrok http 8090` đang mở.
  M12 = composite XOR của 2 monitor "có signal từ sentinel/datadog trong 10m" trên metric `reflex.incident.signal{source}` (phát cả khi gộp).
- `task infra:datadog:plan` / `:apply` nạp key từ `.env` (TF_VAR_*), plan ra file `tfplan` rồi apply đúng file đó.
- Dashboard JSON phải có `response_format: timeseries` cho request dạng formula và `notify_list: null` (nếu không sẽ diff mãi).
- T10: Docker Desktop đã tăng RAM.

- T6: state trên Terraform Cloud (org/workspace `llm-reliability-platform`, CLI-driven, Execution Mode Local), Cần `terraform login` trên máy mới.

## 13. Lần chạy silent-brownout trên stack thật (2026-10-30 03:55–04:28 UTC)

Policy `order.extract` được đưa về seed 90/10 theo ID (v27) trước khi chạy; không dùng `demo_reset` (xoá hàng loạt trên Atlas dùng chung).
Kết quả runner: M3 `Alert` PASS, incident mở bởi sentinel PASS, delivered quality 1.0000 PASS, `resolved` FAIL — chỉ vì action chờ duyệt tay quá hạn chờ của runner.

Incident `INC-202610300359-af5254`: duyệt tay → verify → failback 10/50/100 **đều mang `baseline=0.9`** → `resolved` 04:27:46;
policy cuối **vendorA 0.9 / vendorB 0.1** (T8 kiểm chứng trên stack thật).

**Bug phát hiện và đã sửa:** webhook Datadog tới được (`200`) nhưng **mở incident thứ hai** `INC-202610300400-6f1c6e` thay vì gộp:
(1) `dedup_key` chứa `slo_id` — Sentinel `target:vendorA:large:quality` ≠ Datadog `dd:<monitor_id>`; (2) Datadog hạ chữ thường tag (`vendora:large`).
Hai `shift_weight` 90% chồng nhau → policy 0.009/0.991. Sửa: `dedup_key = {sli}:{target}:{route}`; hook tra lại tên target trong catalog `targets`
(không phân biệt hoa thường). Dọn theo ID: failback chờ duyệt của incident trùng → `rejected`, incident → `false_positive`.
**Chưa chạy lại scenario để thấy signal `datadog` gộp vào incident của sentinel.**

**Hạn chế T9 quan sát được → đã sửa:** nấc failback 10% bị rollback một lần (04:23) vì vendorA chỉ có 2 mẫu/phút, 1 mẫu lỗi.
Giờ có hysteresis: rollback khi cận trên Wilson < 0.95, tiến nấc khi cận trên ≥ 0.99, ở giữa thì chờ thêm mẫu (`plausibly_healthy`).

**Guardrail mới `no_overlapping_mitigation`** (guardrail thứ 11): `shift_weight`/`downgrade_tier` bị chặn khi một incident **khác** đang mở
đã chuyển traffic (`succeeded`) trên cùng route.

## 14. Chạy lại sau khi sửa dedup (2026-10-30 04:37–04:47 UTC) — 4/4 PASS

`reflex-sim run silent-brownout --fast` → **ALL PASSED**. Incident `INC-202610300441-bd0f78`: sentinel mở 04:41, **signal `datadog` gộp vào
cùng incident 04:42** (không có incident thứ hai), duyệt tay 04:43 → failback 10/50/100 (04:44 / 04:45 / 04:46, `baseline=0.9`, không rollback)
→ `resolved`; policy cuối 0.9/0.1. Lần chạy này **chưa có** hysteresis/guardrail mới (deploy sau, 04:50) — chưa quan sát trên stack thật.
Control-plane cold start ~2 phút với Docker 2.8 GB.

## 15. Lần chạy thứ ba (2026-10-30 05:05–05:28 UTC) — lộ thêm một đường trùng incident

Trước khi chạy: incident `INC-202610300502-e27ab4` do **M3 báo giả** trên `vendorB:large`/`support.triage` (1–4 mẫu/phút sau failback,
không có chaos); Cortex đề xuất chuyển traffic **sang chính target đang báo động** (confidence 0.4, chờ duyệt). Đã từ chối action và đóng
`false_positive` theo ID. Sửa: monitor **M3v** (≥ 20 lần kiểm tra chất lượng trong cửa sổ dài); M3/M9 = … && M3v. Lần chạy sau M3 vẫn `Alert`.
⚠ Cortex đề xuất đích là target đang alert mà `healthy_destination` không chặn (health_state của vendorB vẫn healthy) — cần DE/Cortex xem.

Trong lần chạy: **M7 (retry amplification, group theo route, không có target)** gọi webhook → `dedup_key = quality:*:order.extract` không
khớp incident Sentinel → incident thứ hai `INC-202610300509-28c3dc`; hai `shift_weight` được đề xuất cách nhau 1s nên guardrail
`no_overlapping_mitigation` (khi đó chỉ xét `succeeded`) không chặn; cả hai được duyệt → hai vòng failback giẫm nhau (baseline 0.09 vs 0.9).
Dọn theo ID: failback baseline sai → `rejected`, `INC-202610300508-70a2a3` → `false_positive` (trùng 28c3dc). `28c3dc` failback 10/50/100
baseline 0.9 → `resolved` 05:27, policy 0.9/0.1. Runner: 3/4 (resolved hết hạn chờ trong lúc hai incident giẫm nhau).

Sửa (đã deploy 05:2x, **chưa chạy lại để quan sát**): signal không khớp `dedup_key` mà có route → gộp vào incident đang mở trên route đó
(một route một incident); guardrail tính cả action `proposed/awaiting_approval` của incident khác. Hysteresis 0.95/0.99 chưa được thử thật
(lần này không có nấc nào rơi vào vùng xám/xấu).

Integration test 2026-10-30: 9 passed, 3 skipped (stub DE).

## 16. Lần chạy thứ tư và thứ năm (2026-10-30 05:31–05:57 UTC)

**05:31 — 4/4 PASS.** Một incident duy nhất `INC-202610300535-30eef5` có cả signal `datadog` và `sentinel` (gộp theo route chạy đúng, M7 không
mở incident riêng). Mitigation đi đường rules R4 (`shift_weight` 100%, `duration_s: 300`, tự áp dụng). **Nhưng policy kết thúc 1.0/0.0**:
nấc 10% và 100% không có `baseline`, chỉ nấc 50% có.

Nguyên nhân: trong khoảng 05:28–05:35 có người/tiến trình khác chạy **`reflex-mongo seed`** trên Atlas dùng chung (mọi policy về
`version: 1`, `updated_by` rỗng; `slos.datadog` bị xoá). `policy_history` có hai snapshot `version: 1`; `find_one` theo version không sort
trả bản tùy ý giữa các lần gọi. Sửa: `Actuator.snapshot_before` lấy snapshot mới nhất có `at ≤ execution.applied_at`, dùng cho cả
baseline failback và rollback. Policy `order.extract` đưa về seed theo ID (v6), `slos.datadog` ghi lại bằng `task infra:datadog:sync`.

**05:47 — 3/4.** Một incident (`INC-202610300552-4a9b57`, `datadog`+`sentinel`), Cortex đề xuất (confidence 0.4) → duyệt tay → áp dụng
05:53:25 → failback 10/50/100 **đều `baseline=0.9`** → `resolved` 05:57:17, policy **0.9/0.1**. FAIL ở `delivered_sli` = 0.9778: trong cửa sổ
`--fast` chỉ ~45 request, đúng **1** request rescue sang `vendorB:large` không qua validator (vendorB không có fault) → 44/45. Expectation này
dễ dao động với mẫu nhỏ; cân nhắc tăng traffic hoặc nới cửa sổ cho `--fast`.

Chưa quan sát được: guardrail `no_overlapping_mitigation` thực sự chặn (sau khi sửa dedup không còn incident thứ hai để chặn) và
hysteresis 0.95/0.99 (không nấc nào rơi vào vùng xám/xấu). Cả hai đã có unit test.

**Vận hành:** sau mỗi lần ai đó chạy `task seed` trên Atlas dùng chung phải chạy lại `task infra:datadog:sync -- --yes`.

## 17. Sau merge `loibui` → `main` (2026-10-31)

PR #10 (merge, xử lý conflict với ldduc) và PR #11 (M13 `status:failed`). Terraform đã apply, `plan` = No changes.
- Dashboard của SE (ops/slo/cortex) đã bị xoá khỏi Datadog từ trước; 4 dashboard D1–D4 của ldduc đang tồn tại nên được **import** vào state
  `datadog_dashboard_json.reflex[...]` và cập nhật tại chỗ theo JSON trong repo (ops/slo/cortex = bản SE, mongo = bản ldduc). Bản cũ của ldduc nằm trong git history.
- Metric Cortex: dùng emission của ldduc (`_investigate`) + đường exception của SE với `status:failed`; M13 đếm `status:failed`.
- `delivered_sli` của runner: mẫu < 100 request chỉ FAIL khi cận trên Wilson 95% < `min` (lần 05:47 fail vì 44/45 trong `--fast`).
- Việc SE còn lại: quan sát trên stack thật guardrail `no_overlapping_mitigation` và hysteresis 0.95/0.99; cần `ngrok http 8090` khi muốn Datadog gọi webhook.
- Cortex đề xuất chuyển traffic sang target đang alert mà `healthy_destination` không chặn (§15) — chờ DE/Cortex.


## 18. DE hoàn tất T11–T14, duyệt R1–R5 & T8, đóng nợ kỹ thuật (2026-10-31)

Đức (DE) đã rà soát và xử lý toàn bộ các hạng mục tồn đọng kỹ thuật phía DE:

1. **T11 / D8 — Inlined MongoDB `$jsonSchema` (`$defs` / `$ref`)**:
   - `tools/export_schemas.py` đệ quy inline toàn bộ `$defs`/`$ref` sang schema phẳng cho MongoDB 8.x `collMod`.
   - Sinh lại thành công `actions.json`, `incidents.json`, `policies.json`. Không còn lỗi `Unknown $jsonSchema keyword: $defs`.

2. **T12 — `HealthWriter` ghi `budget_remaining` vào `health_state`**:
   - `apps/control-plane/reflex_cp/sentinel/burn.py`: `BurnEvaluator` tính `budget_remaining(g_l, t_l, objective)` cho từng SLO.
   - `apps/control-plane/reflex_cp/sentinel/health.py`: `HealthWriter` ghi nhận `budget_remaining: { quality: ..., availability: ... }` vào document `health_state`.
   - Bổ sung unit test kiểm chứng trong `test_sentinel.py`. Guardrail `blast_radius` đã có đủ dữ liệu kích hoạt nới bậc theo budget.

3. **T13 — Hoàn thiện toàn bộ Integration Test Stubs**:
   - `packages/reflex-mongo/tests/test_streams.py`: Gỡ skip; test `StreamConsumer` nhận event change stream, ghi checkpoint token vào `stream_checkpoints`, và resume thành công.
   - `tests/integration/test_migrate.py`: Gỡ skip; test `_migrate` CLI chạy 2 lần liên tiếp (idempotency), kiểm tra đầy đủ collections, Time Series, và validators.
   - `packages/reflex-mongo/tests/test_migrate.py`: Thêm test case `test_validators_applied_without_defs_error`.

4. **T14 — Phê duyệt Contract R1–R5 & T8; Sửa Guardrail `healthy_destination` (§15)**:
   - **R1** (`ProposedBy.confidence`): Chấp thuận.
   - **R2** (`time_scale` trong phase runner): Chấp thuận.
   - **R3** (root `conftest.py` clear tokens): Chấp thuận.
   - **R4** (`rules.py` chuyển sang `reflex_core` & watchdog fallback): Chấp thuận kiến trúc pure rules + watchdog lease CAS.
   - **R5** (`dropDatabase` trong `it_db`): Chấp thuận.
   - **T8** (`FailbackStepParams.baseline`): Chấp thuận.
   - **Fix §15:** Cập nhật `_healthy_destination` trong `guardrails.py` chặn dứt điểm hành vi chuyển traffic sang chính nguồn (`dest == from`) hoặc vào target đang chịu sự cố của `incident`. Thêm 2 unit test trong `test_guardrails.py`.

5. **Kết quả kiểm thử & Nghiệm thu Giám khảo (J-9.1)**:
   - `tools/judge_verify.py`: 100% PASS (MTTD 58s, Dual-Ledger 99.4% vs 65.0%, Recovery Proof Wilson 95% pass, Zero COLLSCAN).
   - Test suite: 298 passed, 1 skipped (test_events stub).
   - Ruff linter: All checks passed.
