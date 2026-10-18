# SLI · SLO · Error Budget

## 1. Hai ledger: Provider và Delivered

| | Provider SLO | Delivered SLO |
| :--- | :--- | :--- |
| Đo cái gì | Vendor trả gì cho **mỗi attempt** | Người dùng nhận gì cho **mỗi request** (sau retry, hedge, reroute) |
| Scope | `target` | `route` |
| Nguồn | `attempts_ts` (+ probes) | `requests_ts` |
| Dùng để | Router scoring, chẩn đoán, đánh giá vendor | Cam kết với người dùng, alert để page người |
| Câu chuyện | "Vendor A đang xấu" | "Người dùng có bị ảnh hưởng không?" |

> **Gap = Delivered − Provider** là KPI đầu tiên của sản phẩm (`reflex.slo.delivered_vs_provider_gap`).

## 2. SLI definitions (good / valid)

| SLI | Good event | Valid event (mẫu số) | Ghi chú |
| :--- | :--- | :--- | :--- |
| **Availability** | `outcome ∈ {ok, quality_fail}` (served) | mọi request, trừ lỗi client 4xx (trừ 429) và trừ `shed` ở route P2 | 429 tính là bad: vendor không phục vụ được |
| **Latency** | `ok ∧ latency_ms < T` (T trùng biên bucket) | `ok` | SLO dạng tỉ lệ, không dạng "p95 ≤ X" |
| **TTFT** | `ok ∧ ttft_ms < T` | `ok ∧ stream` | Riêng cho route interactive |
| **Quality** | `served ∧ quality.pass` | `served ∧ route có validator` | Validator theo route, xem §3 |

## 3. Quality validators

Điều kiện: rẻ (< 2ms), deterministic, **không dùng LLM-as-judge** trên request path.

| Validator | Áp dụng | Fail khi |
| :--- | :--- | :--- |
| `not_empty` | mọi route | content rỗng hoặc chỉ có whitespace |
| `no_truncation` | mọi route | `finish_reason == "length"` *và* output < `max_tokens` của route × 0.95 *hoặc* JSON chưa đóng |
| `json_schema:<name>` | `order.extract` | `json.loads` lỗi hoặc không khớp JSON Schema (`fastjsonschema`, compile sẵn) |
| `refusal_pattern` | `chat.reply` | regex bộ câu từ chối phổ biến (vi/en) mà prompt không thuộc loại được phép từ chối |
| `lang:vi` | `chat.reply` | tỉ lệ ký tự có dấu tiếng Việt < ngưỡng (heuristic nhanh) |
| `length_bounds` | `ticket.summarize` | số từ ngoài [20, 160] |

Kết quả validator đi vào ba nơi: attempt event (Mongo), metric `reflex.quality.check`, và LLMObs evaluation.

**Streaming:** với route stream, validator chạy trên toàn bộ output sau khi stream kết thúc. Nếu fail thì *không* retry được (client đã nhận nội dung), nên sự cố chỉ được ghi nhận và tính vào SLI. Route `order.extract` không stream nên retry được. Đây là trade-off của thiết kế, được ghi rõ trong tài liệu.

## 4. SLO mặc định (catalog seed)

| SLO id | Objective | Ngưỡng | Window (standard / demo) |
| :--- | :---: | :---: | :---: |
| `route:chat.reply:availability` | 99.5% | — | 30d / 6h |
| `route:chat.reply:ttft` | 99% | < 1000ms | 30d / 6h |
| `route:order.extract:availability` | 99.5% | — | 30d / 6h |
| `route:order.extract:quality` | 99.5% | — | 30d / 6h |
| `route:ticket.summarize:latency` | 95% | < 12000ms | 30d / 6h |
| `target:*:availability` | 99% | — | 30d / 6h |
| `target:*:quality` | 99% | — | 30d / 6h |
| `target_route:*:quality` | 99% | — | 30d / 6h |

Dòng có `*` là **template**. Seed và migrate bung template thành một document cho mỗi target (và mỗi target × route), xem [review F5](../00-strategy/design-review-v1.md#f5).

> **Availability nghĩa là "có response"; quality nghĩa là "response dùng được".** Response bị validator đánh trượt vẫn tính là available ([review F2](../00-strategy/design-review-v1.md#f2)). Nhờ vậy hai SLI độc lập với nhau, và lỗi im lặng chỉ hiện ở quality.

## 5. Burn-rate alerting

`burn = (bad/valid trong cửa sổ) / (1 − objective)`

| Tier | Long | Short | Factor | Ý nghĩa (với 30 ngày) | Hành động |
| :--- | :---: | :---: | :---: | :--- | :--- |
| page | 1h | 5m | 14.4 | 2% budget mất trong 1h | Mở incident P1; Cortex được phép auto-mitigate |
| ticket | 6h | 30m | 6 | 5% budget mất trong 6h | Incident P2; Cortex điều tra, action cần duyệt |
| notice | 3d | 6h | 1 | Đang dùng budget đúng tốc độ "hết vào cuối kỳ" | Ghi nhận, không mở incident |

Profile demo: window 6h; page = **3m/30s**; ticket = 30m/5m. Cửa sổ ≤ 1 phút tính trên raw TS ([A4](../30-data/aggregation-catalog.md#a4)). Thời điểm alert của mỗi scenario được tính bằng `tools/burn_calc.py`, không ước lượng tay ([review F4](../00-strategy/design-review-v1.md#f4)). Thêm điều kiện `min_samples` ở short window (mặc định 30).

## 6. Error budget policy (tự động hóa)

| Budget còn lại | Router & Policy engine tự điều chỉnh |
| :--- | :--- |
| > 50% | Bình thường. Hedging chỉ chạy cho route P0 khi TTFT anomaly |
| 25–50% | Tăng trọng số `w_budget` trong scoring; giảm `retry.budget_ratio` của target đang burn |
| 10–25% | Action có `blast_radius ≤ medium` được auto-approve; bật preemptive hedging cho P0 |
| < 10% | **Protect mode:** shed P2 khi cần; failover preemptive; mọi thay đổi không khẩn cấp (failback 100%) cần người duyệt |
| 0% | SLO breached; bắt buộc có postmortem (Cortex soạn draft) |

<a id="kpi"></a>
## 7. KPI vận hành, định nghĩa thống nhất

| KPI | Định nghĩa | Nguồn |
| :--- | :--- | :--- |
| **MTTD** | `detected_at − first_bad_at` | A8 + incident |
| **MTTA** (acknowledge / bắt đầu điều tra) | `investigation.started_at − detected_at` | investigations |
| **MTTM** (mitigate) | `mitigated_at − first_bad_at` (`mitigated_at` = lúc verification PASS đầu tiên) | actions |
| **MTTR** (resolve) | `resolved_at − first_bad_at` (`resolved_at` = sau failback hoàn tất và ổn định) | incidents |
| **User-impact minutes** | Σ phút có delivered SLI < objective | sli_1m (route) |
| **Requests saved** | request `ok` có `attempts > 1` hoặc được reroute trong cửa sổ incident | A13 |
| **Budget consumed** | (bad trong incident) / (allowed bad của window) | A5 |
| **Cost of reliability** | Chi phí retry + hedge + chênh lệch giá khi reroute | A13, A18 |

Mọi KPI đều tính từ `first_bad_at` để alert chậm không thể che giấu sự cố, sửa lỗi E10 của v0.
