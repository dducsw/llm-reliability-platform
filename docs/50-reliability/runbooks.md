# Runbooks

> Mỗi monitor có một mục ở đây, được link từ monitor message. Cột **Auto** là những gì Reflex tự làm; cột **Human** là những gì người on-call nên kiểm tra.

<a id="M1"></a>
## M1/M2 — Delivered availability burn
| Bước | Auto | Human |
| :--- | :--- | :--- |
| 1 | Incident mở, Cortex nhận context pack | Mở Console → incident; xem "Delivered vs Provider" |
| 2 | Rule/Cortex: nếu provider_side thì `shift_weight` hoặc `open_circuit_global` | Nếu mọi target cùng xấu: nghi lỗi phía mình (M10) hoặc lỗi mạng |
| 3 | Verifier chứng minh hồi phục | Nếu FAIL 2 lần: `page_human` → cân nhắc `shed_priority` |

<a id="M3"></a>
## M3/M9 — Provider quality burn (Silent Brownout)
| Bước | Auto | Human |
| :--- | :--- | :--- |
| 1 | Quality retry ở gateway (Reflex) | Logs view "Quality failures": xem `@quality.failed`, `@finish_reason` |
| 2 | Cortex A12: tìm chiều có lift cao | Xác nhận bằng LLMObs span: `tokens_out` giảm? |
| 3 | `shift_weight` (auto nếu M9 xác nhận provider_side) | Kiểm tra trang status của vendor; ghi action item |

<a id="M4"></a>
## M4/M5 — TTFT burn / anomaly
Auto: `enable_hedging` cho route P0, có cost guard. Human: xem heatmap TTFT theo target; nếu chỉ một gateway bị thì kiểm tra tài nguyên host.

<a id="M6"></a>
## M6 — Probe silence
Auto: không có action lên traffic (không mù quáng hành động khi bị mù). Human: kiểm tra container prober và API key; dùng A7 để xem target nào câm.

<a id="M7"></a>
## M7 — Retry amplification
Auto: `set_concurrency` + giảm `retry.budget_ratio`; nếu budget P0 < 25% thì `shed_priority`. Human: xác nhận 429 có `Retry-After` không; liên hệ vendor về quota.

<a id="M10"></a>
## M10 — Gateway-side suspected
Auto: Cortex đề xuất `rollback_flag`, **cần duyệt**. Human: xem Deployment Tracking (version mới nhất), so sánh span `reflex.*` nội bộ giữa hai version; duyệt rollback trong Console.

<a id="M11"></a>
## M11–M13 — Meta monitors
Telemetry drop, detector disagreement, Cortex health. Không ảnh hưởng người dùng trực tiếp; cần ticket để xử lý trong giờ làm việc.
