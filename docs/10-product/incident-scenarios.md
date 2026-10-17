# Incident Scenarios — Kịch bản sự cố trình diễn

> Đáp ứng mục **#11** của hồ sơ nộp bài. Mỗi scenario là một file `scenarios/*.yaml` (scenario-as-code), chạy bằng `reflex-sim run <name> --seed 42`. Cùng seed thì lần chạy nào cũng cho kết quả giống nhau.

## 0. Thang thời gian demo

SLO thật dùng cửa sổ 30 ngày. Không thể demo 30 ngày, nên mọi scenario chạy với **`time_scale`**, một cấu hình nằm trong `slos` và `scenarios`:

- `slo_window = 30d / time_scale`. Mặc định cho demo: `time_scale = 720`, nghĩa là cửa sổ 1 giờ.
- Các cửa sổ burn rate được nén theo cùng tỉ lệ: `1h → 5s`, `5m → 0.4s`… Không thực tế ở mức này, nên demo dùng **profile riêng `demo`**: SLO window 6h, các burn window 5m/1m (fast) và 30m/5m (slow).
- Dashboard và Console luôn hiển thị nhãn **"DEMO TIME (×N)"** để minh bạch với giám khảo.

Hệ số burn rate (14.4×, 6×) giữ nguyên vì nó là tỉ lệ, không phụ thuộc thang thời gian.

---

## 1. Scenario chính — "The Silent Brownout" 🎯

**Ý tưởng:** provider chính vẫn trả HTTP 200 với latency bình thường, nhưng 35% response của route `order.extract` bị cắt cụt hoặc sai JSON schema. Uptime monitor xanh hoàn toàn. Chỉ Quality SLI thấy sự cố.

### Bối cảnh

- Target chính của `order.extract`: `vendorA:large` (alias trong catalog, ánh xạ tới model thật qua cấu hình).
- Fallback ứng viên: `vendorB:large` (đắt hơn 1,8 lần) và `vendorA:small` (rẻ, chất lượng thấp hơn, đúng schema 97%).
- Traffic: 8 req/s, nhịp ngày đêm (diurnal) mô phỏng, 3 route.

### Timeline (T = thời điểm chaos bắt đầu)

| Thời điểm | Sự kiện | Ai/Cái gì | Bằng chứng nhìn thấy |
| :--- | :--- | :--- | :--- |
| T−10m | Baseline | traffic-gen | Mọi SLO xanh; Delivered = Provider ≈ 99,9% |
| **T+0** | Chaos Proxy bật fault `truncate(p=0.35, route=order.extract, target=vendorA:large)` và `ttft_shift(+180ms)` | chaos | — |
| T+0..2s | Validator `json_schema` fail → **Reflex** retry *quality-aware* sang target điểm cao thứ 2 (`vendorB:large`) | gateway | Span `reflex.attempt[2]` có `retry_reason=quality.schema_invalid` |
| T+30s | Sentinel: Provider Quality SLI của `vendorA:large` burn 23× (5m) và 16× (1m) | control-plane | `health_state.vendorA:large.quality_burn` |
| T+60s | **Datadog Monitor M3** "Quality SLO fast burn" bắn alert. Composite **M9** = M3 ∧ (probe quality của vendorA cũng fail) → kết luận **provider-side** | Datadog | Alert kèm tag `target`, `route`, `diagnosis:provider_side` |
| T+61s | Webhook → control-plane → mở incident `INC-…` (dedup với detector nội bộ). Change Stream → Cortex | control-plane | Console: thẻ incident nhấp nháy |
| T+62s..2m | **Cortex** điều tra: (1) context pack, (2) `$vectorSearch` tìm 2 incident tương tự, sim 0.91, (3) query Datadog Logs `@finish_reason:length` tăng 40×, (4) so sánh token output P50 giảm từ 180 xuống 64 → giả thuyết H1 "*vendorA:large cắt output sớm (server-side max_tokens regression)*", confidence 0.86 | cortex | Investigation doc có 6 evidence item, mỗi item link tới query/log/trace |
| T+2m | Cortex đề xuất `shift_weight(route=order.extract, from=vendorA:large, to=vendorB:large, pct=90)` kèm dự báo chi phí +62%/giờ. Policy engine thấy blast radius thấp, có thể đảo ngược, trong cost ceiling → **auto-approve** | cortex → actuator | `actions` doc: `proposed → approved(auto)` |
| T+2m05s | Actuator ghi `policies` version mới → Change Stream → mọi gateway hot-reload trong <1s | actuator | Datadog Event "Policy v17 applied" phủ lên mọi graph |
| T+2m..5m | **Verifier** so sánh delivered quality SLI 3 phút sau với baseline: Wilson CI + two-proportion test | control-plane | Recovery Proof `PASS`: valid 99,4% [99,1–99,7] so với baseline 99,6% |
| T+15m | Chaos tắt fault. Probe thấy vendorA phục hồi | chaos / prober | Probe quality xanh 10 phút liên tục |
| T+25m | **Staged failback** 10% → 50% → 100%, mỗi bước có gate | actuator | 3 action con, mỗi action có proof riêng |
| T+40m | Incident `resolved`. Cortex soạn postmortem; signature vector được lưu vào Incident Memory | cortex | Console: postmortem với timeline tự động |
| T+41m | **Time Machine** replay: static failover (chỉ failover khi 5xx) so với Reflex | Console | "Static: delivered quality 65,2%, budget đốt 48%. Reflex: 99,4%, budget đốt 4,1%" |

