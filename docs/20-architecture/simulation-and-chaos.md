# Simulation & Chaos

> Mục tiêu: sự cố **có kiểm soát**, **lặp lại được** và **đủ thật** để giám khảo tin.

## 1. Bốn thành phần

| Thành phần | Vai trò |
| :--- | :--- |
| **traffic-gen** | Sinh workload ShopMate: rps theo nhịp diurnal (sin + noise), mix route, prompt synthetic tiếng Việt lấy từ template + từ điển sản phẩm hư cấu, `x-session-id` để đo blast radius theo phiên |
| **mock-llm** | LLM giả deterministic (seed theo `request_id`). Có profile latency (log-normal TTFT, tps), sinh output đúng theo route (JSON hợp lệ cho `order.extract`, câu tiếng Việt cho `chat.reply`), hỗ trợ SSE streaming, `usage` token |
| **chaos-proxy** | Reverse proxy đặt trước *mọi* upstream (thật và mock). Áp fault theo `chaos_runs` đang active. Hot-reload qua Change Stream |
| **prober** | Mỗi 15s gửi một **golden prompt** (input cố định, có output kỳ vọng) tới mỗi target theo hai đường: qua gateway và gọi thẳng chaos-proxy. So sánh hai đường để biết lỗi nằm ở provider hay ở gateway |

## 2. Fault catalog

| Fault | Params | Tác động | Scenario |
| :--- | :--- | :--- | :--- |
| `error` | `status` (500/502/503), `probability` | Trả lỗi HTTP | S5 |
| `rate_limit` | `probability`, `retry_after_s` | 429 + header | S2 |
| `latency` | `add_ms`, `jitter_ms`, `tail_p`, `tail_ms` | Cộng thêm latency, kể cả heavy tail | S3 |
| `ttft_shift` | `add_ms` | Trễ chunk đầu của stream | S1, S3 |
| `truncate` | `probability`, `keep_ratio` | Cắt output, set `finish_reason=length` | **S1** |
| `corrupt_json` | `probability`, `mode` (drop_brace / wrong_type / missing_field) | JSON sai schema | S1 |
| `empty` | `probability` | `content=""` | — |
| `refusal` | `probability`, `phrase` | Trả câu từ chối mẫu | — |
| `stall` | `after_tokens`, `stall_ms` | Stream dừng giữa chừng | S3 |
| `capacity` | `max_rps`, `overflow` (`429`/`latency`) | Mô phỏng sức chứa hữu hạn | S5 |
| `replay_shape` | `source: bench_ts window`, `scale` | Phát lại hình dạng error/latency thật | S6 |

Mọi fault đều có selector `{target, route?, pct_of_traffic?}`. Response bị chèn fault có header nội bộ `x-chaos-fault`. Gateway **không** đọc header này (để không gian lận). Nó chỉ được ghi vào span tag `chaos.fault` để dùng khi kiểm chứng sau sự kiện, và được loại khỏi input của Cortex (xem [cortex-agent §5](../50-reliability/cortex-agent.md#anti-cheat)).

## 3. Scenario runner

- `reflex-sim run <scenario> --seed N` đọc YAML ([định dạng](../10-product/incident-scenarios.md#3-định-dạng-scenario-as-code)). Mỗi phase ghi vào `chaos_runs` một document `{run_id, phase, faults, starts_at, ends_at}`. Chaos-proxy watch collection này.
- Runner kiểm tra `expectations` trong lúc chạy, xuất báo cáo pass/fail, và gửi Datadog Event `scenario.phase` để giám khảo nhìn rõ trên timeline của dashboard.
- **Chế độ `--fast`** (dùng cho CI): time scale ×60, chạy toàn bộ trên mock, assert theo expectations.

## 4. Import dataset public (`bench_ts`)

1. `reflex-sim bench import --days 60`: shallow clone repo `Jwrede/llm-bench-data`, đọc `data/YYYY-MM/*.jsonl`.
2. Chuẩn hóa: `vendor = model.split('/')[0]`; `meta.route_proto = provider` (luôn là `openai` qua OpenRouter); bỏ record lỗi định dạng; timestamp chuyển thành `Date`.
3. Sắp theo `(meta, timestamp)` rồi `insertMany(ordered:false)` theo batch 1000 (theo khuyến nghị của workshop: cùng nguồn đi cùng nhau, cũ trước mới sau).
4. Dedup ở phía client theo `(model, timestamp)`, vì Time Series không có unique index.
5. Dùng cho: baseline theo giờ trong tuần ([A14](../30-data/aggregation-catalog.md#a14)), tìm sự cố thật ([A15](../30-data/aggregation-catalog.md#a15)), replay hình dạng (S6), và prior cho profile latency của mock-llm.

> **Lưu ý trung thực:** dataset đo bằng prompt "Hi" với output ≤ 20 token qua OpenRouter, nên phản ánh *latency hạ tầng* chứ không phản ánh chất lượng hay chi phí. Tài liệu và slide phải nói rõ điều này.
