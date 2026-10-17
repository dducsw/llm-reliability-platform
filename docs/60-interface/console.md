# Reflex Console

> Console **không** thay thế Datadog. Datadog là nơi quan sát và tương quan tín hiệu. Console là nơi **ra quyết định**: duyệt action, xem bằng chứng, chạy Time Machine, điều khiển scenario. Mọi màn hình đều có deep link sang Datadog.

## 1. Stack

React 18 + TypeScript + Vite · TanStack Router & Query · Tailwind + shadcn/ui · **ECharts** (chịu được dữ liệu dày, hỗ trợ markLine/markArea để vẽ event overlay) · SSE (`EventSource`) cho realtime · type sinh từ OpenAPI của control-plane (`openapi-typescript`).

## 2. Màn hình

| Route | Tên | Mục đích | Realtime |
| :--- | :--- | :--- | :--- |
| `/` | **Pulse** | Toàn cảnh: thẻ health theo route và target, Delivered vs Provider, budget, incident đang mở | SSE `health_state`, `incidents` |
| `/incidents` | Incidents | Danh sách, bộ lọc, MTTx KPIs (A17) | SSE |
| `/incidents/:key` | **War Room** | Màn hình quan trọng nhất (§3) | SSE |
| `/approvals` | Approvals | Action `awaiting_approval`: diff policy, guardrails, nút Duyệt hoặc Từ chối (kèm lý do) | SSE `actions` |
| `/memory` | Incident Memory | Bản đồ tương đồng (UMAP 2D, tính sẵn ở backend), tìm theo hình dạng | — |
| `/timemachine/:key` | Time Machine | Chọn variant → chạy → bảng và biểu đồ so sánh | SSE job |
| `/policies` | Policies | Policy hiện tại theo route, timeline version, diff | SSE |
| `/lab` | Chaos Lab | Chạy scenario, xem phase, expectations pass/fail theo thời gian thực | SSE `chaos_runs` |
| `/explain` | Query Explorer | Mọi con số trên Console → pipeline ID → pipeline JSON + `explain` summary | — |

## 3. War Room (`/incidents/:key`)

```
┌───────────────────────────────────────────────────────────────────────────────┐
│ INC-20261020-0007 · P1 · quality · vendorA:large → order.extract   ● MITIGATED│
│ MTTD 58s · MTTM 2m41s · Budget used 4.1% · Requests saved 1 226 · +$3.12      │
│ [Datadog: Monitor] [Logs] [Traces] [Notebook]                                 │
├───────────────────────────────────────────┬───────────────────────────────────┤
│ SIGNALS (ECharts, shared time axis)        │ TIMELINE                          │
│  Provider quality ───╲____________╱───     │ 10:15:02 first bad (A8)           │
│  Delivered quality ──────────────────      │ 10:16:00 Datadog M3 → incident    │
│  Router weights (stacked)  ▇▇▇▇░░░░▇▇      │ 10:16:01 Sentinel signal merged   │
│  ┆policy v17┆        ┆proof PASS┆          │ 10:17:43 Cortex H1 (0.86)         │
│                                            │ 10:17:45 shift_weight auto ✔      │
├───────────────────────────────────────────┤ 10:20:51 Recovery Proof PASS      │
│ CORTEX INVESTIGATION                       │ 10:41:00 failback 10% → 50% → 100%│
│  H1 vendorA:large truncates output (0.86)  │ 10:56:12 resolved                 │
│   ✓ finish_reason=length lift 41× [q_03]↗ │                                   │
│   ✓ probe direct quality 63% [q_02]↗      ├───────────────────────────────────┤
│   ✓ similar INC-…-0003 (0.91) [mem]↗      │ MEMORY: similar incidents         │
│  ✗ gateway regression — ruled out [q_02]   │  0003 sim .91 shift_weight PASS   │
│  Tools: 7 calls · 38s · $0.04 [LLMObs ↗]   │  0011 sim .87 shift_weight PASS   │
├───────────────────────────────────────────┤  0019 sim .82 hedging FAIL        │
│ ACTIONS                                    │  → shift_weight: 92% weighted     │
│  shift_weight 90% → vendorB:large  ✔ auto  │    success, median TTR 2m50s      │
│   guardrails ✔✔✔✔✔  proof: 99.4% [99.1,99.7]                                  │
│  failback_step 10/50/100 ✔✔✔               │ [▶ Open in Time Machine]          │
└───────────────────────────────────────────┴───────────────────────────────────┘
```

- Mỗi evidence `[q_03]↗` mở drawer chứa kết quả tool gốc (pipeline + output) hoặc link Datadog. Không có kết luận nào thiếu nguồn.
- Biểu đồ vẽ event overlay (policy applied, proof) bằng `markLine`.

## 4. Chế độ trình diễn

- **`?present=1`:** chữ to hơn, ẩn panel phụ, che các chuỗi giống secret.
- **Narration ribbon:** dải chú thích phía trên War Room cho biết hệ thống đang ở bước nào (DETECT / INVESTIGATE / RESPOND / VERIFY), giúp người xem video theo kịp.
- **Demo clock:** đồng hồ hiển thị cả thời gian thực và "DEMO TIME ×N".
