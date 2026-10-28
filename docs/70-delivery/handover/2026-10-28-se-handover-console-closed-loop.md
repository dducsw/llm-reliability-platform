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
| Kết quả cuối của vòng khép kín | **Chưa quan sát trọn vẹn trên stack thật** (xem §3) |

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
| D1 | Verdict `FAIL` chưa kéo theo rollback/escalate | Hiện: action `failed`, incident ở lại `mitigating`; cần `page_human` hoặc rollback tự động |
| D2 | Failback bước ≥50 chất lượng xấu → dừng im lặng | Nên rollback bước và ghi timeline |
| D3 | `investigations`, `timeline`, `signals.at`, lease `investigating_since` vẫn ghi chuỗi ISO | Cùng loại lỗi #8 nếu sau này `sort` theo các trường này |
| D4 | Monitor Datadog trong `expectations` luôn SKIP | Cần Datadog API hoặc kiểm chứng gián tiếp |
| D5 | Fault selector `vendorA:large` cũng chạm `vendorA:small` | Gateway chỉ gọi `/<vendor>/…`; muốn tách cần header `x-reflex-target` từ adapter |
| D6 | SLO provider mới có `vendorA:large`; target khác chưa có | `seeds/slos.yaml` (TODO còn ở cuối file) |
| D7 | Verifier mặc định `baseline_good=198/200`… chỉ còn dùng khi gọi trực tiếp | Cân nhắc bỏ default |
| D8 | `reflex-mongo migrate` vẫn bỏ qua 3 validator (`$defs`) | Đã ghi ở handover 10-27 (DE) |
| D9 | Cảnh báo `ddtrace … run_operation` | Nhiễu, không ảnh hưởng |

## 5. Thay đổi đã áp lên Atlas dùng chung

- `task migrate`: index `sli_1m` (`scope,key,env,ts`) tạo lại dạng **unique**; thêm unique index cho `sli_1h`.
- Thêm document SLO `target:vendorA:large:quality` vào collection `slos` (cùng nội dung `seeds/slos.yaml`). Không chạy lại
  `task seed` toàn bộ vì sẽ ghi đè policy.
- Chuyển kiểu `t.*` của 8 incident và `created_at`/`updated_at` của 10 action từ chuỗi sang `datetime`.
- Policy `order.extract` đã đưa về trọng số baseline (90/10) với version tăng tiếp (hiện v9+); nhiều incident test đã đặt
  `false_positive`, action chờ duyệt đã `rejected`, `chaos_runs` kẹt đã `completed`.
