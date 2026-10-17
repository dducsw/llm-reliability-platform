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
- Monte Carlo với K seed (mặc định 30), báo cáo mean và khoảng 90%.

## 4. Giới hạn (nói thẳng khi pitch)

| Giới hạn | Hệ quả | Giảm thiểu |
| :--- | :--- | :--- |
| World chỉ biết target ở những thời điểm có traffic tới nó | Thiếu dữ liệu về target ít được gọi | Router luôn giữ `explore_min_pct` + probe 15s cho mọi target. Chỗ nào thiếu thì nội suy từ probe và đánh dấu "low confidence" |
| Không mô hình hóa đầy đủ phản ứng của vendor theo tải | Ước lượng thấp tác hại của retry storm | Thêm **capacity model** đơn giản cho target (`capacity_hint`, overflow → 429/latency), được fit từ S5 |
| Demand là cố định | Không mô phỏng người dùng bấm lại khi lỗi | Tùy chọn `user_retry_prob` |

## 5. Output (ví dụ cho S1)

| Policy | Delivered quality | Budget consumed | Extra cost | Attempts/request | Requests hỏng |
| :--- | ---: | ---: | ---: | ---: | ---: |
| naive | 65.1% ± 0.6 | 100% (breach) | $0.00 | 1.00 | 1 247 |
| static_failover | 65.3% ± 0.6 | 100% (breach) | $0.04 | 1.01 | 1 239 |
| **reflex_recorded** | **99.4% ± 0.2** | **4.1%** | $3.12 | 1.21 | **21** |
| reflex (no quality retry) | 96.8% ± 0.4 | 52% | $2.70 | 1.03 | 117 |

*(Đây là số minh họa định dạng. Số thật sẽ được tính khi chạy.)* Dòng cuối là **ablation**, chứng minh tính năng nào tạo ra giá trị.

## 6. Hiện thực

- `apps/control-plane/reflex_cp/timemachine/`: `world.py` (build World từ Mongo bằng aggregation, cache trong `replays`), `des.py` (heap event queue), `variants.py`.
- Bảo đảm cùng logic với gateway: router, breaker, retry nằm trong `reflex-core` dưới dạng **pure function, nhận clock và rng được inject**. Gateway truyền clock thật; Time Machine truyền clock ảo.
- API: `POST /api/replays {incident_id, variants, k}` trả về job id. Kết quả được stream qua SSE.
