# Aggregation Pipeline Catalog

> Mỗi pipeline có ID cố định (A1…A16), được hiện thực trong `packages/reflex-mongo/reflex_mongo/pipelines/` dưới dạng **hàm Python thuần trả về `list[dict]`**. Nhờ vậy pipeline unit-test được (so sánh output trên fixture), explain-test được, và Console hiển thị được pipeline đã chạy ("Show me the query"). Console có panel cho giám khảo xem pipeline thật đã tạo ra con số đang hiển thị.

| ID | Tên | Bước | Collection | Kỹ thuật chính |
| :--- | :--- | :--- | :--- | :--- |
| [A1](#a1) | Attempt rollup → `sli_1m` | Detect | attempts_ts | `$dateTrunc`, `$percentile`, histogram, `$merge` on nhiều field |
| [A2](#a2) | Request rollup → `sli_1m` | Detect | requests_ts | như A1 |
| [A3](#a3) | Hourly rollup với cộng histogram | Lifecycle | sli_1m → sli_1h | `$reduce` + `$map` cộng vector |
| [A4](#a4) | Multi-window burn rate, một lần quét | Detect | sli_1m | conditional `$sum` |
| [A5](#a5) | Error budget còn lại | Detect / Report | sli_1h ∪ sli_1m | `$unionWith` |
| [A6](#a6) | Anomaly z-score + EWMA | Detect | sli_1m | `$setWindowFields`, `$stdDevSamp`, `$expMovingAvg` |
| [A7](#a7) | Probe blindness (mất tín hiệu) | Detect | probes_ts | `$densify`, `$fill` |
| [A8](#a8) | First-bad-at (cho MTTD) | Investigate | sli_1m | `$setWindowFields` (`$shift`) |
| [A9](#a9) | Incident signature vector | Investigate | sli_1m | `$densify`, `$fill linear`, chuẩn hóa, `$concatArrays` |
| [A10](#a10) | Sự cố tương tự + hiệu quả action | Investigate / Respond | incidents ⨝ actions | `$vectorSearch`, `$lookup`, `$median` |
| [A11](#a11) | Chẩn đoán phân biệt: provider hay gateway | Investigate | probes_ts | `$group` theo `meta.path` |
| [A12](#a12) | Dấu vết lỗi theo chiều (top-k contributors) | Investigate | attempts_ts | `$facet` đa chiều |
| [A13](#a13) | Blast radius & cost of incident | Respond | requests_ts | `$group` 2 tầng, `$sum` có điều kiện |
| [A14](#a14) | Baseline hour-of-week | Detect (context) | bench_ts → baselines | `$dateToParts`, `$median`, `$merge` |
| [A15](#a15) | Khai thác sự cố thật trong dataset | Scenario | bench_ts | `$setWindowFields` range window |
| [A16](#a16) | Recovery Proof data | Respond | sli_1m | `$facet` trước/sau |
| A17 | MTTD / MTTA / MTTR theo SLI & side | Report | incidents | `$percentile` trên thời lượng |
| A18 | Cost-of-reliability theo ngày (VN tz) | Report | sli_1h | `$dateTrunc` + `timezone: "Asia/Ho_Chi_Minh"` |

Quy ước: `NOW`, `FROM`, `TO` là tham số do Python truyền vào (kiểu `datetime`, UTC). `BOUNDS` là 19 biên hữu hạn của histogram. `NB = 20`.

---

<a id="a1"></a>
## A1 — Attempt rollup → `sli_1m`

Chạy mỗi 10s trên khoảng `[watermark − 3 phút, NOW)`. Mỗi lần chạy tính lại 3 phút gần nhất để xử lý late data. Nhờ `whenMatched: "replace"` nên pipeline idempotent.

```js
db.attempts_ts.aggregate([
  { $match: { "meta.env": ENV, ts: { $gte: FROM, $lt: TO } } },            // bucket skip
  { $match: { outcome: { $ne: "cancelled" } } },                            // hedge thua không vào SLI
  { $set: {
      minute: { $dateTrunc: { date: "$ts", unit: "minute" } },
      ok: { $eq: ["$outcome", "ok"] },
      lb: { $cond: [ { $eq: ["$outcome", "ok"] },
                     { $size: { $filter: { input: BOUNDS, cond: { $lte: ["$$this", "$latency_ms"] } } } },
                     -1 ] },
      tb: { $cond: [ { $eq: ["$outcome", "ok"] },
                     { $size: { $filter: { input: BOUNDS, cond: { $lte: ["$$this", "$ttft_ms"] } } } },
                     -1 ] }
  } },
  { $group: {
      _id: { key: "$meta.target", env: "$meta.env", ts: "$minute" },
      total:        { $sum: 1 },
      ok:           { $sum: { $cond: ["$ok", 1, 0] } },
      error:        { $sum: { $cond: [{ $eq: ["$outcome", "error"] }, 1, 0] } },
      timeout:      { $sum: { $cond: [{ $eq: ["$outcome", "timeout"] }, 1, 0] } },
      rate_limited: { $sum: { $cond: [{ $eq: ["$outcome", "rate_limited"] }, 1, 0] } },
      q_eligible:   { $sum: { $cond: [{ $ne: [{ $type: "$quality" }, "missing"] }, 1, 0] } },
      q_good:       { $sum: { $cond: [{ $eq: ["$quality.pass", true] }, 1, 0] } },
      pct:          { $percentile: { input: "$latency_ms", p: [0.5, 0.95, 0.99], method: "approximate" } },
      ttft_pct:     { $percentile: { input: "$ttft_ms",    p: [0.95],             method: "approximate" } },
      lbs: { $push: "$lb" }, tbs: { $push: "$tb" },
      retries: { $sum: { $cond: [{ $in: ["$kind", ["retry", "quality_retry"]] }, 1, 0] } },
      hedges:  { $sum: { $cond: [{ $eq: ["$kind", "hedge"] }, 1, 0] } },
      tokens_in:  { $sum: "$tokens_in" }, tokens_out: { $sum: "$tokens_out" },
      cost_usd:   { $sum: "$cost_usd" }
  } },
  { $set: {
      scope: "target", key: "$_id.key", env: "$_id.env", ts: "$_id.ts",
      err: { error: "$error", timeout: "$timeout", rate_limited: "$rate_limited" },
      p50: { $arrayElemAt: ["$pct", 0] }, p95: { $arrayElemAt: ["$pct", 1] }, p99: { $arrayElemAt: ["$pct", 2] },
      ttft_p95: { $arrayElemAt: ["$ttft_pct", 0] },
      lat_hist:  { $map: { input: { $range: [0, NB] }, as: "i",
                   in: { $size: { $filter: { input: "$lbs", cond: { $eq: ["$$this", "$$i"] } } } } } },
      ttft_hist: { $map: { input: { $range: [0, NB] }, as: "i",
                   in: { $size: { $filter: { input: "$tbs", cond: { $eq: ["$$this", "$$i"] } } } } } },
      watermark: "$$NOW"
  } },
  { $unset: ["_id", "pct", "ttft_pct", "lbs", "tbs", "error", "timeout", "rate_limited"] },
  { $merge: { into: "sli_1m", on: ["scope", "key", "env", "ts"],
              whenMatched: "replace", whenNotMatched: "insert" } }
])
```

**Ghi chú:** `$percentile` bỏ qua giá trị không phải số (attempt lỗi có `latency_ms: null`). `$push` tạo mảng tối đa vài trăm phần tử mỗi phút, an toàn. Ở tải cao hơn thì đổi sang `$group` hai tầng theo `(key, minute, bucket)`.

<a id="a2"></a>
## A2 — Request rollup (Delivered SLO)

Giống A1, khác ở các điểm: nguồn là `requests_ts`; `scope: "route"`, `key: "$meta.route"`; `ok` = `outcome == "ok"`; thêm `sheds`, `deadline`. **`quality_fail` được tính là bad** cho quality SLI, và `shed` được tính là bad cho availability SLI của route P0. Riêng P2, shed là hành vi theo thiết kế: SLO của route P2 loại shed khỏi mẫu số và báo cáo shed thành một chỉ số riêng.

<a id="a3"></a>
## A3 — Hourly rollup có cộng histogram

```js
db.sli_1m.aggregate([
  { $match: { ts: { $gte: HOUR_FROM, $lt: HOUR_TO } } },
  { $group: {
      _id: { scope: "$scope", key: "$key", env: "$env",
             ts: { $dateTrunc: { date: "$ts", unit: "hour" } } },
      total: { $sum: "$total" }, ok: { $sum: "$ok" },
      q_eligible: { $sum: "$q_eligible" }, q_good: { $sum: "$q_good" },
      cost_usd: { $sum: "$cost_usd" }, /* … các counter khác … */
      lh: { $push: "$lat_hist" }, th: { $push: "$ttft_hist" }
  } },
  { $set: {
      lat_hist: { $reduce: { input: "$lh", initialValue: ZEROS_NB,
        in: { $map: { input: { $range: [0, NB] }, as: "i",
              in: { $add: [ { $arrayElemAt: ["$$value", "$$i"] }, { $arrayElemAt: ["$$this", "$$i"] } ] } } } } },
      ttft_hist: { /* tương tự với $th */ }
  } },
  { $set: { scope: "$_id.scope", key: "$_id.key", env: "$_id.env", ts: "$_id.ts" } },
  { $unset: ["_id", "lh", "th"] },
  { $merge: { into: "sli_1h", on: ["scope", "key", "env", "ts"], whenMatched: "replace" } }
])
```
P95 của giờ được ước lượng từ `lat_hist` ở tầng app (`reflex_core.hist.quantile()`). Có unit test với sai số bị chặn.

<a id="a4"></a>
## A4 — Multi-window burn rate trong **một** lần quét

Thay vì chạy N pipeline cho N cửa sổ, quét một lần cửa sổ dài nhất và cộng có điều kiện. Pipeline được **sinh từ danh sách SLO**, nên mọi SLO cùng scope được tính trong một lần `aggregate`.

```js
// Ví dụ: availability, các cửa sổ 1m/5m/30m/6h (profile demo); budget = 1 - objective
db.sli_1m.aggregate([
  { $match: { scope: "target", env: ENV, key: { $in: KEYS }, ts: { $gte: NOW_MINUS_6H } } },
  { $group: {
      _id: "$key",
      t_1m:  { $sum: { $cond: [{ $gte: ["$ts", NOW_MINUS_1M]  }, "$total", 0] } },
      b_1m:  { $sum: { $cond: [{ $gte: ["$ts", NOW_MINUS_1M]  }, { $subtract: ["$total", "$ok"] }, 0] } },
      t_5m:  { $sum: { $cond: [{ $gte: ["$ts", NOW_MINUS_5M]  }, "$total", 0] } },
      b_5m:  { $sum: { $cond: [{ $gte: ["$ts", NOW_MINUS_5M]  }, { $subtract: ["$total", "$ok"] }, 0] } },
      t_30m: { /* … */ }, b_30m: { /* … */ },
      t_6h:  { $sum: "$total" }, b_6h: { $sum: { $subtract: ["$total", "$ok"] } },
      // quality: bad = q_eligible - q_good ; latency(T at bucket i): bad = ok - Σ lat_hist[0..i]
  } },
  { $lookup: { from: "slos", localField: "_id", foreignField: "key", as: "slo",
               pipeline: [ { $match: { sli: "availability", scope: "target" } } ] } },
  { $unwind: "$slo" },
  { $set: { budget: { $subtract: [1, "$slo.objective"] } } },
  { $project: {
      burn: {
        "1m":  { $cond: [{ $gt: ["$t_1m", 0] },  { $divide: [{ $divide: ["$b_1m", "$t_1m"] },   "$budget"] }, null] },
        "5m":  { $cond: [{ $gt: ["$t_5m", 0] },  { $divide: [{ $divide: ["$b_5m", "$t_5m"] },   "$budget"] }, null] },
        "30m": { /* … */ },
        "6h":  { $cond: [{ $gt: ["$t_6h", 0] },  { $divide: [{ $divide: ["$b_6h", "$t_6h"] },   "$budget"] }, null] }
      },
      samples: { "5m": "$t_5m", "6h": "$t_6h" }
  } }
])
```

**Quy tắc alert** (ở tầng app): tier `page` bắn khi `burn[long] ≥ factor AND burn[short] ≥ factor AND samples[short] ≥ min_samples`. Điều kiện `min_samples` chống false positive khi traffic thấp, vì 1 lỗi trên 2 request đã là burn 500 lần. `$lookup` trên `slos` (vài chục document) chi phí không đáng kể.

<a id="a5"></a>
## A5 — Error budget còn lại

```js
db.sli_1h.aggregate([
  { $match: { scope: S, key: K, env: ENV, ts: { $gte: WINDOW_START, $lt: CURRENT_HOUR } } },
  { $unionWith: { coll: "sli_1m", pipeline: [
      { $match: { scope: S, key: K, env: ENV, ts: { $gte: CURRENT_HOUR } } } ] } },
  { $group: { _id: null, total: { $sum: "$total" }, bad: { $sum: { $subtract: ["$total", "$ok"] } } } },
  { $project: {
      sli: { $subtract: [1, { $divide: ["$bad", "$total"] }] },
      allowed_bad: { $multiply: ["$total", BUDGET] },
      remaining: { $subtract: [1, { $divide: ["$bad", { $multiply: ["$total", BUDGET] }] }] }
  } }
])
```

<a id="a6"></a>
## A6 — Anomaly: z-score + EWMA

Bổ sung cho Datadog Anomaly Detection. Hai bên đối chiếu được, và A6 chạy cả khi Datadog trễ.

```js
db.sli_1m.aggregate([
  { $match: { scope: "target", env: ENV, ts: { $gte: NOW_MINUS_3H } } },
  { $setWindowFields: {
      partitionBy: "$key", sortBy: { ts: 1 },
      output: {
        mu:   { $avg:        "$ttft_p95", window: { range: [-60, -1], unit: "minute" } },
        sd:   { $stdDevSamp: "$ttft_p95", window: { range: [-60, -1], unit: "minute" } },
        ewma: { $expMovingAvg: { input: "$ttft_p95", alpha: 0.3 } }
      } } },
  { $match: { ts: { $gte: NOW_MINUS_5M } } },
  { $set: { z: { $cond: [{ $gt: ["$sd", 0] }, { $divide: [{ $subtract: ["$ttft_p95", "$mu"] }, "$sd"] }, 0] } } },
  { $match: { z: { $gte: 3 } } }
])
```
Cửa sổ `[-60, -1]` **loại phút hiện tại** để điểm bất thường không tự kéo baseline lên.

<a id="a7"></a>
## A7 — Probe blindness (`$densify` + `$fill`)

"Không có dữ liệu" cũng là một sự cố: nếu prober chết thì hệ thống bị mù.

```js
db.probes_ts.aggregate([
  { $match: { "meta.env": ENV, ts: { $gte: NOW_MINUS_10M, $lt: NOW_MINUTE } } },
  { $group: { _id: { target: "$meta.target", path: "$meta.path",
                     ts: { $dateTrunc: { date: "$ts", unit: "minute" } } }, n: { $sum: 1 } } },
  { $replaceWith: { target: "$_id.target", path: "$_id.path", ts: "$_id.ts", n: "$n" } },
  { $densify: { field: "ts", partitionByFields: ["target", "path"],
                range: { step: 1, unit: "minute", bounds: [NOW_MINUS_10M, NOW_MINUTE] } } },
  { $fill: { output: { n: { value: 0 } } } },
  { $match: { n: 0 } },
  { $group: { _id: { target: "$target", path: "$path" }, silent_minutes: { $sum: 1 } } }
])
```
**Hạn chế:** series mất dữ liệu *trong cả 10 phút* sẽ không xuất hiện, vì `$densify` cần ít nhất một document để có partition. Để xử lý, pipeline `$unionWith` thêm danh sách target kỳ vọng từ `targets` (document `n: 0` ở đầu cửa sổ). Datadog M6 (no-data monitor) là lớp phòng thủ thứ hai.

<a id="a8"></a>
## A8 — First-bad-at

MTTD được đo từ **phút xấu đầu tiên**, không phải từ lúc alert bắn ([định nghĩa KPI](../50-reliability/slo-and-error-budget.md#kpi)).

```js
db.sli_1m.aggregate([
  { $match: { scope: S, key: K, env: ENV, ts: { $gte: DETECTED_MINUS_60M, $lte: DETECTED_AT } } },
  { $set: { bad: { $gt: [ { $divide: [ { $subtract: ["$q_eligible", "$q_good"] }, { $max: ["$q_eligible", 1] } ] }, { $multiply: [BUDGET, 2] } ] } } },
  { $setWindowFields: { sortBy: { ts: 1 }, output: { prev_bad: { $shift: { output: "$bad", by: -1, default: false } } } } },
  { $match: { bad: true, prev_bad: false } },     // điểm chuyển từ tốt sang xấu
  { $sort: { ts: -1 } }, { $limit: 1 }            // lần chuyển gần nhất trước khi detect
])
```

<a id="a9"></a>
## A9 — Incident signature vector (64 chiều)

**Ý tưởng:** biểu diễn *hình dạng* của sự cố, gồm 4 tín hiệu × 16 phút quanh thời điểm phát hiện (12 phút trước, 4 phút sau). Mỗi tín hiệu được chuẩn hóa để hai sự cố cùng kiểu, dù khác target và khác mức traffic, vẫn cho vector gần nhau.

| Kênh | Công thức | Miền giá trị |
| :--- | :--- | :--- |
| c1 availability bad ratio | `(total-ok)/total` | [0, 1] |
| c2 quality bad ratio | `(q_eligible-q_good)/q_eligible` | [0, 1] |
| c3 latency shift | `clip(log2(p95 / baseline_p95), -3, 3) / 3` | [-1, 1] |
| c4 TTFT shift | `clip(log2(ttft_p95 / baseline_ttft), -3, 3) / 3` | [-1, 1] |

```js
db.sli_1m.aggregate([
  { $match: { scope: S, key: K, env: ENV, ts: { $gte: D_MINUS_12M, $lt: D_PLUS_4M } } },
  { $densify: { field: "ts", range: { step: 1, unit: "minute", bounds: [D_MINUS_12M, D_PLUS_4M] } } },
  { $fill: { sortBy: { ts: 1 }, output: { total: { value: 0 }, ok: { value: 0 },
             q_eligible: { value: 0 }, q_good: { value: 0 },
             p95: { method: "linear" }, ttft_p95: { method: "linear" } } } },
  { $set: {
      c1: { $cond: [{ $gt: ["$total", 0] }, { $divide: [{ $subtract: ["$total", "$ok"] }, "$total"] }, 0] },
      c2: { $cond: [{ $gt: ["$q_eligible", 0] }, { $divide: [{ $subtract: ["$q_eligible", "$q_good"] }, "$q_eligible"] }, 0] },
      c3: { $divide: [ { $max: [-3, { $min: [3, { $log: [ { $divide: [{ $ifNull: ["$p95", BASE_P95] }, BASE_P95] }, 2] }] }] }, 3 ] },
      c4: { $divide: [ { $max: [-3, { $min: [3, { $log: [ { $divide: [{ $ifNull: ["$ttft_p95", BASE_TTFT] }, BASE_TTFT] }, 2] }] }] }, 3 ] }
  } },
  { $sort: { ts: 1 } },
  { $group: { _id: null, c1: { $push: "$c1" }, c2: { $push: "$c2" }, c3: { $push: "$c3" }, c4: { $push: "$c4" } } },
  { $project: { _id: 0, vec: { $concatArrays: ["$c1", "$c2", "$c3", "$c4"] } } }
])
```
`BASE_P95` và `BASE_TTFT` = median của 60 phút trước cửa sổ (một truy vấn phụ `$median`), hoặc lấy từ `baselines` nếu thiếu dữ liệu. Vector được ghi vào `incidents.signature` và cập nhật lại một lần khi incident resolved (với cửa sổ đầy đủ).

<a id="a10"></a>
## A10 — Sự cố tương tự & hiệu quả của action

```js
db.incidents.aggregate([
  { $vectorSearch: {
      index: "incident_signature", path: "signature.vec", queryVector: VEC,
      numCandidates: 200, limit: 20,
      filter: { $and: [ { status: "resolved" }, { "signature.v": 2 }, { sli: SLI } ] } } },
  { $set: { sim: { $meta: "vectorSearchScore" } } },
  { $match: { sim: { $gte: 0.80 }, _id: { $ne: CURRENT_ID } } },
  { $lookup: { from: "actions", localField: "_id", foreignField: "incident_id", as: "acts",
               pipeline: [ { $match: { "verification.verdict": { $in: ["PASS", "FAIL"] }, parent_action_id: null } },
                           { $project: { type: 1, params: 1, "verification.verdict": 1, ttr_s: 1 } } ] } },
  { $unwind: "$acts" },
  { $group: {
      _id: "$acts.type",
      weight:  { $sum: "$sim" },
      tried:   { $sum: 1 },
      passed:  { $sum: { $cond: [{ $eq: ["$acts.verification.verdict", "PASS"] }, 1, 0] } },
      w_pass:  { $sum: { $cond: [{ $eq: ["$acts.verification.verdict", "PASS"] }, "$sim", 0] } },
      ttr_med: { $median: { input: "$acts.ttr_s", method: "approximate" } },
      examples:{ $topN: { n: 3, sortBy: { sim: -1 }, output: { key: "$key", sim: "$sim", params: "$acts.params" } } }
  } },
  { $set: { weighted_success: { $divide: ["$w_pass", "$weight"] } } },
  { $sort: { weighted_success: -1, ttr_med: 1 } }
])
```
Kết quả trả lời câu hỏi: *"Những sự cố trông giống thế này trước đây được xử lý bằng gì, và cách đó có hiệu quả không?"* Đây là input chính cho Cortex, và cũng hiển thị trực tiếp trong Console ngay cả khi không dùng LLM.

<a id="a11"></a>
## A11 — Chẩn đoán phân biệt: lỗi ở provider hay ở gateway

```js
db.probes_ts.aggregate([
  { $match: { "meta.target": T, "meta.env": ENV, ts: { $gte: NOW_MINUS_5M } } },
  { $group: { _id: "$meta.path",
      n: { $sum: 1 },
      ok: { $sum: { $cond: [{ $and: [{ $eq: ["$outcome", "ok"] }, { $eq: ["$quality.pass", true] }] }, 1, 0] } },
      p95: { $percentile: { input: "$latency_ms", p: [0.95], method: "approximate" } } } },
  { $group: { _id: null, paths: { $push: { k: "$_id", v: { ok_ratio: { $divide: ["$ok", "$n"] }, p95: { $first: "$p95" } } } } } },
  { $project: { paths: { $arrayToObject: "$paths" } } }
])
```

| `direct` | `via_gateway` | Kết luận |
| :--- | :--- | :--- |
| xấu | xấu | **provider_side** |
| tốt | xấu | **gateway_side** (S4) |
| tốt | tốt, nhưng traffic thật xấu | **workload_side** (prompt hoặc route cụ thể), chuyển sang A12 |

<a id="a12"></a>
## A12 — Top-k contributors

```js
db.attempts_ts.aggregate([
  { $match: { "meta.target": T, ts: { $gte: W_FROM, $lt: W_TO }, outcome: { $ne: "ok" } } },
  { $facet: {
      by_route:   [ { $group: { _id: "$route",         n: { $sum: 1 } } }, { $sort: { n: -1 } }, { $limit: 5 } ],
      by_outcome: [ { $group: { _id: "$outcome",       n: { $sum: 1 } } }, { $sort: { n: -1 } } ],
      by_finish:  [ { $group: { _id: "$finish_reason", n: { $sum: 1 } } }, { $sort: { n: -1 } } ],
      by_gateway: [ { $group: { _id: "$gateway_id",    n: { $sum: 1 } } } ],
      by_check:   [ { $unwind: "$quality.failed" }, { $group: { _id: "$quality.failed", n: { $sum: 1 } } } ],
      tokens_out: [ { $group: { _id: null, med: { $median: { input: "$tokens_out", method: "approximate" } } } } ]
  } }
])
```
Chạy song song cho cửa sổ baseline, rồi tính **lift** = tỉ lệ trong sự cố / tỉ lệ baseline. Chiều có lift cao nhất là manh mối hàng đầu. Trong S1, `finish_reason=length` có lift khoảng 40×.

<a id="a13"></a>
## A13 — Blast radius & chi phí của sự cố

```js
db.requests_ts.aggregate([
  { $match: { "meta.env": ENV, ts: { $gte: INC_FROM, $lt: INC_TO }, "meta.route": { $in: ROUTES } } },
  { $group: {
      _id: "$session",
      bad:     { $sum: { $cond: [{ $ne: ["$outcome", "ok"] }, 1, 0] } },
      saved:   { $sum: { $cond: [{ $and: [{ $eq: ["$outcome", "ok"] }, { $gt: ["$attempts", 1] }] }, 1, 0] } },
      reqs:    { $sum: 1 },
      cost:    { $sum: "$cost_usd" },
      rerouted:{ $sum: { $cond: [{ $ne: ["$final_target", "$primary_target"] }, 1, 0] } }
  } },
  { $group: {
      _id: null,
      sessions: { $sum: 1 },
      sessions_hurt: { $sum: { $cond: [{ $gt: ["$bad", 0] }, 1, 0] } },
      requests: { $sum: "$reqs" }, delivered_bad: { $sum: "$bad" },
      saved_by_reflex: { $sum: "$saved" }, rerouted: { $sum: "$rerouted" }, cost: { $sum: "$cost" }
  } }
])
```
`saved_by_reflex` là số request mà Reflex đã cứu bằng retry hoặc hedge. Đây là con số Impact đưa lên slide.

<a id="a14"></a>
## A14 — Baseline hour-of-week từ dataset public

```js
db.bench_ts.aggregate([
  { $match: { ts: { $gte: NOW_MINUS_60D } } },
  { $set: { p: { $dateToParts: { date: "$ts" } }, dow: { $isoDayOfWeek: "$ts" } } },   // UTC: peak theo giờ US/EU
  { $group: {
      _id: { model: "$meta.model", dow: "$dow", hour: "$p.hour" },
      lat_median:  { $median: { input: "$latency_ms", method: "approximate" } },
      lat_p90:     { $percentile: { input: "$latency_ms", p: [0.9], method: "approximate" } },
      ttft_median: { $median: { input: "$ttft_ms", method: "approximate" } },
      err_ratio:   { $avg: { $cond: [{ $eq: ["$status", "error"] }, 1, 0] } },
      samples: { $sum: 1 } } },
  { $set: { lat_p90: { $arrayElemAt: ["$lat_p90", 0] }, updated_at: "$$NOW" } },
  { $merge: { into: "baselines", on: "_id", whenMatched: "replace" } }
])
```

<a id="a15"></a>
## A15 — Khai thác sự cố thật trong dataset

```js
db.bench_ts.aggregate([
  { $match: { ts: { $gte: FROM, $lt: TO } } },
  { $setWindowFields: { partitionBy: "$meta.model", sortBy: { ts: 1 },
      output: { err6h: { $avg: { $cond: [{ $eq: ["$status", "error"] }, 1, 0] },
                         window: { range: [-5, 0], unit: "hour" } } } } },
  { $match: { err6h: { $gte: 0.5 } } },
  { $group: { _id: "$meta.model", worst: { $max: "$err6h" }, first: { $min: "$ts" }, last: { $max: "$ts" }, hours: { $sum: 1 } } },
  { $sort: { worst: -1, hours: -1 } }, { $limit: 10 }
])
```
Kết quả được dùng làm nguồn cho S6 và đưa vào slide: "Sự cố thật của model X ngày Y: lỗi kéo dài Z giờ".

<a id="a16"></a>
## A16 — Recovery Proof data

```js
db.sli_1m.aggregate([
  { $match: { scope: "route", key: R, env: ENV, ts: { $gte: BASE_FROM, $lt: AFTER_TO } } },
  { $facet: {
      baseline: [ { $match: { ts: { $lt: BASE_TO } } },    { $group: { _id: null, n: { $sum: "$q_eligible" }, good: { $sum: "$q_good" }, lh: { $push: "$lat_hist" } } } ],
      after:    [ { $match: { ts: { $gte: AFTER_FROM } } }, { $group: { _id: null, n: { $sum: "$q_eligible" }, good: { $sum: "$q_good" }, lh: { $push: "$lat_hist" } } } ]
  } }
])
```
Kiểm định thống kê (Wilson interval, two-proportion z-test, so sánh histogram) chạy ở tầng app. Xem [recovery-engine §Verify](../50-reliability/recovery-engine.md#verify).

---

## Kiểm thử pipeline

| Loại test | Cách làm |
| :--- | :--- |
| Golden output | Fixture JSONL → insert vào atlas-local → chạy pipeline → so sánh snapshot |
| Explain | `explain("executionStats")`: collection thường không được có `COLLSCAN`; Time Series phải có bucket filter trên `meta` và `control.min/max.ts` |
| Property test | Rollup A1 + A3 rồi tính A5 **bằng** tính trực tiếp trên raw (sai số = 0 với counter, bị chặn với percentile) |
| Hiệu năng | Benchmark 10M attempt (seed bằng generator), ghi lại thời gian chạy A1/A4/A9 vào `docs/30-data/benchmarks.md` |