### Vì sao thuyết phục

- Detect: một kiểu sự cố mà monitor thông thường **không thể** thấy.
- Investigate: tương quan metric (quality burn) + log (`finish_reason`) + trace (attempt span) + operational context (incident tương tự, deploy event) + probe (phân biệt provider-side).
- Respond: tự động có guardrail; hồi phục **được chứng minh** bằng thống kê; failback từng bước; định lượng được impact.

---

## 2. Scenario phụ

### S2 — "429 Storm & Thundering Herd"
- **Fault:** `vendorB` trả 429 cho 70% request, có `Retry-After: 2`.
- **Điểm nhấn:** retry ngây thơ khuếch đại tải lên 3,2 lần (hiện trong Time Machine). Reflex dùng **retry budget** (≤10% request) và tôn trọng `Retry-After`; route `ticket.summarize` (P2) bị **shed** trước để giữ P0.
- **Monitor:** M2 Availability burn, M7 Retry amplification.

### S3 — "Tail Latency in the Dark"
- **Fault:** 8% request của `vendorA:large` có TTFT +6s (heavy tail). P50 không đổi.
- **Điểm nhấn:** **Hedged request**: sau P95 TTFT mà chưa có token đầu thì bắn request thứ 2 sang target khác, hủy request chậm hơn. Datadog trace hiện 2 span song song. Có cost guard, chỉ hedge khi có budget.
- **Monitor:** M4 TTFT SLO burn, M5 Anomaly TTFT p99.

### S4 — "It's Us, Not Them" (lỗi do chính mình)
- **Fault:** deploy gateway `version=1.4.0-bad` có bug serialize thêm 450ms (feature flag `slow_codec`).
- **Điểm nhấn:** Datadog **Deployment Tracking** (tag `version`) thấy regression trùng thời điểm deploy. **Probe gọi thẳng provider (bypass gateway) vẫn bình thường** → composite M10 kết luận *gateway-side*. Cortex đề xuất `rollback_flag(slow_codec)` → cần **human approval**, vì đây là thay đổi code path.
- **Ý nghĩa:** cho thấy investigation không phải lúc nào cũng đổ lỗi cho provider.

### S5 — "Cascading Failover"
- **Fault:** vendorA down hoàn toàn (503). vendorB có `capacity=12 rps` (chaos mô phỏng sức chứa).
- **Điểm nhấn:** failover tĩnh dồn 100% traffic → vendorB quá tải → sập dây chuyền. Router của Reflex có **capacity-aware term**: chia traffic giữa vendorB và vendorA:small, đồng thời brownout route P2.

### S6 — "Real-World Replay" (dữ liệu public)
- **Nguồn:** một cửa sổ có tỉ lệ `status=error` cao bất thường trong `llm-bench-data` (CC0), tìm bằng pipeline [A15](../30-data/aggregation-catalog.md#a15).
- **Cách dùng:** Chaos Proxy phát lại *hình dạng* error-rate và latency của cửa sổ đó (đã nội suy từ hourly xuống giây) lên mock target. Minh chứng scenario bám vào sự cố đã xảy ra thật ngoài đời, không phải tự bịa.

---

## 3. Định dạng scenario-as-code

```yaml
# scenarios/silent-brownout.yaml
name: silent-brownout
profile: demo                 # SLO profile (window, burn windows)
seed: 42
traffic:
  rps: 8
  mix: { chat.reply: 0.5, order.extract: 0.35, ticket.summarize: 0.15 }
  diurnal: { amplitude: 0.3, period: 10m }
phases:
  - at: 0s      # warm-up baseline
    duration: 10m
  - at: 10m
    duration: 15m
    faults:
      - target: vendorA:large
        route: order.extract
        type: truncate
        params: { probability: 0.35, keep_ratio: [0.2, 0.5] }
      - target: vendorA:large
        type: ttft_shift
        params: { add_ms: 180, jitter_ms: 60 }
  - at: 25m
    duration: 20m   # recovery + failback observation
expectations:       # dùng làm e2e test & checklist khi quay video
  - monitor: M3_quality_fast_burn
    state: Alert
    within: 90s
  - incident: { route: order.extract, status: resolved }
    within: 45m
  - delivered_sli: { route: order.extract, sli: quality, min: 0.99 }
    window: [12m, 25m]
```

Phần `expectations` vừa là **e2e test** (chạy trong CI ở chế độ mock), vừa là **checklist khi quay video**.
