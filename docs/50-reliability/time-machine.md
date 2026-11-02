# Time Machine — Counterfactual Replay

> *"Nếu hôm đó dùng policy khác thì sao?"* Time Machine trả lời câu này bằng con số, trên dữ liệu thật của chính sự cố.

## 1. Mô hình

Một sự cố được tách thành hai phần độc lập:

1. **Demand:** dòng request thật đã đến, lấy từ `requests_ts` (ts, route, priority, session, tokens_in ước lượng).
2. **World:** hành vi của **từng target** theo thời gian, lấy từ `attempts_ts` và `probes_ts`. Với mỗi target và mỗi cửa sổ 5 giây: phân phối outcome (ok, error, rate_limited, quality_fail) và mẫu latency/TTFT thực nghiệm (empirical, theo bucket).

Replay là một **discrete-event simulation**: lần lượt đưa từng request trong Demand qua một **policy ảo** (router, breaker, retry, hedge giống hệt code gateway, vì **dùng chung package `reflex-core`**). Mỗi khi policy ảo gọi target `t` tại thời điểm `τ`, outcome và latency được **lấy mẫu từ World(t, τ)**.

```mermaid
flowchart LR
    D[(Demand<br/>requests_ts)] --> SIM
    W[(World model<br/>attempts_ts + probes_ts<br/>per target × 5s)] --> SIM
    P[Policy variant<br/>reflex-core] --> SIM[DES engine<br/>seeded Monte Carlo ×K]
    SIM --> R[(replays)<br/>delivered SLI · budget · cost<br/>amplification · CI]
```

## 2. Các policy so sánh mặc định

| Variant | Mô tả |
| :--- | :--- |
| `naive` | Một target, không retry. Đây là "app gọi thẳng vendor" |
| `naive_retry` | Retry 3 lần cùng target, không budget. Dùng để thấy thundering herd |
| `static_failover` | Kiểu gateway phổ biến: failover khi gặp 5xx/timeout, không có quality validator, không có breaker theo tỉ lệ |
| `reflex_recorded` | Đúng chuỗi policy version đã áp dụng (lấy từ `policy_history`). Dùng để **hiệu chuẩn** |
| `reflex_variant(x)` | Reflex với tham số khác, ví dụ `breaker.open_ratio`, `retry.budget_ratio`, có/không hedge |

## 3. Hiệu chuẩn — vì sao tin được con số

- Replay `reflex_recorded` rồi so với delivered SLI **thực tế** trong cùng cửa sổ. Sai số được hiển thị ngay cạnh mọi kết quả ("calibration error: 0.3 pp").
- Monte Carlo với K seed (API mặc định 20, bảng §5 dùng 30), báo cáo mean và khoảng 90%.

## 4. Giới hạn (nói thẳng khi pitch)

| Giới hạn | Hệ quả | Giảm thiểu |
| :--- | :--- | :--- |
| World chỉ biết target ở những thời điểm có traffic tới nó | Thiếu dữ liệu về target ít được gọi | Router luôn giữ `explore_min_pct` + probe 15s cho mọi target. Chỗ nào thiếu thì nội suy từ probe và đánh dấu "low confidence" |
| Không mô hình hóa đầy đủ phản ứng của vendor theo tải | Ước lượng thấp tác hại của retry storm | Thêm **capacity model** đơn giản cho target (`capacity_hint`, overflow → 429/latency), được fit từ S5 |
| Demand là cố định | Không mô phỏng người dùng bấm lại khi lỗi | Tùy chọn `user_retry_prob` |

## 5. Output — số thật trên Atlas (K = 30, seed 42)

Incident `INC-202610300552-4a9b57` (silent-brownout, 05:43–05:57 UTC 30/10): 2 234 request thật của `order.extract`,
onset 05:43:01 (attempt hỏng đầu tiên của `vendorA:large`), mitigation 05:54:34, delivered thực tế **99.37%**.

| Policy | Delivered quality (± 90%) | Request hỏng | Budget (1%) | Extra cost | Attempts/request |
| :--- | ---: | ---: | ---: | ---: | ---: |
| naive | 92.44% ± 0.12 | 169 | 100% (breach) | $0.00 | 1.000 |
| naive_retry | 92.44% ± 0.12 | 169 | 100% (breach) | $0.78 | 1.151 |
| static_failover | 93.08% ± 0.14 | 155 | 100% (breach) | $0.04 | 1.008 |
| **reflex_recorded** | **99.95% ± 0.01** | **1.2** | **5.5%** | $0.39 | 1.076 |
| reflex_variant (tắt quality retry) | 93.08% ± 0.14 | 155 | 100% (breach) | $0.04 | 1.008 |

- **Calibration error 0.58 pp** (99.95% mô phỏng vs 99.37% thực tế). Coverage bucket thật của `reflex_recorded`: 91%.
- Ablation: tắt quality retry thì Reflex rơi về đúng mức static failover → giá trị đến từ quality SLI + rescue, không phải từ failover.
- Ba lần chạy khác (`bd0f78`, `30eef5`, `1cb7d5`) cho cùng kết luận: static failover 84.7–92.6%, Reflex 100%, 155–198 request được cứu mỗi sự cố.
- Tái lập: `POST /api/replays {"incident_id": "<key>", "k": 30}`; kết quả kèm `world` (cửa sổ, target, coverage) trong `replays`.

## 6. Hiện thực

- `apps/control-plane/reflex_cp/timemachine/`: `world.py` (build World từ Mongo bằng aggregation, cache trong `replays`), `des.py` (heap event queue), `variants.py`.
- Bảo đảm cùng logic với gateway: router, breaker, retry nằm trong `reflex-core` dưới dạng **pure function, nhận clock và rng được inject**. Gateway truyền clock thật; Time Machine truyền clock ảo.
- API: `POST /api/replays {incident_id, variants, k}` trả về job id. Kết quả được stream qua SSE.
