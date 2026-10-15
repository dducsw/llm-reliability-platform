# Testing Strategy

| Tầng | Phạm vi | Công cụ | Chạy ở |
| :--- | :--- | :--- | :--- |
| **Unit** | `reflex-core` (routing, breaker, retry, hedge, validators, sli, hist, stats), parser, adapter mapping | pytest, **hypothesis** (property), clock và rng giả | mọi commit |
| **Pipeline golden** | A1–A18 trên fixture | atlas-local, snapshot JSON | mọi commit |
| **Explain** | Không COLLSCAN; TS có bucket filter | `explain("executionStats")` | mọi commit |
| **Integration** | Change Streams resume, dedup race, optimistic concurrency, outbox transaction | atlas-local replica set | mọi commit |
| **Contract** | OpenAI compat (SDK `openai` chính thức gọi vào gateway), webhook payload, event schemas, tool schema của Cortex | pytest | mọi commit |
| **E2E scenario** | 6 scenario `--fast` trên mock + `expectations` | compose trong CI | PR vào main |
| **Cortex eval** | side/cause/action/evidence accuracy, cost, latency | eval harness + LLMObs | thủ công / nightly |
| **Resilience** | Kill Mongo, agent, Cortex, gateway | chaos script | trước demo |
| **Load** | 50 rps, overhead gateway, chi phí Mongo | locust/k6 | trước demo |

## Các property test quan trọng

- Router: với mọi tập input, xác suất của target không eligible bằng 0; tổng xác suất bằng 1; `weight=0` thì không bao giờ được chọn (trừ khi explore đã bị tắt).
- Breaker: không bao giờ chuyển `closed → half_open` trực tiếp; thời gian open không vượt `open_max_s`.
- Retry: số attempt không vượt `max_attempts`; tổng retry trong cửa sổ không vượt budget.
- Rollup: `Σ sli_1h.total == Σ sli_1m.total == count(raw)` trên cùng khoảng thời gian.
- Histogram: `quantile()` nằm trong biên của bucket chứa nó.
- Wilson CI: phủ đúng tỉ lệ thật ~95% trên mô phỏng 10k lần.

## Kiểm chứng quan trọng cho demo

`tests/e2e/test_silent_brownout.py` khẳng định:
1. M3 alert trong ≤ 90s (khi có Datadog thật), hoặc Sentinel mở incident trong ≤ 60s (chế độ mock).
2. Delivered quality ≥ 99% trong phase fault.
3. Action đầu tiên là `shift_weight` với verdict PASS.
4. Incident `resolved` sau failback; Memory tăng thêm 1.
