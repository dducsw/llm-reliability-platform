# Datadog Dashboards

Ba dashboard, tất cả đều có template variable `$env`, `$route`, `$target`, kèm event overlay `source:reflex`.

## D1 — "Reflex · Operations" (dashboard chính khi demo)

Bố cục theo đúng ba bước của thể lệ, đọc từ trên xuống dưới.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ DETECT                                                                       │
│ [SLO summary ×4]  [Monitor summary: Reflex/*]  [Open incidents (query value)]│
│ [Delivered vs Provider — timeseries 2 đường, cùng route]  ← hình ảnh chủ đạo│
│ [Burn rate heatmap: slo × window]  [Budget remaining bars per SLO]           │
├──────────────────────────────────────────────────────────────────────────────┤
│ INVESTIGATE                                                                  │
│ [Quality failures by check & target (stacked)]  [finish_reason distribution]│
│ [Latency p50/p95/p99 by target]  [TTFT p99 + anomaly band]                   │
│ [Probe matrix: target × path (direct/via_gw) ok%]  ← chẩn đoán phân biệt     │
│ [Log stream: -@outcome:ok]  [Trace list: errors / slow]                      │
├──────────────────────────────────────────────────────────────────────────────┤
│ RESPOND                                                                      │
│ [Router weights per route (stacked area) + policy events]                    │
│ [Breaker state per target × gateway]  [Retry amplification]  [Sheds]         │
│ [Requests saved by Reflex (count)]  [Cost/h by attempt_kind]                 │
│ [Event stream: policy.applied, recovery.proof]                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Widget đinh:** "Delivered vs Provider". Trong S1, đường Provider quality tụt xuống 65% trong khi đường Delivered gần như phẳng ở 99,4%. Khoảng cách giữa hai đường là giá trị của Reflex, và nó hiện ra mà không cần giải thích bằng lời.

## D2 — "Reflex · SLO & Error Budget"

- Mỗi SLO một hàng: SLO widget (7d/30d hoặc demo window), budget remaining, burn đa cửa sổ, sự kiện incident.
- Bảng "Dual ledger": SLI theo Datadog SLO và SLI theo Sentinel (metric `reflex.slo.*`), kèm cột chênh lệch.
- Cost of reliability: chi phí phát sinh do retry, hedge, failover, phân theo route.

## D3 — "Reflex · Cortex Agent"

- Investigation count, success, p50/p95 duration (`reflex.cortex.*`).
- LLMObs: tokens và cost theo ngày; tool call distribution; error rate.
- "Agent accuracy": evaluation `root_cause_correct` trên các lần chạy scenario.
- Action outcomes: proposed → auto/human → PASS/FAIL (`reflex.action.count`).

## Notebook theo incident (tùy chọn, T3)

Cortex tạo một **Datadog Notebook** cho mỗi incident qua API: tiêu đề, timeline, các graph đã khoanh time range, log query, và kết luận. Link được lưu vào `incident.links.dd_notebook`. Đây là cách để kết quả điều tra nằm lại *ngay trong Datadog* cho SRE dùng tiếp.
